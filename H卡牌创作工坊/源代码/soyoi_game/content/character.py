"""所依角色定义与战斗接线。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..core.cards import (
    Card,
    CardKeyword,
    CardRarity,
    CardSpec,
    CardType,
    PileType,
    RewardEffectOperation,
    RewardEffectSpec,
    TargetType,
)
from ..core.combat import CombatState
from ..soyoi.material_effect_resolver import MaterialEffectResolver
from ..soyoi.material_lifecycle import consume_retained_across_turn
from ..soyoi.material_runtime import begin_combat, store
from .materials import CORE_MATERIAL_IDS, MATERIAL_FACTORIES, make_material
from .soyoi_cards import PLAYABLE_REWARD_CARDS


STRIKE_SPEC = CardSpec(
    card_id="strike_soyoi", title="打击",
    base_cost=1, upgraded_cost=1,
    card_type=CardType.ATTACK, rarity=CardRarity.BASIC,
    target=TargetType.ANY_ENEMY,
    base_text="造成6点伤害。", upgraded_text="造成9点伤害。",
    base_effects=[RewardEffectSpec(RewardEffectOperation.DAMAGE, 6)],
    upgraded_effects=[RewardEffectSpec(RewardEffectOperation.DAMAGE, 9)],
)

DEFEND_SPEC = CardSpec(
    card_id="defend_soyoi", title="防御",
    base_cost=1, upgraded_cost=1,
    card_type=CardType.SKILL, rarity=CardRarity.BASIC,
    target=TargetType.SELF,
    base_text="获得5点格挡。", upgraded_text="获得8点格挡。",
    base_effects=[RewardEffectSpec(RewardEffectOperation.GAIN_BLOCK, 5)],
    upgraded_effects=[RewardEffectSpec(RewardEffectOperation.GAIN_BLOCK, 8)],
)

RUSH_JOB_SPEC = CardSpec(
    card_id="rush_job", title="赶制",
    base_cost=1, upgraded_cost=1,
    card_type=CardType.ATTACK, rarity=CardRarity.BASIC,
    target=TargetType.ANY_ENEMY,
    base_text="造成10点伤害。", upgraded_text="造成14点伤害。",
    base_effects=[RewardEffectSpec(RewardEffectOperation.DAMAGE, 10)],
    upgraded_effects=[RewardEffectSpec(RewardEffectOperation.DAMAGE, 14)],
)

TOUCH_UP_SPEC = CardSpec(
    card_id="touch_up", title="细修",
    base_cost=1, upgraded_cost=1,
    card_type=CardType.SKILL, rarity=CardRarity.BASIC,
    target=TargetType.SELF,
    base_text="获得9点格挡。", upgraded_text="获得13点格挡。",
    base_effects=[RewardEffectSpec(RewardEffectOperation.GAIN_BLOCK, 9)],
    upgraded_effects=[RewardEffectSpec(RewardEffectOperation.GAIN_BLOCK, 13)],
)

ASK_AROUND_SPEC = CardSpec(
    card_id="ask_around", title="群里问一圈",
    base_cost=0, upgraded_cost=0,
    card_type=CardType.SKILL, rarity=CardRarity.BASIC,
    target=TargetType.SELF,
    base_text="生成1张随机素材。消耗。",
    upgraded_text="生成1张随机素材。",
    base_keywords=[CardKeyword.EXHAUST], upgraded_keywords=[],
    base_effects=[RewardEffectSpec(RewardEffectOperation.ATTACH_MATERIAL)],
    upgraded_effects=[RewardEffectSpec(RewardEffectOperation.ATTACH_MATERIAL)],
)


@dataclass
class CharacterDef:
    name: str
    starting_hp: int
    starting_deck: list[CardSpec]
    starting_relics: list[str]
    card_pool: list[CardSpec]
    material_pool: list[Callable]


def build_character() -> CharacterDef:
    return CharacterDef(
        name="所依",
        starting_hp=72,
        starting_deck=[
            STRIKE_SPEC, STRIKE_SPEC, STRIKE_SPEC, STRIKE_SPEC,
            DEFEND_SPEC, DEFEND_SPEC, DEFEND_SPEC,
            RUSH_JOB_SPEC, TOUCH_UP_SPEC, ASK_AROUND_SPEC,
        ],
        starting_relics=["soy_sauce_department_badge"],
        card_pool=list(PLAYABLE_REWARD_CARDS),
        material_pool=list(MATERIAL_FACTORIES.values()),
    )


def instantiate_deck(character: CharacterDef) -> list[Card]:
    return [spec.create() for spec in character.starting_deck]


# 示例卡组的奖励牌（下标指向 PLAYABLE_REWARD_CARDS）
SAMPLE_REWARD_INDEXES = (0, 3, 6, 10, 12, 15, 20, 24)


def sample_deck_cards() -> dict[str, int]:
    """示例卡组的牌：角色原本的起始牌组 + 8 张奖励牌。"""
    counts: dict[str, int] = {}
    for spec in build_character().starting_deck:
        counts[spec.card_id] = counts.get(spec.card_id, 0) + 1
    for index in SAMPLE_REWARD_INDEXES:
        card_id = PLAYABLE_REWARD_CARDS[index].card_id
        counts[card_id] = counts.get(card_id, 0) + 1
    return counts


def setup_soyoi_combat(combat: CombatState) -> None:
    """给战斗注册素材触发与起始遗物。"""
    if combat.__dict__.get("_soyoi_setup_done"):
        return
    combat.__dict__["_soyoi_setup_done"] = True
    begin_combat(combat.player)
    material_resolver = MaterialEffectResolver(combat)

    def resolve_materials(state: CombatState, card: Card) -> None:
        material_resolver.resolve_after_carrier_played(card, state.last_card_target)

    def resolve_retained_materials(state: CombatState) -> None:
        hand = state.player.piles.pile(PileType.HAND).cards
        for card in list(hand):
            if consume_retained_across_turn(card):
                material_resolver.resolve_after_retained_across_turn(card)
            if state.check_outcome():
                break

    def badge_turn_start(state: CombatState) -> None:
        """起始遗物：每回合开始给一张随机素材牌。"""
        material_id = state.rng.choice(CORE_MATERIAL_IDS)
        store(state.player, make_material(material_id))

    combat.after_card_played.append(resolve_materials)
    combat.on_player_turn_start.append(resolve_retained_materials)
    combat.on_player_turn_start.append(badge_turn_start)
