import unittest

from soyoi_game.content.character import build_character
from soyoi_port.character import SOYOI


class RepositoryIntegrationTests(unittest.TestCase):
    def test_framework_and_character_port_share_core_values(self) -> None:
        framework_character = build_character()

        self.assertEqual(framework_character.name, SOYOI.name)
        self.assertEqual(framework_character.starting_hp, SOYOI.starting_hp)
        self.assertEqual(len(framework_character.starting_deck), len(SOYOI.starting_deck))


if __name__ == "__main__":
    unittest.main()
