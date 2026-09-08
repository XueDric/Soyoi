"""生物（Creature）抽象：玩家与敌人的共同数值与状态容器。

对应 C# 的 Creature / Player / AbstractEnemy。
- 挂状态(Power)
- 有生命、格挡
- 有意图(敌人用，见 enemy.py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .powers import Power, Powers, PowerKind

if TYPE_CHECKING:
    from .cards import Card


@dataclass
class Creature:
    """一个可战斗的生物。玩家和敌人共有。"""
    name: str
    max_hp: int
    hp: int = 0
    block: int = 0
    powers: dict[str, Power] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.hp == 0:
            self.hp = self.max_hp

    # --- 状态(Power) 接口 ---
    def has_power(self, name: str) -> bool:
        return name in self.powers and self.powers[name].amount > 0

    def get_power_amount(self, name: str) -> int:
        p = self.powers.get(name)
        return p.amount if p else 0

    def add_power(self, name: str, delta: int, kind: PowerKind = PowerKind.BUFF) -> int:
        p = self.powers.get(name)
        if p is None:
            p = Power(kind=kind, amount=0)
            self.powers[name] = p
        p.add(delta)
        return p.amount

    # --- 战斗数值 ---
    def gain_block(self, amount: float) -> int:
        self.block += int(amount)
        return self.block

    def take_attack(self, amount: float, attacker: Optional["Creature"] = None) -> int:
        """受到一次攻击。先扣格挡，溢出扣血。返回实际扣血量。"""
        dmg = int(amount)
        if dmg <= 0:
            return 0
        absorbed = min(self.block, dmg)
        self.block -= absorbed
        remainder = dmg - absorbed
        real = min(self.hp, remainder)
        self.hp -= real
        return real

    def is_dead(self) -> bool:
        return self.hp <= 0

    def reset_block(self) -> None:
        """回合结束清空格挡。"""
        self.block = 0

    def trigger_plating(self) -> None:
        """覆甲回合末结算：获得等于层数的格挡，然后层数-1。

        对应原版 Plated Seelie 行为：回合结束给 X 格挡，X-1。
        注意：此方法必须在敌人回合开始前调用，这样给的格挡能挡住本轮敌人。
        """
        plating = self.get_power_amount(Powers.PLATING)
        if plating > 0:
            self.gain_block(plating)
            self.add_power(Powers.PLATING, -1)

    def end_turn_tick(self) -> None:
        """回合结束的状态结算（中毒等）。基础在此，子类可扩展。"""
        poison = self.get_power_amount(Powers.POISON)
        if poison > 0:
            self.take_attack(poison)   # 中毒是失去生命还是攻击？简化：直接扣血，无视格挡
            self.add_power(Powers.POISON, -1)
        # 清理临时力量
        if self.has_power(Powers.TEMP_STRENGTH):
            self.powers[Powers.TEMP_STRENGTH].amount = 0
        if self.has_power(Powers.VIGOR):
            self.powers[Powers.VIGOR].amount = 0

        # 易伤/虚弱：每回合结束各减1层，避免永久累积（类尖塔标准行为）。
        # add_power 内部用 max(0, ...) 保证不会减到负数；减到 0 即清空该状态。
        if self.has_power(Powers.VULNERABLE):
            self.add_power(Powers.VULNERABLE, -1)
        if self.has_power(Powers.WEAK):
            self.add_power(Powers.WEAK, -1)
