"""素材卡与承载牌接口契约。"""

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

# 素材效果默认继承目标的操作集合
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


@dataclass(eq=False)
class MaterialCardBase(Card):
    #素材牌基类。继承 Card（本质是一张带效果的 Token Skill 牌）
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


# 能不能承载素材的判定
def can_carry_materials(card: Card) -> bool:
    #非素材牌即可承载素材。融合牌与基底牌都可承载，素材牌不可
    return not card.is_material


@dataclass
class MaterialCardSpec:
    #静态素材牌描述：创作端造出来的自制素材走这里
    card_id: str
    title: str
    base_text: str
    upgraded_text: str
    material_category: MaterialCategory = MaterialCategory.NORMAL
    material_effects: list[MaterialEffectSpec] = field(default_factory=list)
    base_cost: int = 0     # 素材牌不打出，费用固定 0（留着是为了和 CardSpec 用同一套界面代码）
    upgraded_cost: int = 0
    art: str = ""          # 卡面插画：相对卡牌目录的文件名，空串 = 程序画的占位图

    def create(self) -> MaterialCardBase:
        return MaterialCardBase(
            card_id=self.card_id,
            title=self.title,
            base_cost=self.base_cost,
            upgraded_cost=self.upgraded_cost,
            card_type=CardType.SKILL,
            rarity=CardRarity.TOKEN,
            target=TargetType.SELF,
            base_text=self.base_text,
            upgraded_text=self.upgraded_text,
            base_keywords=[CardKeyword.RETAIN, CardKeyword.UNPLAYABLE],
            upgraded_keywords=[CardKeyword.RETAIN, CardKeyword.UNPLAYABLE],
            material_category=self.material_category,
            material_effects=list(self.material_effects),
            art=self.art,
        )

def find_loadout(card: Card) -> Optional[MaterialLoadout]:
    #看一眼这张牌身上挂着的素材槽；没装过素材就返回 None（不创建）
    return card.__dict__.get("_material_loadout")


def get_loadout(card: Card) -> MaterialLoadout:
    #要用素材槽：没有就现建一个（第一次装素材时才会走到这里）。素材牌不可装，抛错、
    if not can_carry_materials(card):
        raise ValueError(f"{card.title} 是素材牌，不能再装备素材。")
    loadout = find_loadout(card)
    if loadout is None:
        loadout = MaterialLoadout(SLOTS_PER_CARD)
        card.__dict__["_material_loadout"] = loadout
        card.dynamic_vars["MaterialCount"] = 0
        card.dynamic_vars["MaterialLimit"] = SLOTS_PER_CARD
    return loadout
