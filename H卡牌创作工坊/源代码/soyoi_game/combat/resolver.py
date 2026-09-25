"""卡牌本体效果的统一结算器。"""

from __future__ import annotations

from typing import Optional

from ..core.cards import Card, CardKeyword, CardType, PileType, RewardEffectOperation, RewardEffectSpec, TargetType
from ..core.combat import CombatState
from ..core.creature import Creature
from ..core.powers import Powers, compute_attack_damage, compute_block_gain


class ResolveCard:
    """一次出牌的结算上下文。"""
    def __init__(self, combat: CombatState) -> None:
        self.combat = combat

    def resolve(self, card: Card, target: Optional[Creature] = None) -> None:
        from ..soyoi.material_lifecycle import consume_return_to_hand
        owner = self.combat.player
        # 活力覆盖这一张攻击牌的全部段数及附着伤害，不影响下一张牌。
        vigor = owner.get_power_amount(Powers.VIGOR) if card.card_type == CardType.ATTACK else 0
        try:
            for eff in card.current_effects():
                if owner.is_dead():
                    break
                self._apply_effect(card, eff, target)
            for cb in self.combat.after_card_played:
                if owner.is_dead():
                    break
                cb(self.combat, card)
        finally:
            if vigor:
                owner.add_power(Powers.VIGOR, -vigor)
            # 素材结算完成后再决定去向；消耗优先于返手，满手返手进弃牌堆。
            return_to_hand = consume_return_to_hand(card)
            if CardKeyword.EXHAUST in card.keywords:
                owner.piles.exhaust(card)
            elif return_to_hand and not owner.is_dead():
                owner.piles.put_in_hand(card, owner.hand_limit)
            else:
                owner.piles.move_to_discard(card)

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
                    if t.is_dead() or owner.is_dead():
                        break
                    dmg = compute_attack_damage(amount, owner, t)
                    t.take_attack(dmg, owner)
        elif op == RewardEffectOperation.GAIN_BLOCK:
            owner.gain_block(compute_block_gain(amount, owner))
        elif op == RewardEffectOperation.DRAW_CARDS:
            self.combat.draw_cards(int(amount))
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
            owner.lose_hp(int(amount))
        elif op == RewardEffectOperation.HEAL:
            owner.hp = min(owner.max_hp, owner.hp + int(amount))
        elif op == RewardEffectOperation.ATTACH_MATERIAL:
            # 打出「生成素材」的牌：素材变成一张手牌，装哪张由玩家点。
            from ..content.materials import CORE_MATERIAL_IDS, make_material
            from ..soyoi.material_runtime import store

            material_id = effect.material_id or self.combat.rng.choice(CORE_MATERIAL_IDS)
            store(owner, make_material(material_id))
        elif op == RewardEffectOperation.LOWER_ENEMY_STRENGTH_THIS_TURN:
            for t in targets_of(card.target):
                t.add_power(Powers.TEMP_STRENGTH, -int(amount))
        else:
            raise NotImplementedError(f"未实现的效果操作: {op}")
