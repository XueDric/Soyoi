import unittest

from soyoi_port.character import SOYOI, SoyoiTurnState, get_card_body_effects


class CharacterTests(unittest.TestCase):
    def test_character_matches_reference_start(self) -> None:
        self.assertEqual(SOYOI.starting_hp, 72)
        self.assertEqual(SOYOI.color_rgb, (127, 183, 190))
        self.assertEqual(len(SOYOI.starting_deck), 10)
        self.assertEqual(SOYOI.starting_deck.count("strike_soyoi"), 4)
        self.assertEqual(SOYOI.starting_deck.count("defend_soyoi"), 3)

    def test_material_turn_bonus(self) -> None:
        state = SoyoiTurnState(material_used_this_turn=True)
        self.assertEqual(get_card_body_effects("rush_job", False, state)[0].amount, 14)
        self.assertEqual(get_card_body_effects("touch_up", True, state)[0].amount, 20)


if __name__ == "__main__":
    unittest.main()

