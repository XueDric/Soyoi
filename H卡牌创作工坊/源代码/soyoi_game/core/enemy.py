"""敌人对象与意图系统。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from .cards import RewardEffectOperation
from .creature import Creature


class IntentAction(IntEnum):
    """敌人的意图种类，只有三种。"""
    ATTACK = 0          # 攻击：对玩家造成伤害（hits 段）
    DEFEND = 1          # 防御：给自己加格挡
    BUFF = 2            # 强化：给自己加力量
    UNKNOWN = 3         # 还没决定（开战前的占位）


ACTION_NAMES = {
    IntentAction.ATTACK: "攻击",
    IntentAction.DEFEND: "防御",
    IntentAction.BUFF: "强化",
    IntentAction.UNKNOWN: "未知",
}


@dataclass
class Intent:
    """一个意图 = 动作 + 数值 + 段数 + 说明文本（+ 可选附加效果）。"""
    action: IntentAction
    amount: int = 0
    hits: int = 1
    label: str = ""
    effect_operation: Optional[RewardEffectOperation] = None
    effect_amount: int = 0
    card_spec: Optional[object] = None

    @property
    def text(self) -> str:
        """给界面显示的文字，例如「啃咬 11」或「碾压 6×3」。"""
        if self.label:
            return self.label
        name = ACTION_NAMES[self.action]
        if self.action == IntentAction.ATTACK:
            return f"{name} {self.amount}×{self.hits}" if self.hits > 1 else f"{name} {self.amount}"
        if self.action == IntentAction.DEFEND:
            return f"{name} {self.amount}"
        if self.action == IntentAction.BUFF:
            return f"{name} 力量+{self.amount}"
        return name


@dataclass
class Enemy(Creature):
    """敌人。持有意图与行动模式。"""
    intent: Intent = field(default_factory=lambda: Intent(IntentAction.UNKNOWN))
    act_pattern: Optional[list] = None
    brain: Optional[object] = None
    # 敌人编号（jaw_worm / cultist）。界面按它找 assets/enemies/<id>.png 当立绘。
    enemy_id: str = ""

    def set_intent(self, intent: Intent) -> None:
        self.intent = intent
