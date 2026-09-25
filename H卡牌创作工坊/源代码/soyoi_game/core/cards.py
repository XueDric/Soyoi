"""基础卡牌与牌堆类型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional


class PileType(IntEnum):
    """牌堆类型：抽牌堆 / 手牌 / 弃牌堆 / 消耗堆。"""
    DRAW = 0
    HAND = 1
    DISCARD = 2
    EXHAUST = 3


class CardType(IntEnum):
    """卡牌类型。"""
    ATTACK = 0
    SKILL = 1
    POWER = 2


class CardRarity(IntEnum):
    """卡牌稀有度。"""
    BASIC = 0
    COMMON = 1
    UNCOMMON = 2
    RARE = 3
    TOKEN = 4   # 素材/衍生牌常用


class TargetType(IntEnum):
    """目标类型：自己 / 单个敌人 / 所有敌人。"""
    NONE = 0
    SELF = 1
    ANY_ENEMY = 2          # 攻击/单体
    ALL_ENEMIES = 3
    TARGETED_NO_CREATURE = 4
    SELF_OR_ONE = 5


class CardKeyword(IntEnum):
    """卡牌关键字。只放最常用、框架已支持的关键字。"""
    NONE = 0
    RETAIN = 1     # 保留：回合结束保持手牌
    EXHAUST = 2    # 消耗
    UNPLAYABLE = 3
    X_COST = 4
    ETHEREAL = 5   # 虚影：回合结束消失


@dataclass(eq=False)
class Card:
    """一张卡牌实例（每张实例独立，可携带升级状态与素材）。"""

    # --- 静态定义 (来自数据定义) ---
    card_id: str
    title: str
    base_cost: int
    upgraded_cost: int
    card_type: CardType
    rarity: CardRarity
    target: TargetType
    base_text: str = ""
    upgraded_text: str = ""
    base_keywords: list[CardKeyword] = field(default_factory=list)
    upgraded_keywords: list[CardKeyword] = field(default_factory=list)
    # 本体效果（静态表），由数据定义填充
    base_effects: list[RewardEffectSpec] = field(default_factory=list)
    upgraded_effects: list[RewardEffectSpec] = field(default_factory=list)

    # --- 运行时状态 ---
    upgraded: bool = False
    # 战斗中临时费用修正（本回合耗能 0、耗能 +1），不进存档
    cost_modifiers: dict[str, int] = field(default_factory=dict)
    # 本回合是否保留（Retain）
    retained_this_turn: bool = False
    # 常驻素材状态与本回合临时状态分开，换料时重新同步。
    material_retain: bool = False
    material_cost_modifier: int = 0

    # --- 动态卡面变量：key -> 当前值（见 DynamicVar）---
    dynamic_vars: dict[str, int] = field(default_factory=dict)

    # --- 卡面插画：相对卡牌目录的路径，如 "art/my_card.png"；空串 = 没图 ---
    art: str = ""

    def __post_init__(self) -> None:
        # 动态变量默认值，子类/数据定义可覆盖
        self.dynamic_vars.setdefault("MaterialCount", 0)
        self.dynamic_vars.setdefault("MaterialLimit", 3)

    @property
    def cost(self) -> int:
        """当前费用 = 基础/升级费用 + 临时修正。"""
        base = self.upgraded_cost if self.upgraded else self.base_cost
        return max(0, base + self.material_cost_modifier + sum(self.cost_modifiers.values()))

    @property
    def keywords(self) -> list[CardKeyword]:
        return list(self.upgraded_keywords if self.upgraded else self.base_keywords)

    @property
    def text(self) -> str:
        return self.upgraded_text if self.upgraded else self.base_text

    # --- 素材相关的三个属性：素材牌会覆盖，普通牌给默认值 ---
    # 界面直接用 card.xxx 就行，不用到处写 getattr。
    @property
    def is_material(self) -> bool:
        """这张牌是不是素材牌。普通牌一律 False。"""
        return False

    @property
    def effect_text(self) -> str:
        """素材效果的说明文字。普通牌没有素材效果，返回空串。"""
        return ""

    @property
    def category_text(self) -> str:
        """素材类别名（一次性 / 普通 / 永久 / 诅咒）。普通牌没有类别，返回空串。"""
        return ""

    def current_effects(self) -> list[RewardEffectSpec]:
        """当前生效的本体效果（随升级切换）。"""
        return list(self.upgraded_effects if self.upgraded else self.base_effects)

    def upgrade(self) -> None:
        """升级卡牌（卡面数值由数据定义，这里只翻转标记）。"""
        self.upgraded = True

    def reset_per_turn(self) -> None:
        """每回合开始重置的临时状态。"""
        self.cost_modifiers.clear()
        self.retained_this_turn = False


# 卡牌效果规格：操作 + 数值 + 段数
class RewardEffectOperation(IntEnum):
    """卡牌本体的效果操作（伤害、格挡、抽牌这些）。"""
    DAMAGE = 0
    GAIN_BLOCK = 1
    DRAW_CARDS = 2
    GAIN_ENERGY = 3
    APPLY_VULNERABLE = 4
    APPLY_WEAK = 5
    LOWER_ENEMY_STRENGTH_THIS_TURN = 6
    GAIN_STRENGTH = 7
    GAIN_TEMPORARY_STRENGTH = 8
    GAIN_VIGOR = 9
    GAIN_PLATING = 10
    GAIN_THORNS = 11
    LOSE_HP = 12
    HEAL = 13
    ATTACH_MATERIAL = 14


@dataclass
class RewardEffectSpec:
    """一条卡牌本体效果 = 操作 + 数值 + 段数。"""
    operation: RewardEffectOperation
    amount: float = 0.0
    hits: int = 1
    material_id: Optional[str] = None


# 一个方便的"卡牌工厂"，由内容数据生成 Card 实例
@dataclass
class CardSpec:
    """静态卡牌描述 (数据驱动)。内容层用这个描述一张卡。"""
    card_id: str
    title: str
    base_cost: int
    upgraded_cost: int
    card_type: CardType
    rarity: CardRarity
    target: TargetType
    base_text: str
    upgraded_text: str
    base_keywords: list[CardKeyword] = field(default_factory=list)
    upgraded_keywords: list[CardKeyword] = field(default_factory=list)
    base_effects: list[RewardEffectSpec] = field(default_factory=list)
    upgraded_effects: list[RewardEffectSpec] = field(default_factory=list)
    # 卡面插画：相对卡牌目录的路径。空串 = 用程序画的占位图。
    art: str = ""

    def create(self) -> Card:
        return Card(
            card_id=self.card_id,
            title=self.title,
            base_cost=self.base_cost,
            upgraded_cost=self.upgraded_cost,
            card_type=self.card_type,
            rarity=self.rarity,
            target=self.target,
            base_text=self.base_text,
            upgraded_text=self.upgraded_text,
            base_keywords=list(self.base_keywords),
            upgraded_keywords=list(self.upgraded_keywords),
            base_effects=list(self.base_effects),
            upgraded_effects=list(self.upgraded_effects),
            art=self.art,
        )
