import unittest

from soyoi_port.catalog import MATERIALS, REWARD_CARDS


class CatalogTests(unittest.TestCase):
    def test_full_reference_catalog_is_extracted(self) -> None:
        self.assertEqual(len(REWARD_CARDS), 80)
        self.assertEqual(len(MATERIALS), 17)
        self.assertEqual(REWARD_CARDS["soyoi_reward_001"].name, "拼豆弹射")
        self.assertEqual(MATERIALS["perler_color_pack"].name, "拼豆色包")


if __name__ == "__main__":
    unittest.main()

