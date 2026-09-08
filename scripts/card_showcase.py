"""依次结算 40 张奖励牌，输出可供课堂验收的战斗结果。"""

from __future__ import annotations

import random

from soyoi_game.content.character import STRIKE_SPEC, setup_soyoi_combat
from soyoi_game.content.soyoi_cards import PLAYABLE_REWARD_CARDS
from soyoi_game.core.cards import PileType, TargetType
from soyoi_game.core.combat import CombatState
from soyoi_game.core.enemy import Enemy
from soyoi_game.core.player import Player
from soyoi_game.soyoi.card import get_loadout


def run_card(spec) -> str:
    card = spec.create()
    fillers = [STRIKE_SPEC.create() for _ in range(5)]
    player = Player(name="所依", max_hp=72, hp=60, deck=fillers)
    player.energy = 99
    player.piles.pile(PileType.HAND).add(card)
    enemy = Enemy(name="测试木桩", max_hp=999)
    combat = CombatState(player=player, enemies=[enemy], rng=random.Random(7))
    combat.round_number = 1
    combat.phase = "player"
    setup_soyoi_combat(combat)

    combat.play_card(card, player if card.target == TargetType.SELF else enemy)

    powers = ",".join(f"{name}:{value.amount}" for name, value in player.powers.items() if value.amount) or "无"
    enemy_powers = ",".join(f"{name}:{value.amount}" for name, value in enemy.powers.items() if value.amount) or "无"
    return (
        f"{spec.card_id} {spec.title:<8} | 敌人HP {enemy.hp:>3} | "
        f"自身HP {player.hp:>2} 格挡 {player.block:>2} 能量 {player.energy:>2} | "
        f"手牌 {len(player.piles.pile(PileType.HAND).cards):>2} 素材 {get_loadout(card).material_count} | "
        f"自身状态 {powers} | 敌方状态 {enemy_powers}"
    )


def main() -> None:
    print("所依 40 张精简奖励牌战斗结算")
    print("=" * 90)
    for spec in PLAYABLE_REWARD_CARDS:
        print(run_card(spec))


if __name__ == "__main__":
    main()
