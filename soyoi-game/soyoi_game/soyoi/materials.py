"""素材系统：接口契约与核心数据结构。

对应 C# 的 SoyoiMod.SoyoiModCode.Materials 命名空间下的核心类型：
- MaterialCategory            (枚举)
- MaterialEffectOperation      (枚举，素材效果操作)
- MaterialEffectTiming         (枚举，素材效果触发时机)
- MaterialEffectTarget         (枚举，素材效果目标)
- MaterialEffectSpec           (一条素材效果)
- MaterialBundle               (一捆素材=组件列表，可能是复合)
- MaterialLoadout              (一张牌上的素材槽位 3 槽)
- MaterialCard                 (素材卡，见 soyoi/card.py，这里只定义基类数据类型)

这是队友移植卡牌时最重要的对齐点。所有数值都用 int/float，不用 decimal，
因为 Python 的 float/int 足够本游戏精度。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class MaterialCategory(IntEnum):
    """素材类别。对应 C# MaterialCategory。"""
    ONE_SHOT = 0     # 一次性
    NORMAL = 1       # 普通
    PERMANENT = 2    # 永久
    CURSE = 3        # 诅咒

    @property
    def label(self) -> str:
        return {
            MaterialCategory.ONE_SHOT: "一次性",
            MaterialCategory.NORMAL: "普通",
            MaterialCategory.PERMANENT: "永久",
            MaterialCategory.CURSE: "诅咒",
        }[self]


class MaterialEffectOperation(IntEnum):
    """素材效果操作。对应 C# MaterialEffectOperation。"""
    MATERIAL_DAMAGE = 0
    APPLY_VULNERABLE = 1
    APPLY_WEAK = 2
    GAIN_BLOCK = 3
    LOSE_STRENGTH_THIS_TURN = 4
    GAIN_PLATING = 5
    GRANT_RETAIN = 6
    REDUCE_NEXT_COST = 7
    DRAW_CARDS = 8
    PUT_OTHER_NON_MATERIAL_FROM_DISCARD_ON_DRAW_PILE = 9
    GAIN_ENERGY = 10
    RETURN_CARRIER_TO_HAND = 11
    ADD_WOUND_TO_DISCARD = 12
    INCREASE_CARRIER_COST = 13


class MaterialEffectTiming(IntEnum):
    """素材效果触发时机。对应 C# MaterialEffectTiming。"""
    PERSISTENT = 0                 # 持续常驻（如加费/保留）
    AFTER_CARRIER_PLAYED = 1       # 承载牌打出后
    AFTER_RETAINED_ACROSS_TURN = 2 # 跨回合保留后
    AFTER_CARRIER_NEXT_PLAYED = 3  # 承载牌下次打出后
    FIRST_CARRIER_PLAY_EACH_COMBAT = 4  # 本场第一次打出承载牌


class MaterialEffectTarget(IntEnum):
    """素材效果目标。对应 C# MaterialEffectTarget。"""
    INHERITED = 0   # 继承承载牌的目标
    OWNER = 1       # 玩家自己
    CARRIER = 2     # 承载牌（一般无目标，仅触发）


@dataclass
class MaterialEffectSpec:
    """一条素材效果。对应 C# MaterialEffectSpec (record)。

    字段对齐 C#：
        operation       操作
        amount          数值
        hits            段数（默认1）
        timing          触发时机
        target          目标
        once_per_turn   每回合限一次
        consumes_component  是否消耗该组件（一次性素材用）
    """
    operation: MaterialEffectOperation
    amount: float = 0.0
    hits: int = 1
    timing: MaterialEffectTiming = MaterialEffectTiming.AFTER_CARRIER_PLAYED
    target: MaterialEffectTarget = MaterialEffectTarget.INHERITED
    once_per_turn: bool = False
    consumes_component: bool = False


@dataclass
class MaterialBundle:
    """一捆素材 = 组件列表。可能是复合（>=2 组件合并）。

    对应 C# MaterialBundle (record)。
    category 是按组件中最高优先级的类别算：
        Curse > Permanent > Normal > OneShot
    """
    components: list["MaterialCard"] = field(default_factory=list)

    @property
    def is_composite(self) -> bool:
        return len(self.components) > 1

    @property
    def category(self) -> MaterialCategory:
        cs = [c.material_category for c in self.components]
        if MaterialCategory.CURSE in cs:
            return MaterialCategory.CURSE
        if MaterialCategory.PERMANENT in cs:
            return MaterialCategory.PERMANENT
        if MaterialCategory.NORMAL in cs:
            return MaterialCategory.NORMAL
        return MaterialCategory.ONE_SHOT

    @property
    def positive(self) -> bool:
        """正向素材（非诅咒）。"""
        return self.category != MaterialCategory.CURSE

    @classmethod
    def from_material(cls, material: "MaterialCard") -> "MaterialBundle":
        return cls([material])

    def merge(self, other: "MaterialBundle") -> "MaterialBundle":
        """合料：把两捆合并成一捆。诅咒不能参与合料（与 C# 一致）。"""
        if self.category == MaterialCategory.CURSE or other.category == MaterialCategory.CURSE:
            raise ValueError("诅咒素材不能参与合料。")
        return MaterialBundle(list(self.components) + list(other.components))

    @property
    def representative(self) -> Optional["MaterialCard"]:
        return self.components[0] if self.components else None


class MaterialLoadout:
    """一张承载牌上的素材槽位。对应 C# MaterialLoadout。

    固定 3 槽（SlotsPerCard=3）。支持：
    - get_next_slot(): 轮询空闲槽；全满返回当前的 _next_slot
    - replace(slot, bundle): 放入并返回被替换的旧素材
    - clear(slot): 清槽
    - rotate_left(): 槽位左移一格（C# RotateLeft）
    - material_count
    """
    def __init__(self, slot_count: int = 3) -> None:
        self.slots: list[Optional[MaterialBundle]] = [None] * slot_count
        self._next_slot = 0

    @property
    def material_count(self) -> int:
        return sum(1 for s in self.slots if s is not None)

    def get_next_slot(self, skip_curse: bool = False) -> int:
        n = len(self.slots)
        if n == 0:
            return -1
        for offset in range(n):
            candidate = (self._next_slot + offset) % n
            slot = self.slots[candidate]
            if slot is None:
                return candidate
        # 全满
        return self._next_slot

    def replace(self, slot: int, bundle: MaterialBundle) -> Optional[MaterialBundle]:
        if slot < 0 or slot >= len(self.slots):
            raise IndexError(f"slot out of range: {slot}")
        previous = self.slots[slot]
        self.slots[slot] = bundle
        self._next_slot = (slot + 1) % len(self.slots)
        return previous

    def clear(self, slot: int) -> None:
        if slot < 0 or slot >= len(self.slots):
            raise IndexError(f"slot out of range: {slot}")
        self.slots[slot] = None
        if slot < self._next_slot:
            self._next_slot = slot

    def rotate_left(self) -> None:
        n = len(self.slots)
        previous = list(self.slots)
        for i in range(n):
            self.slots[i] = None
        for i in range(n):
            material = previous[(i + 1) % n]
            if material is not None:
                self.slots[i] = material
        self._next_slot = 0


# 素材位数量是常量
SLOTS_PER_CARD = 3
