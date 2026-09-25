"""玩家对象：血量、能量、牌堆都在它身上。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import Card
from .creature import Creature
from .pile import PileManager


@dataclass
class Player(Creature):
    """玩家。继承 Creature 的生命/格挡/状态。"""
    energy: int = 0
    max_energy: int = 3
    draw_per_turn: int = 5
    hand_limit: int = 10
    deck: list[Card] = field(default_factory=list)   # 初始牌组定义
    piles: PileManager = field(default_factory=PileManager)

    def __post_init__(self) -> None:
        super().__post_init__()
        # 用初始牌组填满抽牌堆
        self.piles.pile(PileType.DRAW).cards.extend(self.deck)

    @property
    def combat_name(self) -> str:
        return "玩家"

    def gain_energy(self, amount: int) -> int:
        self.energy += amount
        return self.energy

    def start_turn(self, rng=None, draw_fn=None) -> None:
        """回合开始：回能量、清本回合状态、抽牌。"""
        self.energy = self.max_energy
        self.reset_block()   # 回合开始不清格挡？STSv1 格挡回合末清空，这里回合开始重置临时力量
        # 抽牌
        if draw_fn is None:
            self.piles.draw(self.draw_per_turn, self.hand_limit)
        else:
            draw_fn(self.draw_per_turn)


# 便于 import 的别称
from .cards import PileType  # noqa: E402
