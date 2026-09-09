"""战斗协调器：统一校验动作、结算卡牌和回合，并裁定胜负。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from .cards import Card, CardKeyword, PileType, TargetType
from .creature import Creature
from .enemy import Enemy, IntentAction
from .player import Player


@dataclass
class CombatState:
    player: Player
    enemies: list[Enemy] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)
    round_number: int = 0
    phase: str = "setup"  # setup | player | resolving | enemy | resolve | victory | defeat | error

    before_combat_start: list[Callable] = field(default_factory=list)
    after_card_played: list[Callable] = field(default_factory=list)
    after_card_drawn: list[Callable] = field(default_factory=list)
    on_player_turn_start: list[Callable] = field(default_factory=list)
    on_enemy_turn_end: list[Callable] = field(default_factory=list)
    on_round_end: list[Callable] = field(default_factory=list)

    materials_played_this_round: int = 0
    cards_played_this_round: int = 0
    last_card_target: Optional[Creature] = None

    def __post_init__(self) -> None:
        self.player.piles.shuffle_draw()

    @property
    def living_enemies(self) -> list[Enemy]:
        return [e for e in self.enemies if not e.is_dead()]

    @property
    def has_living_enemy(self) -> bool:
        return any(not e.is_dead() for e in self.enemies)

    def get_target(self) -> Optional[Enemy]:
        return next(iter(self.living_enemies), None)

    def check_outcome(self) -> bool:
        """统一裁定：同时死亡按失败处理；已经结束的战斗不可恢复。"""
        if self.phase in ("victory", "defeat"):
            return True
        if self.player.is_dead():
            self.phase = "defeat"
            return True
        if not self.has_living_enemy:
            self.phase = "victory"
            return True
        return False

    def start_combat(self) -> None:
        if self.phase != "setup":
            raise ValueError("战斗已开始；重新开始请创建新的战斗。")
        for cb in self.before_combat_start:
            cb(self)
        self.round_number = 0
        self.begin_player_turn()

    def begin_player_turn(self) -> None:
        if self.check_outcome():
            return
        from ..soyoi.persistent import sync_persistent_materials
        self.round_number += 1
        self.phase = "player"
        self.materials_played_this_round = 0
        self.cards_played_this_round = 0
        # 包括弃牌/消耗堆，避免洗回时带入上一回合临时状态。
        for pile in self.player.piles.piles.values():
            for card in pile.cards:
                card.reset_per_turn()
                sync_persistent_materials(card)
        self.player.start_turn(self.rng)
        self.next_enemy_intents()
        for cb in self.on_player_turn_start:
            cb(self)
            if self.check_outcome():
                break

    def validate_card_play(self, card: Card, target: Optional[Creature] = None) -> Optional[Creature]:
        """所有 UI/脚本共用的出牌校验；失败时不扣能量或移动卡牌。"""
        if self.check_outcome() or self.phase != "player":
            raise ValueError("当前不能出牌：不在有效的玩家回合。")
        if not self.player.piles.pile(PileType.HAND).contains(card):
            raise ValueError("这张牌不在手牌中。")
        if CardKeyword.UNPLAYABLE in card.keywords:
            raise ValueError(f"{card.title} 不可打出。")
        if card.cost > self.player.energy:
            raise ValueError(f"能量不足：{card.title} 需要 {card.cost}，当前 {self.player.energy}。")
        if card.target in (TargetType.SELF, TargetType.NONE, TargetType.TARGETED_NO_CREATURE):
            if target is not None and target is not self.player:
                raise ValueError("这张牌只能作用于玩家自身。")
            return self.player
        if card.target == TargetType.SELF_OR_ONE and target is self.player:
            return target
        target = target if target is not None else self.get_target()
        if not any(enemy is target for enemy in self.living_enemies):
            raise ValueError("请选择当前战斗中存活的敌人。")
        return target

    def play_card(self, card: Card, target: Optional[Creature] = None) -> None:
        target = self.validate_card_play(card, target)
        self.player.energy -= card.cost
        self.last_card_target = target
        # 正在结算的牌不能占手牌位，也不能被本次抽牌洗回。
        self.player.piles.remove(card)
        self.phase = "resolving"
        from ..combat.resolver import ResolveCard
        try:
            ResolveCard(self).resolve(card, target)
        except Exception:
            # 未预料的内容错误不能悄悄恢复为可继续操作的半结算战斗。
            self.phase = "error"
            raise
        self.cards_played_this_round += 1
        if not self.check_outcome():
            self.phase = "player"

    def end_player_turn(self) -> None:
        if self.check_outcome() or self.phase != "player":
            return
        self.discard_hand()
        self.player.trigger_plating()
        self.end_enemy_turn()
        if self.check_outcome():
            return
        self.resolve_round_end()
        if not self.check_outcome():
            self.begin_player_turn()

    def discard_hand(self) -> None:
        from ..soyoi.persistent import sync_persistent_materials
        for card in list(self.player.piles.pile(PileType.HAND).cards):
            sync_persistent_materials(card)
            if CardKeyword.ETHEREAL in card.keywords:
                self.player.piles.exhaust(card)
            elif not (CardKeyword.RETAIN in card.keywords or card.retained_this_turn or card.material_retain):
                self.player.piles.move_to_discard(card)

    def end_enemy_turn(self) -> None:
        self.phase = "enemy"
        # 上一敌方回合获得的格挡覆盖玩家回合，到这里才失效。
        for enemy in self.living_enemies:
            enemy.reset_block()
        for enemy in self.enemies:
            if self.player.is_dead():
                break
            if not enemy.is_dead():
                self.execute_enemy_intent(enemy)
        for cb in self.on_enemy_turn_end:
            if self.player.is_dead():
                break
            cb(self)

    def execute_enemy_intent(self, enemy: Enemy) -> None:
        from .powers import Powers, compute_attack_damage
        intent = enemy.intent
        if intent.action == IntentAction.ATTACK:
            for _ in range(intent.hits):
                if self.player.is_dead() or enemy.is_dead():
                    break
                self.player.take_attack(compute_attack_damage(intent.amount, enemy, self.player), enemy)
        elif intent.action == IntentAction.DEFEND:
            enemy.gain_block(intent.amount)
        elif intent.action == IntentAction.BUFF:
            enemy.add_power(Powers.STRENGTH, intent.amount)

    def resolve_round_end(self) -> None:
        self.phase = "resolve"
        for enemy in self.living_enemies:
            enemy.end_turn_tick()
        self.player.end_turn_tick()
        self.player.reset_block()
        for cb in self.on_round_end:
            if self.player.is_dead():
                break
            cb(self)

    def next_enemy_intents(self) -> None:
        for enemy in self.living_enemies:
            if enemy.act_pattern:
                enemy.intent = enemy.act_pattern[(self.round_number - 1) % len(enemy.act_pattern)]
