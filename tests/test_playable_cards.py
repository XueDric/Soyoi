import random
import unittest

from soyoi_game.content.character import (
    ASK_AROUND_SPEC,
    DEFEND_SPEC,
    RUSH_JOB_SPEC,
    STRIKE_SPEC,
    TOUCH_UP_SPEC,
    build_character,
    setup_soyoi_combat,
)
from soyoi_game.content.soyoi_cards import (
    COMMON_CARDS,
    PLAYABLE_REWARD_CARDS,
    RARE_CARDS,
    UNCOMMON_CARDS,
)
from soyoi_game.core.cards import PileType, TargetType
from soyoi_game.core.combat import CombatState
from soyoi_game.core.enemy import Enemy, Intent, IntentAction
from soyoi_game.core.player import Player
from soyoi_game.soyoi.card import get_loadout


class PlayableCardTests(unittest.TestCase):
    all_card_specs = [
        STRIKE_SPEC,
        DEFEND_SPEC,
        RUSH_JOB_SPEC,
        TOUCH_UP_SPEC,
        ASK_AROUND_SPEC,
        *PLAYABLE_REWARD_CARDS,
    ]

    def make_combat(self, card):
        player = Player(name="所依", max_hp=72, deck=[])
        player.energy = 99
        player.piles.pile(PileType.HAND).add(card)
        enemy = Enemy(name="测试木桩", max_hp=10000)
        combat = CombatState(player=player, enemies=[enemy], rng=random.Random(7))
        combat.round_number = 1
        combat.phase = "player"
        setup_soyoi_combat(combat)
        return combat, enemy

    def test_pool_is_the_requested_40_card_demo(self):
        character = build_character()

        self.assertEqual(len(PLAYABLE_REWARD_CARDS), 40)
        self.assertEqual(len(COMMON_CARDS), 20)
        self.assertEqual(len(UNCOMMON_CARDS), 15)
        self.assertEqual(len(RARE_CARDS), 5)
        self.assertEqual(character.card_pool, PLAYABLE_REWARD_CARDS)
        self.assertEqual(len({spec.card_id for spec in character.card_pool}), 40)

    def test_every_card_and_upgrade_resolves_in_combat(self):
        for spec in self.all_card_specs:
            for upgraded in (False, True):
                with self.subTest(card=spec.card_id, upgraded=upgraded):
                    card = spec.create()
                    if upgraded:
                        card.upgrade()
                    self.assertTrue(card.current_effects())
                    combat, enemy = self.make_combat(card)

                    target = combat.player if card.target == TargetType.SELF else enemy
                    combat.play_card(card, target)

                    all_finished_cards = (
                        combat.player.piles.pile(PileType.DISCARD).cards
                        + combat.player.piles.pile(PileType.EXHAUST).cards
                    )
                    self.assertIn(card, all_finished_cards)
                    self.assertFalse(combat.player.piles.pile(PileType.HAND).contains(card))
                    occurrences = sum(item is card for pile in combat.player.piles.piles.values() for item in pile.cards)
                    self.assertEqual(occurrences, 1)

    def test_material_card_runs_body_then_attached_effect(self):
        card = COMMON_CARDS[0].create()
        combat, enemy = self.make_combat(card)

        combat.play_card(card, enemy)

        self.assertEqual(enemy.hp, enemy.max_hp - 10)
        self.assertEqual(get_loadout(card).material_count, 1)
        self.assertEqual(combat.materials_played_this_round, 1)

    def test_starting_relic_attaches_one_material_each_turn(self):
        card = COMMON_CARDS[1].create()
        player = Player(name="所依", max_hp=72, deck=[card], draw_per_turn=1)
        combat = CombatState(
            player=player,
            enemies=[Enemy(name="测试木桩", max_hp=100)],
            rng=random.Random(3),
        )
        setup_soyoi_combat(combat)

        combat.start_combat()

        self.assertEqual(get_loadout(card).material_count, 1)
        self.assertEqual(combat.materials_played_this_round, 1)

    def test_plating_grants_block_then_loses_one_stack(self):
        from soyoi_game.core.powers import Powers
        player = Player(name="所依", max_hp=72, deck=[])
        enemy = Enemy(name="废料怪", max_hp=999, act_pattern=[Intent(IntentAction.ATTACK, 10)], intent=Intent(IntentAction.ATTACK, 10))
        combat = CombatState(player=player, enemies=[enemy], rng=random.Random(1))
        combat.round_number = 1
        player.add_power(Powers.PLATING, 3)

        combat.begin_player_turn()
        hp_before = player.hp
        combat.end_player_turn()

        # 覆甲3层 -> 回合末给3格挡, 挡敌人10点 -> 掉7血; 覆甲降到2
        self.assertEqual(player.hp, hp_before - 7, "覆甲3格挡应吸收敌人10点中的3点")
        self.assertEqual(player.get_power_amount(Powers.PLATING), 2, "覆甲应下降一层")


if __name__ == "__main__":
    unittest.main()
