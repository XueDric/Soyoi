"""牌堆运行时。末尾为堆顶；所有移动均按卡牌实例身份，而非卡面属性。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .cards import Card, PileType


@dataclass
class CardPile:
    pile_type: PileType
    cards: list[Card] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.cards

    def contains(self, card: Card) -> bool:
        return any(item is card for item in self.cards)

    def add(self, card: Card, index: int | None = None) -> None:
        """加入实例；默认加在堆顶（末尾），index=0 是堆底。"""
        if self.contains(card):
            return
        if index is None:
            self.cards.append(card)
        else:
            self.cards.insert(index, card)

    def remove(self, card: Card) -> bool:
        for index, item in enumerate(self.cards):
            if item is card:
                self.cards.pop(index)
                return True
        return False

    def draw_top(self) -> Optional[Card]:
        return self.cards.pop() if self.cards else None

    def peek_top(self) -> Optional[Card]:
        return self.cards[-1] if self.cards else None


@dataclass
class PileManager:
    """管理四堆牌。结算中的牌暂不在任何牌堆中，不能被抽到。"""
    piles: dict[PileType, CardPile] = field(default_factory=dict)
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self) -> None:
        if not self.piles:
            self.piles = {kind: CardPile(kind) for kind in PileType}

    def pile(self, pile_type: PileType) -> CardPile:
        return self.piles[pile_type]

    def shuffle_draw(self) -> None:
        self.rng.shuffle(self.piles[PileType.DRAW].cards)

    def remove(self, card: Card) -> bool:
        """从所有牌堆移出同一实例，不会删除另一张同名牌。"""
        removed = False
        for pile in self.piles.values():
            while pile.remove(card):
                removed = True
        return removed

    def move(self, card: Card, destination: PileType, index: int | None = None) -> None:
        self.remove(card)
        self.piles[destination].add(card, index)

    def ensure_draw_has_cards(self) -> None:
        if self.piles[PileType.DRAW].is_empty:
            discard = self.piles[PileType.DISCARD]
            if not discard.is_empty:
                self.rng.shuffle(discard.cards)
                self.piles[PileType.DRAW].cards.extend(discard.cards)
                discard.cards.clear()

    def draw(self, n: int, hand_limit: int = 10) -> list[Card]:
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
        self.move(card, PileType.DISCARD)

    def exhaust(self, card: Card) -> None:
        self.move(card, PileType.EXHAUST)

    def put_in_hand(self, card: Card, hand_limit: int = 10) -> None:
        """生成/返回手牌；手牌满则进弃牌堆，已经在手中则不重复添加。"""
        if self.piles[PileType.HAND].contains(card):
            return
        destination = (
            PileType.HAND if len(self.piles[PileType.HAND].cards) < hand_limit
            else PileType.DISCARD
        )
        self.move(card, destination)
