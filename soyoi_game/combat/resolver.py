"""卡牌本体效果的统一结算器。

对应 C# 的 RewardCardEffectResolver + RewardCardSpecialResolver 的职责：
- 把卡牌的 RewardEffectSpec 列表逐一执行（伤害/格挡/抽牌/给能量/上状态等）
- 处理基础关键字：EXHAUST（消耗）、RETAIN（保留）
- 切换目标类型（单体/全体/自身）

这是"本体效果"层。素材附加效果的结算在 soyoi/material_effect_resolver.py。
"""

from __future__ import annotations

from typing import Optional

from ..core.cards import Card, CardKeyword, RewardEffectOperation, RewardEffectSpec, TargetType
from ..core.combat import CombatState
from ..core.creature import Creature
from ..core.powers import Powers, compute_attack_damage, compute_block_gain


class ResolveCard:
    """一次出牌的结算上下文。"""
    def __init__(self, combat: CombatState) -> None:
        self.combat = combat

    def resolve(self, card: Card, target: Optional[Creature] = None) -> None:
        owner = self.combat.player
        discarded_to = self._end_location(card)

        effects = card.current_effects()

        for eff in effects:
            self._apply_effect(card, eff, target)

        # 关键字处理
        if CardKeyword.EXHAUST in card.keywords:
            owner.piles.exhaust(card)
        elif copied_to_field := discarded_to:
            # 返回手牌/抽牌堆顶等（覆盖默认"进弃牌堆"）
            pass
        else:
            owner.piles.move_to_discard(card)

        # 战斗后钩子
        for cb in self.combat.after_card_played:
            cb(self.combat, card)

    def _end_location(self, card: Card) -> Optional[str]:
        # hook：素材系统会在此重定向卡牌去向（ReturnCarrierToHand 等），
        # 见 soyoi/material_lifecycle.py。此处预留。
        return None

    def _apply_effect(self, card: Card, effect: RewardEffectSpec, target: Optional[Creature]) -> None:
        owner = self.combat.player
        enemies = self.combat.living_enemies
        op = effect.operation
        amount = effect.amount
        hits = effect.hits

        def targets_of(tg: TargetType) -> list[Creature]:
            base = card.target
            if base in (TargetType.ALL_ENEMIES,):
                return list(enemies)
            if base in (TargetType.SELF, TargetType.NONE, TargetType.TARGETED_NO_CREATURE):
                return [owner]
            # 单体：默认给 target，否则第一个存活敌人
            return [target or (enemies[0] if enemies else owner)]

        if op == RewardEffectOperation.DAMAGE:
            for t in targets_of(card.target):
                for _ in range(hits):
                    if t.is_dead():
                        break
                    dmg = compute_attack_damage(amount, owner, t)
                    t.take_attack(dmg, owner)
        elif op == RewardEffectOperation.GAIN_BLOCK:
            owner.gain_block(compute_block_gain(amount, owner))
        elif op == RewardEffectOperation.DRAW_CARDS:
            owner.piles.draw(int(amount), owner.hand_limit)
        elif op == RewardEffectOperation.GAIN_ENERGY:
            owner.gain_energy(int(amount))
        elif op == RewardEffectOperation.APPLY_VULNERABLE:
            for t in targets_of(card.target):
                t.add_power(Powers.VULNERABLE, int(amount))
        elif op == RewardEffectOperation.APPLY_WEAK:
            for t in targets_of(card.target):
                t.add_power(Powers.WEAK, int(amount))
        elif op == RewardEffectOperation.GAIN_STRENGTH:
            owner.add_power(Powers.STRENGTH, int(amount))
        elif op == RewardEffectOperation.GAIN_TEMPORARY_STRENGTH:
            owner.add_power(Powers.TEMP_STRENGTH, int(amount))
        elif op == RewardEffectOperation.GAIN_VIGOR:
            owner.add_power(Powers.VIGOR, int(amount))
        elif op == RewardEffectOperation.GAIN_PLATING:
            owner.add_power(Powers.PLATING, int(amount))
        elif op == RewardEffectOperation.GAIN_THORNS:
            owner.add_power(Powers.THORNS, int(amount))
        elif op == RewardEffectOperation.LOSE_HP:
            owner.hp = max(0, owner.hp - int(amount))
        elif op == RewardEffectOperation.HEAL:
            owner.hp = min(owner.max_hp, owner.hp + int(amount))
        elif op == RewardEffectOperation.ATTACH_MATERIAL:
            from ..content.materials import CORE_MATERIAL_IDS, make_material
            from ..soyoi.material_runtime import attach_next_available

            material_id = effect.material_id or self.combat.rng.choice(CORE_MATERIAL_IDS)
            material = make_material(material_id)
            attach_next_available(owner, card, material.as_bundle())
            self.combat.materials_played_this_round += 1
        elif op == RewardEffectOperation.LOWER_ENEMY_STRENGTH_THIS_TURN:
            for t in targets_of(card.target):
                t.add_power(Powers.TEMP_STRENGTH, -int(amount))
        else:
            raise NotImplementedError(f"未实现的效果操作: {op}")
