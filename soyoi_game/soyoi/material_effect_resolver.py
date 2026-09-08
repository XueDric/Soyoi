"""素材效果结算器。

对应 C# SoyoiMod.SoyoiModCode.Materials.MaterialEffectResolver。

核心职责：承载牌(Carrier)打出后，逐个素材槽、逐个组件、逐条效果结算。
- 只结算 timing 为 AFTER_CARRIER_PLAYED 或 FIRST_CARRIER_PLAY_EACH_COMBAT 的效果
- once_per_turn 的效果每回合只结算一次（这里用 combat 级计数器简化实现）
- consumes_component 的效果（一次性素材的组件）会把组件从槽中移除
- 临时效果（TemporaryMaterialEffectsRuntime）在打出后额外结算
- 复合素材(>1 组件)整体作为一个 bundle 结算

注意：这是"效果结算"层，不负责 UI 选牌、素材生成、附着等（那些在 material_runtime 里）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..core.cards import TargetType
from ..core.creature import Creature
from ..core.powers import Powers, compute_attack_damage, compute_block_gain
from ..soyoi.card import can_carry_materials, get_loadout, IMPLEMENTED_MATERIAL_OPERATIONS
from .materials import (
    MaterialEffectOperation,
    MaterialEffectSpec,
    MaterialEffectTarget,
    MaterialEffectTiming,
    MaterialBundle,
)

if TYPE_CHECKING:
    from ..core.combat import CombatState
    from ..core.cards import Card


class MaterialEffectResolver:
    """对一次承载牌打出进行素材效果结算。"""

    def __init__(self, combat: "CombatState") -> None:
        self.combat = combat
        self._used_this_round: set[tuple] = set()
        self._used_this_combat: set[tuple] = set()
        self._round_number: int | None = None

    def resolve_after_carrier_played(self, carrier: "Card", carrier_target: Optional[Creature] = None) -> None:
        """承载牌打出后结算全部素材效果。"""
        if not can_carry_materials(carrier):
            return
        loadout = get_loadout(carrier)
        round_no = self.combat.round_number
        if round_no != self._round_number:
            self._used_this_round.clear()
            self._round_number = round_no

        # 按槽号结算（C# 支持反向，这里默认正向）
        for slot in range(len(loadout.slots)):
            if self.combat.player.is_dead():
                break
            bundle = loadout.slots[slot]
            if bundle is None:
                continue
            self._resolve_bundle(carrier, carrier_target, bundle, round_no, loadout, slot)

    def _resolve_bundle(
        self,
        carrier: "Card",
        carrier_target: Optional[Creature],
        bundle: MaterialBundle,
        round_no: int,
        loadout,
        slot: int,
    ) -> None:
        """结算一捆素材（可能是复合）。"""
        survivors: list = []
        for component in bundle.components:
            consumed = False
            for effect_index, effect in enumerate(component.material_effects):
                if self.combat.player.is_dead():
                    break
                timing = effect.timing
                if timing not in (MaterialEffectTiming.AFTER_CARRIER_PLAYED, MaterialEffectTiming.FIRST_CARRIER_PLAY_EACH_COMBAT):
                    continue
                # 使用实例引用而不是裸 id，避免被消耗对象的 id 被后续对象复用。
                key = (carrier, component, effect_index)
                if timing == MaterialEffectTiming.FIRST_CARRIER_PLAY_EACH_COMBAT:
                    if key in self._used_this_combat:
                        continue
                    self._used_this_combat.add(key)
                if effect.once_per_turn:
                    if key in self._used_this_round:
                        continue
                    self._used_this_round.add(key)
                self._resolve_immediate(carrier, carrier_target, component, effect)
                if effect.consumes_component:
                    consumed = True
            if not consumed:
                survivors.append(component)

        # 更新槽位：组件被用完则清槽；部分存活则替换；否则保留
        if not survivors:
            loadout.clear(slot)
        elif len(survivors) != len(bundle.components):
            loadout.slots[slot] = MaterialBundle(survivors)
        # 更新卡面素材计数
        carrier.dynamic_vars["MaterialCount"] = loadout.material_count
        # 同步持久化效果（加费/保留），这里只更新动态变量占位
        self._sync_persistent(carrier, loadout)

    def _resolve_immediate(
        self,
        carrier: "Card",
        carrier_target: Optional[Creature],
        material: "Card",
        effect: MaterialEffectSpec,
    ) -> None:
        """结算一条素材效果。"""
        if effect.operation not in IMPLEMENTED_MATERIAL_OPERATIONS:
            return
        targets = self._resolve_targets(carrier, carrier_target, effect.target)
        op = effect.operation
        owner = self.combat.player

        if op == MaterialEffectOperation.MATERIAL_DAMAGE:
            for t in targets:
                for _ in range(effect.hits):
                    if t.is_dead() or owner.is_dead():
                        break
                    dmg = compute_attack_damage(effect.amount, owner, t)
                    t.take_attack(dmg, owner)
        elif op == MaterialEffectOperation.APPLY_VULNERABLE:
            for t in targets:
                t.add_power(Powers.VULNERABLE, int(effect.amount))
        elif op == MaterialEffectOperation.APPLY_WEAK:
            for t in targets:
                t.add_power(Powers.WEAK, int(effect.amount))
        elif op == MaterialEffectOperation.GAIN_BLOCK:
            owner.gain_block(compute_block_gain(effect.amount, owner))
        elif op == MaterialEffectOperation.LOSE_STRENGTH_THIS_TURN:
            for t in targets:
                t.add_power(Powers.TEMP_STRENGTH, -int(effect.amount))
        elif op == MaterialEffectOperation.GAIN_PLATING:
            owner.add_power(Powers.PLATING, int(effect.amount))
        elif op == MaterialEffectOperation.DRAW_CARDS:
            owner.piles.draw(int(effect.amount), owner.hand_limit)
        elif op == MaterialEffectOperation.GAIN_ENERGY:
            owner.gain_energy(int(effect.amount))
        elif op == MaterialEffectOperation.RETURN_CARRIER_TO_HAND:
            # 标记承载牌返回手牌（由 lifecycle/卡片去向处理）
            from .material_lifecycle import set_carrier_return_to_hand
            set_carrier_return_to_hand(carrier)
        elif op == MaterialEffectOperation.ADD_WOUND_TO_DISCARD:
            for _ in range(int(effect.amount)):
                from ..core.cards import Card, CardType, CardRarity, CardKeyword
                wound = Card(
                    card_id="wound", title="伤口", base_cost=0, upgraded_cost=0,
                    card_type=CardType.SKILL,
                    rarity=CardRarity.TOKEN, target=TargetType.NONE,
                    base_text="不可打出。", upgraded_text="不可打出。",
                    base_keywords=[CardKeyword.UNPLAYABLE],
                    upgraded_keywords=[CardKeyword.UNPLAYABLE],
                )
                owner.piles.move_to_discard(wound)
        elif op == MaterialEffectOperation.PUT_OTHER_NON_MATERIAL_FROM_DISCARD_ON_DRAW_PILE:
            self._put_other_non_material_from_discard_to_draw(carrier)
        # GRANT_RETAIN / REDUCE_NEXT_COST / INCREASE_CARRIER_COST 处理在 _sync_persistent

    def _resolve_targets(self, carrier: "Card", carrier_target: Optional[Creature], target: MaterialEffectTarget) -> list[Creature]:
        """确定素材效果的目标。对应 C# ResolveTargets。"""
        if target == MaterialEffectTarget.OWNER:
            return [self.combat.player]
        if target == MaterialEffectTarget.CARRIER:
            return []
        # INHERITED 是游戏规则：自身技能牌上的攻击/减益素材也作用于玩家。
        base = carrier.target
        if base in (TargetType.NONE, TargetType.SELF, TargetType.TARGETED_NO_CREATURE):
            return [self.combat.player]
        if base == TargetType.ALL_ENEMIES:
            return list(self.combat.living_enemies)
        # 单体
        return [carrier_target or self.combat.get_target() or self.combat.player]

    def _sync_persistent(self, carrier: "Card", loadout) -> None:
        """同步常驻效果，与临时保留/临时费用分开。"""
        from .persistent import sync_persistent_materials
        sync_persistent_materials(carrier)

    def _put_other_non_material_from_discard_to_draw(self, carrier: "Card") -> None:
        """从弃牌堆选一张非素材牌放到抽牌堆顶。简化：取第一张符合条件的。"""
        from ..core.cards import PileType
        discard = self.combat.player.piles.pile(PileType.DISCARD)
        for card in list(discard.cards):
            if card is not carrier and not getattr(card, "is_material", False):
                self.combat.player.piles.move(card, PileType.DRAW)
                break
