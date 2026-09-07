from __future__ import annotations

from dataclasses import dataclass

from .model import (
    CardDefinition,
    CardRarity,
    CardType,
    CharacterDefinition,
    EffectSpec,
    RelicDefinition,
    TargetType,
)


STARTER_MATERIAL_CHOICES = ("perler_color_pack", "felt_scrap", "button_battery")


STARTER_CARDS: dict[str, CardDefinition] = {
    "strike_soyoi": CardDefinition(
        id="strike_soyoi",
        name="打击",
        cost=1,
        upgraded_cost=1,
        card_type=CardType.ATTACK,
        rarity=CardRarity.BASIC,
        target=TargetType.ANY_ENEMY,
        base_text="造成6点伤害。",
        upgraded_text="造成9点伤害。",
        portrait="soyoi_strike.png",
        effects=(EffectSpec("damage", 6),),
        upgraded_effects=(EffectSpec("damage", 9),),
    ),
    "defend_soyoi": CardDefinition(
        id="defend_soyoi",
        name="防御",
        cost=1,
        upgraded_cost=1,
        card_type=CardType.SKILL,
        rarity=CardRarity.BASIC,
        target=TargetType.SELF,
        base_text="获得5点格挡。",
        upgraded_text="获得8点格挡。",
        portrait="soyoi_defend.png",
        effects=(EffectSpec("gain_block", 5, target="owner"),),
        upgraded_effects=(EffectSpec("gain_block", 8, target="owner"),),
    ),
    "rush_job": CardDefinition(
        id="rush_job",
        name="赶制",
        cost=1,
        upgraded_cost=1,
        card_type=CardType.ATTACK,
        rarity=CardRarity.BASIC,
        target=TargetType.ANY_ENEMY,
        base_text="造成8点伤害。若本回合使用过素材，额外造成6点伤害。",
        upgraded_text="造成12点伤害。若本回合使用过素材，额外造成8点伤害。",
        portrait="soyoi_rush_job.png",
        effects=(EffectSpec("damage", 8),),
        upgraded_effects=(EffectSpec("damage", 12),),
        requires_custom_logic=True,
    ),
    "touch_up": CardDefinition(
        id="touch_up",
        name="细修",
        cost=1,
        upgraded_cost=1,
        card_type=CardType.SKILL,
        rarity=CardRarity.BASIC,
        target=TargetType.SELF,
        base_text="获得7点格挡。若本回合使用过素材，额外获得7点格挡。",
        upgraded_text="获得10点格挡。若本回合使用过素材，额外获得10点格挡。",
        portrait="soyoi_touch_up.png",
        effects=(EffectSpec("gain_block", 7, target="owner"),),
        upgraded_effects=(EffectSpec("gain_block", 10, target="owner"),),
        requires_custom_logic=True,
    ),
    "ask_around": CardDefinition(
        id="ask_around",
        name="群里问一圈",
        cost=0,
        upgraded_cost=0,
        card_type=CardType.SKILL,
        rarity=CardRarity.BASIC,
        target=TargetType.SELF,
        base_text="选择1张普通素材加入手牌。消耗。",
        upgraded_text="选择1张普通素材加入手牌。",
        portrait="soyoi_material_selection.png",
        effects=(
            EffectSpec(
                "choose_material",
                target="owner",
                payload={"choices": STARTER_MATERIAL_CHOICES},
            ),
        ),
        upgraded_effects=(
            EffectSpec(
                "choose_material",
                target="owner",
                payload={"choices": STARTER_MATERIAL_CHOICES},
            ),
        ),
        keywords=("exhaust",),
        upgraded_keywords=(),
        requires_custom_logic=True,
    ),
}


SOY_SAUCE_DEPARTMENT_BADGE = RelicDefinition(
    id="soy_sauce_department_badge",
    name="酱油部活动证",
    text="每回合开始时，随机将1张普通素材加入手牌。素材不视为正常出牌。",
    turn_start_effects=(
        EffectSpec(
            "generate_random_material",
            target="owner",
            payload={"pool": STARTER_MATERIAL_CHOICES, "counts_as_card_play": False},
        ),
    ),
)


SOYOI = CharacterDefinition(
    id="soyoi",
    name="所依",
    english_name="Soyoi",
    description="酱油部的部娘。她用活动素材加工卡牌，在返工与成品之间周转。",
    starting_hp=72,
    color_rgb=(127, 183, 190),
    energy_per_turn=3,
    draw_per_turn=5,
    starting_deck=(
        "strike_soyoi",
        "strike_soyoi",
        "strike_soyoi",
        "strike_soyoi",
        "defend_soyoi",
        "defend_soyoi",
        "defend_soyoi",
        "rush_job",
        "touch_up",
        "ask_around",
    ),
    starting_relic=SOY_SAUCE_DEPARTMENT_BADGE,
)


@dataclass(frozen=True)
class SoyoiTurnState:
    material_used_this_turn: bool = False


def get_card_body_effects(
    card_id: str, upgraded: bool, state: SoyoiTurnState
) -> tuple[EffectSpec, ...]:
    """Return the playable body effects for the five starter cards."""
    card = STARTER_CARDS[card_id]
    effects = list(card.upgraded_effects if upgraded else card.effects)

    if state.material_used_this_turn and card_id == "rush_job":
        bonus = 8 if upgraded else 6
        effects[0] = EffectSpec("damage", effects[0].amount + bonus)
    elif state.material_used_this_turn and card_id == "touch_up":
        bonus = 10 if upgraded else 7
        effects[0] = EffectSpec("gain_block", effects[0].amount + bonus, target="owner")

    return tuple(effects)

