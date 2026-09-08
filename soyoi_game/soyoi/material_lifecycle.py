"""素材生命周期与回合计数辅助。

对应 C#：
- MaterialLifecycleRuntime ：返回手牌/牌堆、延迟加工、跨回合记录
- MaterialTurnRuntime     ：本回合拖出素材计数、最后消耗素材
- RedesignedCardRuntime   ：单牌加工成长记录、动态卡面数值
- CurrentPowerRuntime     ：回合触发的能力钩子（简化）

这些是队友移植大量卡牌时依赖的关键"状态记录"接口。
各 runtime 用挂在 combat / card / player 上的 dict（WeakKey，这里用 __dict__ 键）保存状态。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..core.cards import Card
    from ..core.combat import CombatState


def _card_state(card: "Card") -> dict:
    st = card.__dict__.get("_soyoi_state")
    if st is None:
        st = {
            "process_count": 0,        # 本场为此牌加工次数
            "growth": 0.0,             # 成长数值（连续打磨等）
            "merge_growth": 0,         # 合并成长
            "retain_growth": 0,        # 保留成长
            "return_to_hand": False,   # 打出后返回手牌
            "return_to_draw": False,   # 打出后返回抽牌堆顶
            "pending_energy_refund": 0,# 下次打出能量返还
            "retained_last_turn": False,
        }
        card.__dict__["_soyoi_state"] = st
    return st


# ---- MaterialTurnRuntime：本回合拖出素材计数 ----
def materials_played_this_round(combat: "CombatState") -> int:
    return getattr(combat, "materials_played_this_round", 0)


def mark_material_played(combat: "CombatState") -> None:
    combat.materials_played_this_round = getattr(combat, "materials_played_this_round", 0) + 1


def mark_last_exhausted_material(combat: "CombatState", material) -> None:
    combat.__dict__["_last_exhausted_material"] = material


def get_last_exhausted_material(combat: "CombatState"):
    return combat.__dict__.get("_last_exhausted_material")


# ---- MaterialLifecycleRuntime：返回手牌 / 延迟 ----
def set_carrier_return_to_hand(card: "Card") -> None:
    _card_state(card)["return_to_hand"] = True


def consume_return_to_hand(card: "Card") -> bool:
    st = _card_state(card)
    flag = st["return_to_hand"]
    st["return_to_hand"] = False
    return flag


def set_pending_energy_refund(card: "Card", amount: int) -> None:
    _card_state(card)["pending_energy_refund"] = amount


def consume_pending_energy_refund(card: "Card") -> int:
    st = _card_state(card)
    amount = st["pending_energy_refund"]
    st["pending_energy_refund"] = 0
    return amount


def mark_retained_across_turn(card: "Card") -> None:
    _card_state(card)["retained_last_turn"] = True


def consume_retained_across_turn(card: "Card") -> bool:
    st = _card_state(card)
    flag = st["retained_last_turn"]
    st["retained_last_turn"] = False
    return flag


# ---- RedesignedCardRuntime：加工成长 ----
def mark_processed(card: "Card") -> None:
    """一张牌被加工过一次，成长+1（换料不清零，复制不继承）。"""
    st = _card_state(card)
    st["process_count"] += 1
    _refresh_material_scaled(card)


def get_process_count(card: "Card") -> int:
    return _card_state(card)["process_count"]


def add_growth(card: "Card", amount: float) -> None:
    _card_state(card)["growth"] += amount
    _refresh_material_scaled(card)


def get_growth(card: "Card") -> float:
    return _card_state(card)["growth"]


def add_merge_growth(card: "Card", amount: int) -> None:
    _card_state(card)["merge_growth"] += amount
    _refresh_material_scaled(card)


def _refresh_material_scaled(card: "Card") -> None:
    # 简化：MaterialScaled 动态变量 = 加工次数（可被卡牌数据覆盖）
    card.dynamic_vars["MaterialScaled"] = _card_state(card)["process_count"]
