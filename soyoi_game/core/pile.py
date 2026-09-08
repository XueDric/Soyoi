"""牌堆运行时：抽牌堆、手牌、弃牌堆、消耗堆的容器与管理。

对应 C# 的 CardPile / CardPileCmd。
所有牌堆持有 Card 实例（引用），移动牌是"从一列挪到另一列"。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .cards import Card, PileType


@dataclass
class CardPile:
    """一列牌。name 对应 PileType。"""
    pile_type: PileType
    cards: list[Card] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.cards

    def add(self, card: Card, index: int | None = None) -> None:
        """加入牌堆。index 为 None 加到末尾，否则插入到指定位置（0=顶）。"""
        if index is None:
            self.cards.append(card)
        else:
            self.cards.insert(index, card)

    def remove(self, card: Card) -> bool:
        try:
            self.cards.remove(card)
            return True
        except ValueError:
            return False

    def draw_top(self) -> Optional[Card]:
        if not self.cards:
            return None
        return self.cards.pop()

    def peek_top(self) -> Optional[Card]:
        if not self.cards:
            return None
        return self.cards[-1]


@dataclass
class PileManager:
    """管理玩家的四堆牌，并处理"抽牌堆耗尽则把弃牌堆洗回"。

    对应 C# 中按 PileType 组织牌堆、以及 Draw 时的洗回逻辑。
    """
    piles: dict[PileType, CardPile] = field(default_factory=dict)
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self) -> None:
        if not self.piles:
            self.piles = {
                PileType.DRAW: CardPile(PileType.DRAW),
                PileType.HAND: CardPile(PileType.HAND),
                PileType.DISCARD: CardPile(PileType.DISCARD),
                PileType.EXHAUST: CardPile(PileType.EXHAUST),
            }

    def pile(self, pile_type: PileType) -> CardPile:
        return self.piles[pile_type]

    def shuffle_draw(self) -> None:
        self.rng.shuffle(self.piles[PileType.DRAW].cards)

    def ensure_draw_has_cards(self) -> None:
        """若抽牌堆为空且弃牌堆有牌，则把弃牌堆洗回抽牌堆。"""
        if self.piles[PileType.DRAW].is_empty:
            discard = self.piles[PileType.DISCARD]
            if not discard.is_empty:
                self.rng.shuffle(discard.cards)
                self.piles[PileType.DRAW].cards.extend(discard.cards)
                discard.cards.clear()

    def draw(self, n: int, hand_limit: int = 10) -> list[Card]:
        """抽 n 张到手中，受手牌上限约束。返回实际抽到的牌。"""
        drawn: list[Card] = []
        for _ in range(n):
            if len(self.piles[PileType.HAND].cards) >= hand_limit:
                break
            self.ensure_draw_has_cards()
            card = self.piles[PileType.DRAW].draw_top()
            if card is None:
                break
            self.piles[PileType.HAND].add(card)
            drawn.append(card)
        return drawn

    def move_to_discard(self, card: Card) -> None:
        """从手牌/任意堆移入弃牌堆。"""
        for pile in self.piles.values():
            if card in pile.cards:
                pile.remove(card)
                break
        self.piles[PileType.DISCARD].add(card)

    def exhaust(self, card: Card) -> None:
        for pile in self.piles.values():
            if card in pile.cards:
                pile.remove(card)
                break
        self.piles[PileType.EXHAUST].add(card)
