"""状态/能力(Power)系统。

对应 C# 的 PowerModel 及其子类（VulnerablePower / WeakPower / StrengthPower / PlatingPower 等）。
状态挂在"生物"(Creature) 上，影响伤害/格挡计算，并在回合末或满足条件时衰减。

设计要点：
- 每个 Power 是"一个可叠加层数的状态"。
- 伤害/格挡的统一结算以"乘算/加算"方式读 Power，不分散在各卡牌逻辑里。
- 本框架实现类杀戮尖塔的 5 个基础状态：格挡、力量、敏捷、易伤、弱化，
  外加酱油部用到的"活力(Vigor)" 与"覆甲(Plating)"，方便队友扩展。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class PowerKind(IntEnum):
    """状态种类。用于区分增/减益、是否回合末衰减。"""
    BUFF = 0
    DEBUFF = 1
    TEMP = 2        # 临时，回合末移


@dataclass
class Power:
    """一个状态实例。amount 为层数/数值。"""
    kind: PowerKind
    amount: int = 0
    # 本回合是否会被应用过（用于"每回合第一次"类触发，可留空）
    metadata: dict = field(default_factory=dict)

    def add(self, delta: int) -> int:
        self.amount = max(0, self.amount + delta)
        return self.amount

    def __int__(self) -> int:
        return self.amount


# 具体状态的命名常量，统一在此注册（方便数据层引用）
class Powers:
    # 基础（STSv1 通用）
    BLOCK = "Block"                     # 格挡（临时的，回合末清空，放在生物而非持久 Power）
    STRENGTH = "Strength"               # 力量：攻击伤害 +amount
    DEXTERITY = "Dexterity"             # 敏捷：格挡 +amount
    VULNERABLE = "Vulnerable"           # 易伤：受到攻击伤害 +50%
    WEAK = "Weak"                       # 虚弱：造成攻击伤害 -25%
    POISON = "Poison"                   # 中毒：回合末扣血并递减（本框架基础，选做）
    THORNS = "Thorns"                   # 荆棘：受击反伤

    # 酱油部 mod 用到的
    VIGOR = "Vigor"                     # 活力：下次攻击伤害 +amount（等同临时力量）
    PLATING = "Plating"                 # 覆甲：受到攻击时给格挡
    TEMP_STRENGTH = "TempStrength"      # 临时力量（PiercingWail 的正面）

    # 酱油部自定义 Power 的命名（队友移植时可注册更多，见 README）
    SOYO_CUSTOM = "SoyoiCustom"         # 占位，用于扩展


# 伤害/格挡统一计算函数。集中处理"易伤/虚弱/力量/敏捷"。
def compute_attack_damage(base_damage: float, attacker: "CreatureLike", target: "CreatureLike") -> float:
    """计算一次攻击的最终伤害。

    顺序（简化版，与 STSv1 一致）：
        dmg = base
        + attacker 力量/临时力量/活力
        * (1 - 虚弱 ? 0.25 : 0)
        * (1 + 易伤 ? 0.5 : 0)  易伤取目标身上的
    取整规则由调用方决定（这里返回 float，让 UI 层决定显示）。
    """
    dmg = float(base_damage)
    str_bonus = attacker.get_power_amount(Powers.STRENGTH)
    temp_str = attacker.get_power_amount(Powers.TEMP_STRENGTH)
    vigor = attacker.get_power_amount(Powers.VIGOR)
    dmg += float(str_bonus + temp_str + vigor)

    if attacker.has_power(Powers.WEAK):
        dmg *= 0.75
    if target.has_power(Powers.VULNERABLE):
        dmg *= 1.5
    return dmg


def compute_block_gain(base_block: float, owner: "CreatureLike") -> float:
    """计算获得的格挡。= base + 敏捷。"""
    return float(base_block) + float(owner.get_power_amount(Powers.DEXTERITY))
