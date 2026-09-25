"""按触发时机结算卡牌上的素材效果。"""

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
    #结算一张卡牌携带的素材

    def __init__(self, combat: "CombatState") -> None:
        self.combat = combat
        self._used_this_round: set[tuple] = set()
        self._used_this_combat: set[tuple] = set()
        self._round_number: int | None = None

    def resolve_after_carrier_played(self, carrier: "Card", carrier_target: Optional[Creature] = None) -> None:
        #打出卡牌后，结算普通、下次打出和本场首次效果
        timings = (
            MaterialEffectTiming.AFTER_CARRIER_PLAYED,
            MaterialEffectTiming.AFTER_CARRIER_NEXT_PLAYED,
            MaterialEffectTiming.FIRST_CARRIER_PLAY_EACH_COMBAT,
        )
        self._resolve(carrier, carrier_target, timings)

    def resolve_after_retained_across_turn(self, carrier: "Card") -> None:
        #卡牌跨回合保留后结算对应素材效果
        self._resolve(carrier, None, (MaterialEffectTiming.AFTER_RETAINED_ACROSS_TURN,))

    def _resolve(self, carrier: "Card", carrier_target: Optional[Creature], timings: tuple) -> None:
        if not can_carry_materials(carrier):
            return
        loadout = get_loadout(carrier)
        round_no = self.combat.round_number
        if round_no != self._round_number:
            self._used_this_round.clear()
            self._round_number = round_no

        # 按槽号结算（这里只做正向）
        for slot in range(len(loadout.slots)):
            if self.combat.player.is_dead():
                break
            bundle = loadout.slots[slot]
            if bundle is None:
                continue
            self._resolve_bundle(carrier, carrier_target, bundle, loadout, slot, timings)

    def _resolve_bundle(
        self,
        carrier: "Card",
        carrier_target: Optional[Creature],
        bundle: MaterialBundle,
        loadout,
        slot: int,
        timings: tuple,
    ) -> None:
        #结算素材（可能是复合）。
        survivors: list = []
        for component in bundle.components:
            consumed = False
            for effect_index, effect in enumerate(component.material_effects):
                if self.combat.player.is_dead():
                    break
                timing = effect.timing
                if timing not in timings:
                    continue
                # 使用实例引用而不是裸 id，避免被消耗对象的 id 被后续对象复用。
                key = (carrier, component, effect_index)
                one_shot = timing in (
                    MaterialEffectTiming.AFTER_CARRIER_NEXT_PLAYED,
                    MaterialEffectTiming.FIRST_CARRIER_PLAY_EACH_COMBAT,
                )
                if one_shot and key in self._used_this_combat:
                    continue
                if effect.once_per_turn and key in self._used_this_round:
                    continue
                applied = self._resolve_immediate(carrier, carrier_target, component, effect)
                if not applied:
                    continue
                if one_shot:
                    self._used_this_combat.add(key)
                if effect.once_per_turn:
                    self._used_this_round.add(key)
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
    ) -> bool:
        #结算一条素材效果。
        if effect.operation not in IMPLEMENTED_MATERIAL_OPERATIONS:
            return False
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
            self.combat.draw_cards(int(effect.amount))
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
        # GRANT_RETAIN / REDUCE_NEXT_COST 等处理在 _sync_persistent 里
        return True

    def _resolve_targets(self, carrier: "Card", carrier_target: Optional[Creature], target: MaterialEffectTarget) -> list[Creature]:
        #确定素材效果的目标。
        if target == MaterialEffectTarget.OWNER:
            return [self.combat.player]
        if target == MaterialEffectTarget.CARRIER:
            return []
        # INHERITED：自身技能牌上的攻击/减益素材也作用于玩家。
        base = carrier.target
        if base in (TargetType.NONE, TargetType.SELF, TargetType.TARGETED_NO_CREATURE):
            return [self.combat.player]
        if base == TargetType.ALL_ENEMIES:
            return list(self.combat.living_enemies)
        # 单体
        return [carrier_target or self.combat.get_target() or self.combat.player]

    def _sync_persistent(self, carrier: "Card", loadout) -> None:
        #同步常驻效果，与临时保留/临时费用分开
        from .persistent import sync_persistent_materials
        sync_persistent_materials(carrier)

    def _put_other_non_material_from_discard_to_draw(self, carrier: "Card") -> None:
        #从弃牌堆选一张非素材牌放到抽牌堆顶。简化：取第一张符合条件的
        from ..core.cards import PileType
        discard = self.combat.player.piles.pile(PileType.DISCARD)
        for card in list(discard.cards):
            if card is not carrier and not card.is_material:
                self.combat.player.piles.move(card, PileType.DRAW)
                break
