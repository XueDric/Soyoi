"""基础卡牌与牌堆类型定义。

对应 C# 侧的:
- CardType / CardRarity / TargetType / CardKeyword
- CardModel 的基础字段
本模块是纯数据枚举和 Card 数据类，不包含任何结算（结算见 resolver/）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional


class PileType(IntEnum):
    """牌堆类型。对应 C# 的 PileType。"""
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
    """目标类型。与 C# TargetType 对应。"""
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


@dataclass
class Card:
    """一张卡牌实例（每张实例独立，可携带升级状态与素材）。

    对应 C# 的 CardModel。注意：这不是静态定义，而是"某一局里的这张牌"，
    所以素材（MaterialLoadout）挂在实例上，不同实例的素材互不影响。
    """

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
    # 战斗中临时费用修正（本回合耗能为0、耗能+1 等），不进存档
    cost_modifiers: dict[str, int] = field(default_factory=dict)
    # 本回合是否保留（Retain）
    retained_this_turn: bool = False

    # --- 动态卡面变量（MaterialCount / MaterialLimit / MaterialScaled 等）---
    # 见 RedesignedCardRuntime 与 DynamicVar。key -> 当前值
    dynamic_vars: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 动态变量默认值，子类/数据定义可覆盖
        self.dynamic_vars.setdefault("MaterialCount", 0)
        self.dynamic_vars.setdefault("MaterialLimit", 3)

    @property
    def cost(self) -> int:
        """当前费用 = 基础/升级费用 + 临时修正。"""
        base = self.upgraded_cost if self.upgraded else self.base_cost
        return max(0, base + sum(self.cost_modifiers.values()))

    @property
    def keywords(self) -> list[CardKeyword]:
        return list(self.upgraded_keywords if self.upgraded else self.base_keywords)

    @property
    def text(self) -> str:
        return self.upgraded_text if self.upgraded else self.base_text

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


# 供队友移植时参考的"卡牌效果规格"（C# 的 RewardEffectSpec / RewardEffectOperation）
class RewardEffectOperation(IntEnum):
    """卡牌本体效果操作。对应 C# RewardEffectOperation。"""
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
    """一条卡牌本体效果 = 操作 + 数值 + 段数。对应 C# RewardEffectSpec。"""
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
        )
