import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from soyoi_game.core.cards import PileType, TargetType
from soyoi_game.ui.pygame_demo import HEIGHT, WIDTH, PygameCombatDemo


class PygameDemoTests(unittest.TestCase):
    def setUp(self):
        self.demo = PygameCombatDemo()

    def tearDown(self):
        pygame.display.quit()

    def test_first_frame_is_rendered(self):
        self.demo.draw()

        self.assertEqual(self.demo.canvas.get_size(), (WIDTH, HEIGHT))
        self.assertNotEqual(self.demo.canvas.get_at((20, 20)), self.demo.canvas.get_at((640, 360)))
        self.assertEqual(len(self.demo.combat.player.piles.pile(PileType.HAND).cards), 5)

    def test_attack_selects_target_then_deals_damage(self):
        hand = self.demo.combat.player.piles.pile(PileType.HAND).cards
        card = next(card for card in hand if card.target == TargetType.ANY_ENEMY)
        old_hp = self.demo.enemy.hp

        self.demo.select_or_play(card)
        self.assertIs(self.demo.selected_card, card)
        self.demo.handle_click(self.demo.enemy_rect.center)

        self.assertLess(self.demo.enemy.hp, old_hp)
        self.assertIsNone(self.demo.selected_card)

    def test_self_target_card_plays_immediately(self):
        hand = self.demo.combat.player.piles.pile(PileType.HAND).cards
        card = next(card for card in hand if card.target == TargetType.SELF)

        self.demo.select_or_play(card)

        self.assertNotIn(card, self.demo.combat.player.piles.pile(PileType.HAND).cards)

    def test_end_turn_advances_round(self):
        old_round = self.demo.combat.round_number

        self.demo.end_turn()

        self.assertEqual(self.demo.combat.round_number, old_round + 1)
        self.assertEqual(self.demo.combat.phase, "player")


if __name__ == "__main__":
    unittest.main()
