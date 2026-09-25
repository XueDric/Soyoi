"""课程 Demo 使用的六种核心素材。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from ..core.cards import CardKeyword, CardRarity, CardType, TargetType
from ..soyoi.card import MaterialCardBase
from ..soyoi.materials import (
    MaterialCategory,
    MaterialEffectOperation,
    MaterialEffectSpec,
    MaterialEffectTarget,
    MaterialEffectTiming,
)


def _material(
    material_id: str,
    title: str,
    text: str,
    operation: MaterialEffectOperation,
    amount: int,
    *,
    hits: int = 1,
    category: MaterialCategory = MaterialCategory.NORMAL,
    target: MaterialEffectTarget = MaterialEffectTarget.INHERITED,
    timing: Optional[MaterialEffectTiming] = None,
    consumes: bool = False,
) -> MaterialCardBase:
    if timing is None:
        timing = MaterialEffectTiming.AFTER_CARRIER_PLAYED
    return MaterialCardBase(
        card_id=material_id,
        title=title,
        base_cost=0,
        upgraded_cost=0,
        card_type=CardType.SKILL,
        rarity=CardRarity.TOKEN,
        target=TargetType.SELF,
        base_text=text,
        upgraded_text=text,
        base_keywords=[CardKeyword.RETAIN, CardKeyword.UNPLAYABLE],
        upgraded_keywords=[CardKeyword.RETAIN, CardKeyword.UNPLAYABLE],
        material_category=category,
        material_effects=[
            MaterialEffectSpec(
                operation=operation,
                amount=amount,
                hits=hits,
                timing=timing,
                target=target,
                consumes_component=consumes,
            )
        ],
    )


def make_perler_color_pack() -> MaterialCardBase:
    return _material(
        "perler_color_pack", "拼豆色包", "承载牌打出后额外造成3点伤害。",
        MaterialEffectOperation.MATERIAL_DAMAGE, 3,
    )


def make_felt_scrap() -> MaterialCardBase:
    return _material(
        "felt_scrap", "不织布裁片", "承载牌打出后获得4点格挡。",
        MaterialEffectOperation.GAIN_BLOCK, 4, target=MaterialEffectTarget.OWNER,
    )


def make_button_battery() -> MaterialCardBase:
    return _material(
        "button_battery", "纽扣电池", "承载牌打出后获得1点能量。",
        MaterialEffectOperation.GAIN_ENERGY, 1, target=MaterialEffectTarget.OWNER,
    )


def make_badge_blank() -> MaterialCardBase:
    return _material(
        "badge_blank", "吧唧底坯", "承载牌打出后给予1层易伤。",
        MaterialEffectOperation.APPLY_VULNERABLE, 1,
    )


def make_liquid_glue() -> MaterialCardBase:
    return _material(
        "liquid_glue", "流麻胶液", "承载牌打出后给予1层虚弱。",
        MaterialEffectOperation.APPLY_WEAK, 1,
    )


def make_self_sealing_bag() -> MaterialCardBase:
    return _material(
        "self_sealing_bag", "自封袋", "承载牌可跨回合保留。",
        MaterialEffectOperation.GRANT_RETAIN, 1,
        category=MaterialCategory.PERMANENT,
        target=MaterialEffectTarget.CARRIER,
        timing=MaterialEffectTiming.PERSISTENT,
    )


MATERIAL_FACTORIES: dict[str, Callable[[], MaterialCardBase]] = {
    "perler_color_pack": make_perler_color_pack,
    "felt_scrap": make_felt_scrap,
    "button_battery": make_button_battery,
    "badge_blank": make_badge_blank,
    "liquid_glue": make_liquid_glue,
    "self_sealing_bag": make_self_sealing_bag,
}

CORE_MATERIAL_IDS = tuple(MATERIAL_FACTORIES)


def make_material(material_id: str) -> MaterialCardBase:
    try:
        return MATERIAL_FACTORIES[material_id]()
    except KeyError as exc:
        raise ValueError(f"未知素材: {material_id}") from exc
