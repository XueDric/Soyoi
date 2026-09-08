"""战斗状态与回合循环。这是框架的协调中心（Coordinator）。

对应 C# 的 CombatState / CreatureCombatState 的职责：
- 持有 .player 与 .enemies
- 管理回合切换（玩家回合 -> 敌人回合 -> 回合结束结算）
- 提供查询方法：存活敌人、目标、本回合计数
- 触发各种事件钩子（BeforeCombatStart / AfterCardPlayed / 回合结束等）

设计：尽量把"事件"做成可注册的回调列表（observers），
这样队友的卡牌/素材/能力逻辑可以监听而不入侵核心。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from .cards import Card, PileType, RewardEffectOperation
from .creature import Creature
from .enemy import Enemy, Intent, IntentAction
from .pile import PileManager
from .player import Player


@dataclass
class CombatState:
    """一场战斗的完整状态。"""
    player: Player
    enemies: list[Enemy] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)
    round_number: int = 0
    phase: str = "setup"     # setup | player | enemy | resolve | done | victory | defeat

    # --- 事件钩子（由玩家/敌人/卡牌监听）---
    before_combat_start: list[Callable[["CombatState"], None]] = field(default_factory=list)
    after_card_played: list[Callable] = field(default_factory=list)
    after_card_drawn: list[Callable] = field(default_factory=list)
    on_player_turn_start: list[Callable] = field(default_factory=list)
    on_enemy_turn_end: list[Callable] = field(default_factory=list)
    on_round_end: list[Callable] = field(default_factory=list)

    # --- 素材/回合计数（酱油部 mod 用，见 soyoi/）---
    materials_played_this_round: int = 0
    cards_played_this_round: int = 0
    last_card_target: Optional[Creature] = None

    def __post_init__(self) -> None:
        # 初始牌堆整理：洗牌
        self.player.piles.shuffle_draw()

    @property
    def living_enemies(self) -> list[Enemy]:
        return [e for e in self.enemies if not e.is_dead()]

    @property
    def has_living_enemy(self) -> bool:
        return any(not e.is_dead() for e in self.enemies)

    def get_target(self) -> Optional[Enemy]:
        """返回默认目标（第一个存活敌人）。"""
        for e in self.enemies:
            if not e.is_dead():
                return e
        return None

    # --- 回合循环 ---
    def start_combat(self) -> None:
        for cb in self.before_combat_start:
            cb(self)
        self.round_number = 0
        self.begin_player_turn()

    def begin_player_turn(self) -> None:
        self.round_number += 1
        self.phase = "player"
        self.materials_played_this_round = 0
        self.cards_played_this_round = 0
        for card in self.player.piles.pile(PileType.DRAW).cards:
            card.reset_per_turn()
        for card in self.player.piles.pile(PileType.HAND).cards:
            card.reset_per_turn()
        self.player.start_turn(self.rng)
        for cb in self.on_player_turn_start:
            cb(self)

    def play_card(self, card: Card, target: Optional[Creature] = None) -> None:
        """玩家打出一张卡（入口）。实际结算由 resolver 处理（见 resolver/）。"""
        from .cards import CardKeyword, PileType as _P
        # 不可打出的牌（伤口/诅咒类）
        if CardKeyword.UNPLAYABLE in card.keywords:
            raise ValueError(f"{card.title} 不可打出。")
        cost = card.cost
        if cost > self.player.energy:
            raise ValueError(f"能量不足：{card.title} 需要 {cost}，当前 {self.player.energy}。")
        # 扣能量
        self.player.energy -= cost
        self.last_card_target = target
        self.phase = "resolving"
        from ..combat.resolver import ResolveCard   # 延迟导入避免循环
        resolve = ResolveCard(self)
        resolve.resolve(card, target)
        self.cards_played_this_round += 1
        self.phase = "player"

    def end_player_turn(self) -> None:
        """结束玩家回合：触发弃牌/保留、结算敌人回合。"""
        self.discard_hand()
        self.end_enemy_turn()
        self.resolve_round_end()
        if not self.has_living_enemy:
            self.phase = "victory"
            return
        if self.player.is_dead():
            self.phase = "defeat"
            return
        self.begin_player_turn()

    def discard_hand(self) -> None:
        """玩家手牌进入弃牌堆（保留牌除外）。"""
        hand = self.player.piles.pile(PileType.HAND)
        keep: list[Card] = []
        for card in list(hand.cards):
            from .cards import CardKeyword
            if CardKeyword.RETAIN in card.keywords or card.retained_this_turn:
                keep.append(card)
            else:
                self.player.piles.move_to_discard(card)
        hand.cards = keep

    def end_enemy_turn(self) -> None:
        """所有存活敌人按意图行动。"""
        self.phase = "enemy"
        for enemy in self.enemies:
            if enemy.is_dead():
                continue
            self.execute_enemy_intent(enemy)
        for cb in self.on_enemy_turn_end:
            cb(self)

    def execute_enemy_intent(self, enemy: Enemy) -> None:
        """执行单个敌人的意图。"""
        intent = enemy.intent
        if intent.action == IntentAction.ATTACK:
            from .powers import compute_attack_damage
            for _ in range(intent.hits):
                if self.player.is_dead():
                    break
                dmg = compute_attack_damage(intent.amount, enemy, self.player)
                self.player.take_attack(dmg, enemy)
        elif intent.action == IntentAction.DEFEND:
            enemy.gain_block(intent.amount)
        elif intent.action == IntentAction.BUFF:
            from .powers import Powers
            enemy.add_power(Powers.STRENGTH, intent.amount)
        # 其他意图（减益等）留给具体实现，框架提供扩展点

    def resolve_round_end(self) -> None:
        """回合结束结算：清空格挡、生物回合末 tick、触发钩子。"""
        self.phase = "resolve"
        for enemy in self.enemies:
            enemy.end_turn_tick()
            enemy.reset_block()
        self.player.end_turn_tick()
        self.player.reset_block()
        for cb in self.on_round_end:
            cb(self)

    def next_enemy_intents(self) -> None:
        """为每个存活敌人设置下回合意图（由数据层设定时也可单独调用）。"""
        # 若 enemy.act_pattern 存在，按轮次取意图（简化循环）
        for enemy in self.enemies:
            if enemy.is_dead() or enemy.act_pattern is None:
                continue
            idx = (self.round_number - 1) % len(enemy.act_pattern)
            enemy.intent = enemy.act_pattern[idx]
