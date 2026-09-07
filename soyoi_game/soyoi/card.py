"""素材卡与承载牌接口契约。

对应 C#：
- MaterialCard : SoyoiCard, IMaterialCard   —— 素材牌
- IMaterialCard 接口：MaterialCategory + MaterialEffects
- IMaterialCarrier / IDefinedFusionCard     —— 承载牌（能带素材）

队友移植卡牌时：
- 素材牌 -> 继承 MaterialCardBase，填 material_category 和 material_effects。
- 承载牌 -> 继承基类并让 LoadoutAvailable() 为真（默认所有非素材牌都可承载）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ..core.cards import Card, TargetType, CardType, CardRarity, CardKeyword
from .materials import (
    MaterialCategory,
    MaterialEffectSpec,
    MaterialEffectOperation,
    MaterialEffectTiming,
    MaterialEffectTarget,
    MaterialBundle,
    MaterialLoadout,
    SLOTS_PER_CARD,
)

# 素材效果默认"继承目标"对应的操作集合（参考 C# MaterialEffectResolver.ImplementedOperations）
IMPLEMENTED_MATERIAL_OPERATIONS = {
    MaterialEffectOperation.MATERIAL_DAMAGE,
    MaterialEffectOperation.APPLY_VULNERABLE,
    MaterialEffectOperation.APPLY_WEAK,
    MaterialEffectOperation.GAIN_BLOCK,
    MaterialEffectOperation.LOSE_STRENGTH_THIS_TURN,
    MaterialEffectOperation.GAIN_PLATING,
    MaterialEffectOperation.DRAW_CARDS,
    MaterialEffectOperation.GAIN_ENERGY,
    MaterialEffectOperation.RETURN_CARRIER_TO_HAND,
    MaterialEffectOperation.ADD_WOUND_TO_DISCARD,
    MaterialEffectOperation.PUT_OTHER_NON_MATERIAL_FROM_DISCARD_ON_DRAW_PILE,
}


@dataclass
class MaterialCardBase(Card):
    """素材牌基类。继承 Card（本质是一张带效果的 Token Skill 牌）。

    material_category : 素材类别
    material_effects  : 素材效果列表（数据驱动）
    """
    material_category: MaterialCategory = MaterialCategory.NORMAL
    material_effects: list[MaterialEffectSpec] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__post_init__()
        if CardKeyword.RETAIN not in self.base_keywords:
            self.base_keywords.append(CardKeyword.RETAIN)

    @property
    def is_material(self) -> bool:
        return True

    @property
    def effect_text(self) -> str:
        # 简化：把素材效果拼成可读文本，供 UI 显示
        from .materials_render import describe_material_effect
        return " ".join(describe_material_effect(e) for e in self.material_effects)

    @property
    def category_text(self) -> str:
        return self.material_category.label

    def as_bundle(self) -> MaterialBundle:
        return MaterialBundle.from_material(self)


# 承载能力的判定（对应 C# MaterialAttachmentRuntime.CanCarryMaterials / IsBaseCard）
def can_carry_materials(card: Card) -> bool:
    """非素材牌即可承载素材。融合牌与基底牌都可承载，素材牌不可。"""
    return not getattr(card, "is_material", False)


def get_loadout(card: Card) -> MaterialLoadout:
    """懒加载一张牌的素材装载。素材牌不可装，抛错（与 C# 一致）。"""
    if not can_carry_materials(card):
        raise ValueError(f"{card.title} 是素材牌，不能再装备素材。")
    loadout = card.__dict__.get("_material_loadout")
    if loadout is None:
        loadout = MaterialLoadout(SLOTS_PER_CARD)
        card.__dict__["_material_loadout"] = loadout
        card.dynamic_vars["MaterialCount"] = 0
        card.dynamic_vars["MaterialLimit"] = SLOTS_PER_CARD
    return loadout
