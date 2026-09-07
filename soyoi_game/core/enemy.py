"""敌人对象与意图系统。对应 C# 的 AbstractEnemy / 意图(intents)。

敌人每回合展示意图（下回合要做什么），玩家据此决策。
意图是一个可预测的行动描述：(动作类型, 数值, 段数, 目标)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from .cards import RewardEffectOperation
from .creature import Creature


class IntentAction(IntEnum):
    """敌人意图动作。"""
    ATTACK = 0
    DEFEND = 1          # 获得格挡
    BUFF = 2            # 加 buff（力量/临时力量）
    DEBUFF = 3          # 给玩家施加减益
    UNKNOWN = 4


@dataclass
class Intent:
    """一个意图 = 动作 + 数值 + 段数 + 说明文本。"""
    action: IntentAction
    amount: int = 0
    hits: int = 1
    label: str = ""
    # 对应卡牌效果操作，方便复用结算
    effect_operation: Optional[RewardEffectOperation] = None

    @property
    def text(self) -> str:
        if self.label:
            return self.label
        action_name = {
            IntentAction.ATTACK: "攻击",
            IntentAction.DEFEND: "防御",
            IntentAction.BUFF: "强化",
            IntentAction.DEBUFF: "减益",
            IntentAction.UNKNOWN: "未知",
        }[self.action]
        if self.action == IntentAction.ATTACK and self.hits > 1:
            return f"{action_name} {self.amount} ×{self.hits}"
        if self.action == IntentAction.ATTACK:
            return f"{action_name} {self.amount}"
        return action_name


@dataclass
class Enemy(Creature):
    """敌人。持有意图与行动模式。

    act_pattern 供数据层定义：一个可索引的行动序列，
    resolve_intent() 由战斗状态调用，返回本回合要执行的 Intent。
    """
    intent: Intent = field(default_factory=lambda: Intent(IntentAction.UNKNOWN))
    # 行动模式：list[Intent]，由 combat 按 turn 索引；或自定义 callable
    act_pattern: Optional[list] = None

    def set_intent(self, intent: Intent) -> None:
        self.intent = intent
