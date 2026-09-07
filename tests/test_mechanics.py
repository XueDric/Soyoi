import unittest

from soyoi_port.catalog import get_material
from soyoi_port.character import STARTER_CARDS
from soyoi_port.mechanics import attach_material, resolve_materials
from soyoi_port.model import CardInstance, MaterialInstance, MaterialTiming


class MaterialMechanicsTests(unittest.TestCase):
    def test_one_slot_mvp_replaces_existing_material(self) -> None:
        carrier = CardInstance(STARTER_CARDS["strike_soyoi"])
        first = MaterialInstance(get_material("perler_color_pack"))
        second = MaterialInstance(get_material("button_battery"))

        first_result = attach_material(carrier, first)
        second_result = attach_material(carrier, second)

        self.assertIsNone(first_result.replaced)
        self.assertIs(second_result.replaced, first)
        self.assertEqual(carrier.materials, [second])
        self.assertFalse(second_result.counts_as_card_play)
        self.assertEqual(second_result.destination_zone, "exhaust")

    def test_three_slots_replace_left_to_right(self) -> None:
        carrier = CardInstance(STARTER_CARDS["defend_soyoi"])
        material_ids = ["perler_color_pack", "felt_scrap", "button_battery"]
        initial = [MaterialInstance(get_material(item)) for item in material_ids]
        for material in initial:
            attach_material(carrier, material, slot_count=3)

        fourth = MaterialInstance(get_material("badge_blank"))
        fifth = MaterialInstance(get_material("spray_can"))
        self.assertIs(attach_material(carrier, fourth, slot_count=3).replaced, initial[0])
        self.assertIs(attach_material(carrier, fifth, slot_count=3).replaced, initial[1])

    def test_material_effect_is_queued_after_carrier_play(self) -> None:
        carrier = CardInstance(STARTER_CARDS["strike_soyoi"])
        material = MaterialInstance(get_material("perler_color_pack"))
        attach_material(carrier, material)

        result = resolve_materials(
            carrier, MaterialTiming.AFTER_CARRIER_PLAYED, turn_number=1
        )

        self.assertEqual(result.effects[0].operation, "material_damage")
        self.assertEqual(result.effects[0].amount, 3)
        self.assertEqual(result.effects[0].hits, 2)

    def test_one_shot_material_is_removed_after_trigger(self) -> None:
        carrier = CardInstance(STARTER_CARDS["strike_soyoi"])
        material = MaterialInstance(get_material("full_perler_tray"))
        attach_material(carrier, material)

        result = resolve_materials(
            carrier, MaterialTiming.AFTER_CARRIER_PLAYED, turn_number=1
        )

        self.assertEqual(result.consumed_material_ids, (material.instance_id,))
        self.assertEqual(carrier.materials, [])


if __name__ == "__main__":
    unittest.main()
