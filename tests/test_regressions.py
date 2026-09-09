"""审查问题的回归测试：实例身份、状态机、素材生命周期和实际 UI 路径。"""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from soyoi_game.content.character import STRIKE_SPEC, DEFEND_SPEC, setup_soyoi_combat
from soyoi_game.content.materials import make_material
from soyoi_game.content.soyoi_cards import PLAYABLE_REWARD_CARDS
from soyoi_game.core.cards import CardKeyword, PileType, RewardEffectOperation as Op, RewardEffectSpec, TargetType
from soyoi_game.core.combat import CombatState
from soyoi_game.core.enemy import Enemy, Intent, IntentAction
from soyoi_game.core.player import Player
from soyoi_game.core.powers import Powers, compute_attack_damage
from soyoi_game.soyoi.card import get_loadout
from soyoi_game.soyoi.material_effect_resolver import MaterialEffectResolver
from soyoi_game.soyoi.material_runtime import attach, attach_next_available, store, get_materials, try_attach_from_box, try_merge_from_box
from soyoi_game.soyoi.materials import MaterialEffectOperation as MatOp, MaterialEffectTiming as Timing


def reward(title):
    return next(spec.create() for spec in PLAYABLE_REWARD_CARDS if spec.title == title)


class CombatRegressionTests(unittest.TestCase):
    def setUp(self):
        self.player = Player(name="玩家", max_hp=72, draw_per_turn=0)
        self.enemy = Enemy(name="木桩", max_hp=1000, intent=Intent(IntentAction.ATTACK, 0))
        self.combat = CombatState(player=self.player, enemies=[self.enemy],
                                  rng=random.Random(7), round_number=1, phase="player")
        self.player.energy = 99
        setup_soyoi_combat(self.combat)
        # 本组隔离随机遗物；默认遗物路径由 UI 回归测试覆盖。
        self.combat.on_player_turn_start.clear()

    def add(self, card, pile=PileType.HAND):
        self.player.piles.move(card, pile)
        return card

    def play(self, card):
        target = self.player if card.target == TargetType.SELF else self.enemy
        self.combat.play_card(card, target)

    def count(self, card):
        return sum(item is card for pile in self.player.piles.piles.values() for item in pile.cards)

    def attach_effect(self, card, operation, amount=1, *, timing=Timing.AFTER_CARRIER_PLAYED,
                      once=False, consumes=False):
        material = make_material("button_battery")
        effect = material.material_effects[0]
        effect.operation, effect.amount, effect.timing = operation, amount, timing
        effect.once_per_turn, effect.consumes_component = once, consumes
        attach_next_available(self.player, card, material.as_bundle())
        return material

    def test_equal_cards_are_distinct_and_move_by_identity(self):
        other = self.add(STRIKE_SPEC.create(), PileType.DRAW)
        played = self.add(STRIKE_SPEC.create())
        self.assertIsNot(other, played)
        self.play(played)
        self.assertTrue(self.player.piles.pile(PileType.DRAW).contains(other))
        self.assertFalse(self.player.piles.pile(PileType.HAND).contains(played))
        self.assertTrue(self.player.piles.pile(PileType.DISCARD).contains(played))
        self.assertEqual((self.count(other), self.count(played)), (1, 1))

    def test_equal_cards_exhaust_independently(self):
        cards = [STRIKE_SPEC.create(), STRIKE_SPEC.create()]
        for card in cards:
            card.base_keywords.append(CardKeyword.EXHAUST)
        self.add(cards[0], PileType.DRAW)
        self.add(cards[1])
        self.play(cards[1])
        self.assertTrue(self.player.piles.pile(PileType.DRAW).contains(cards[0]))
        self.assertTrue(self.player.piles.pile(PileType.EXHAUST).contains(cards[1]))
        self.assertEqual(self.count(cards[1]), 1)

    def test_move_same_card_twice_does_not_duplicate(self):
        card = self.add(STRIKE_SPEC.create())
        self.player.piles.move_to_discard(card)
        self.player.piles.move_to_discard(card)
        self.assertEqual(self.count(card), 1)

    def test_enemy_block_protects_next_player_turn_then_expires(self):
        self.enemy.intent = Intent(IntentAction.DEFEND, 6)
        self.combat.end_player_turn()
        self.assertEqual(self.enemy.block, 6)
        self.play(self.add(STRIKE_SPEC.create()))
        self.assertEqual((self.enemy.hp, self.enemy.block), (1000, 0))
        self.enemy.block = 3
        self.enemy.intent = Intent(IntentAction.ATTACK, 0)
        self.combat.end_player_turn()
        self.assertEqual(self.enemy.block, 0)

    def test_enemy_intents_advance_without_ui(self):
        self.enemy.act_pattern = [Intent(IntentAction.ATTACK, 1), Intent(IntentAction.DEFEND, 6)]
        self.combat.next_enemy_intents()
        self.combat.end_player_turn()
        self.assertEqual(self.enemy.intent.action, IntentAction.DEFEND)
        self.combat.end_player_turn()
        self.assertEqual(self.enemy.block, 6)
        self.assertEqual(self.enemy.intent.action, IntentAction.ATTACK)

    def test_bag_retains_immediately_and_across_multiple_turns(self):
        card = self.add(STRIKE_SPEC.create())
        attach_next_available(self.player, card, make_material("self_sealing_bag").as_bundle())
        self.assertTrue(card.material_retain)
        for _ in range(4):
            self.combat.end_player_turn()
            self.assertTrue(self.player.piles.pile(PileType.HAND).contains(card))
            self.assertEqual(self.count(card), 1)

    def test_bag_card_still_retains_after_redraw(self):
        card = self.add(reward("自封袋收纳"))
        self.play(card)
        self.player.draw_per_turn = 1
        self.combat.end_player_turn()
        self.player.draw_per_turn = 0
        for _ in range(4):
            self.combat.end_player_turn()
            self.assertTrue(self.player.piles.pile(PileType.HAND).contains(card))

    def test_replacing_bag_removes_only_material_retain(self):
        card = self.add(STRIKE_SPEC.create())
        attach(self.player, card, 0, make_material("self_sealing_bag").as_bundle())
        card.retained_this_turn = True
        attach(self.player, card, 0, make_material("button_battery").as_bundle())
        self.assertFalse(card.material_retain)
        self.combat.discard_hand()
        self.assertTrue(self.player.piles.pile(PileType.HAND).contains(card))
        card.reset_per_turn()
        self.combat.discard_hand()
        self.assertTrue(self.player.piles.pile(PileType.DISCARD).contains(card))

    def test_material_cost_is_immediate_persistent_and_removed_on_replace(self):
        card = self.add(STRIKE_SPEC.create(), PileType.DISCARD)
        self.attach_effect(card, MatOp.INCREASE_CARRIER_COST, 2, timing=Timing.PERSISTENT)
        self.assertEqual(card.cost, 3)
        card.cost_modifiers["temporary"] = -1
        self.combat.begin_player_turn()
        self.assertEqual(card.cost, 3)
        self.assertEqual(card.cost_modifiers, {})
        attach(self.player, card, 0, make_material("button_battery").as_bundle())
        self.assertEqual(card.cost, 1)

    def test_terminal_phases_reject_play_without_spending(self):
        card = self.add(STRIKE_SPEC.create())
        for phase in ("setup", "enemy", "resolving", "victory", "defeat", "error"):
            self.combat.phase = phase
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                self.play(card)
            self.assertEqual(self.player.energy, 99)
            self.assertTrue(self.player.piles.pile(PileType.HAND).contains(card))
            self.assertEqual(self.combat.phase, phase)

    def test_nonhand_card_and_invalid_targets_rejected(self):
        card = STRIKE_SPEC.create()
        with self.assertRaises(ValueError):
            self.play(card)
        self.add(card)
        outsider = Enemy(name="不属于此战斗", max_hp=20)
        dead = Enemy(name="已死", max_hp=20)
        dead.hp = 0
        self.combat.enemies.append(dead)
        for target in (self.player, outsider, dead):
            with self.assertRaises(ValueError):
                self.combat.play_card(card, target)
        skill = self.add(DEFEND_SPEC.create())
        with self.assertRaises(ValueError):
            self.combat.play_card(skill, self.enemy)
        self.assertEqual(self.player.energy, 99)

    def test_unplayable_and_insufficient_energy_are_atomic(self):
        card = self.add(STRIKE_SPEC.create())
        self.player.energy = 0
        with self.assertRaises(ValueError):
            self.play(card)
        card.base_cost = 0
        card.base_keywords.append(CardKeyword.UNPLAYABLE)
        with self.assertRaises(ValueError):
            self.play(card)
        self.assertEqual(self.count(card), 1)
        self.assertTrue(self.player.piles.pile(PileType.HAND).contains(card))

    def test_hp_loss_defeats_immediately_and_cannot_heal(self):
        self.player.hp = 1
        card = self.add(reward("深夜清单"))
        filler = self.add(STRIKE_SPEC.create(), PileType.DRAW)
        self.play(card)
        self.assertEqual((self.player.hp, self.combat.phase), (0, "defeat"))
        self.assertTrue(self.player.piles.pile(PileType.DRAW).contains(filler))
        with self.assertRaises(ValueError):
            self.play(self.add(reward("大休息")))
        self.assertEqual(self.player.hp, 0)

    def test_lethal_effect_stops_later_healing_in_same_card(self):
        card = self.add(DEFEND_SPEC.create())
        card.base_effects = [RewardEffectSpec(Op.LOSE_HP, 100), RewardEffectSpec(Op.HEAL, 20)]
        self.play(card)
        self.assertEqual((self.player.hp, self.combat.phase), (0, "defeat"))

    def test_killing_last_enemy_sets_victory_in_core(self):
        self.enemy.hp = 1
        self.play(self.add(STRIKE_SPEC.create()))
        self.assertEqual(self.combat.phase, "victory")
        old_round = self.combat.round_number
        self.combat.end_player_turn()
        self.assertEqual(self.combat.round_number, old_round)

    def test_vigor_applies_to_one_multihit_attack_and_its_material(self):
        self.play(self.add(reward("摊位展示")))
        card = self.add(reward("连续打磨"))
        attach_next_available(self.player, card, make_material("perler_color_pack").as_bundle())
        old_hp = self.enemy.hp
        self.play(card)
        self.assertEqual(old_hp - self.enemy.hp, 7 + 7 + 6)
        self.assertEqual(self.player.get_power_amount(Powers.VIGOR), 0)
        old_hp = self.enemy.hp
        self.play(self.add(STRIKE_SPEC.create()))
        self.assertEqual(old_hp - self.enemy.hp, 6)

    def test_vigor_survives_turn_and_skill_play(self):
        self.player.add_power(Powers.VIGOR, 3)
        self.play(self.add(DEFEND_SPEC.create()))
        self.combat.end_player_turn()
        self.assertEqual(self.player.get_power_amount(Powers.VIGOR), 3)

    def test_thorns_reflects_once_even_when_both_have_thorns(self):
        self.player.add_power(Powers.THORNS, 2)
        self.enemy.add_power(Powers.THORNS, 3)
        self.player.block = 10
        self.enemy.intent = Intent(IntentAction.ATTACK, 7)
        self.combat.execute_enemy_intent(self.enemy)
        self.assertEqual((self.player.hp, self.player.block, self.enemy.hp), (72, 3, 998))

    def test_thorns_kills_attacker_and_stops_remaining_hits(self):
        self.enemy.hp = 1
        self.player.add_power(Powers.THORNS, 1)
        self.enemy.intent = Intent(IntentAction.ATTACK, 7, hits=3)
        self.combat.end_player_turn()
        self.assertEqual((self.player.hp, self.enemy.hp, self.combat.phase), (65, 0, "victory"))

    def test_player_dies_to_thorns_mid_multihit_attack(self):
        self.player.hp = 1
        self.enemy.add_power(Powers.THORNS, 1)
        self.play(self.add(reward("连续打磨")))
        self.assertEqual((self.player.hp, self.enemy.hp, self.combat.phase), (0, 996, "defeat"))

    def test_simultaneous_death_is_defeat(self):
        self.player.hp = 1
        self.enemy.hp = 1
        self.enemy.add_power(Powers.THORNS, 1)
        self.play(self.add(STRIKE_SPEC.create()))
        self.assertEqual(self.combat.phase, "defeat")

    def test_full_hand_draw_frees_one_slot(self):
        card = self.add(reward("桌面清点"))
        for _ in range(9):
            self.add(DEFEND_SPEC.create())
        for _ in range(3):
            self.add(STRIKE_SPEC.create(), PileType.DRAW)
        self.play(card)
        self.assertEqual(len(self.player.piles.pile(PileType.HAND).cards), 10)
        self.assertEqual(len(self.player.piles.pile(PileType.DRAW).cards), 2)
        self.assertTrue(self.player.piles.pile(PileType.DISCARD).contains(card))

    def test_resolving_card_cannot_draw_itself(self):
        card = self.add(reward("桌面清点"))
        self.attach_effect(card, MatOp.DRAW_CARDS)
        self.play(card)
        self.assertEqual(len(self.player.piles.pile(PileType.HAND).cards), 0)
        self.assertEqual(self.count(card), 1)

    def test_offensive_materials_on_skills_still_target_player(self):
        for material_id, power in (("perler_color_pack", None), ("badge_blank", Powers.VULNERABLE),
                                   ("liquid_glue", Powers.WEAK)):
            with self.subTest(material=material_id):
                self.player.hp = 72
                self.player.powers.clear()
                card = self.add(reward("桌面清点"))
                attach_next_available(self.player, card, make_material(material_id).as_bundle())
                self.play(card)
                self.assertEqual(self.enemy.hp, 1000)
                self.assertEqual(self.enemy.powers, {})
                if power:
                    self.assertEqual(self.player.get_power_amount(power), 1)
                else:
                    self.assertEqual(self.player.hp, 69)

    def test_once_per_turn_resets_and_independent_components_trigger(self):
        card = self.add(STRIKE_SPEC.create())
        self.attach_effect(card, MatOp.GAIN_ENERGY, once=True)
        self.attach_effect(card, MatOp.GAIN_ENERGY, once=True)
        resolver = MaterialEffectResolver(self.combat)
        resolver.resolve_after_carrier_played(card, self.enemy)
        resolver.resolve_after_carrier_played(card, self.enemy)
        self.assertEqual(self.player.energy, 101)
        self.combat.round_number += 1
        resolver.resolve_after_carrier_played(card, self.enemy)
        self.assertEqual(self.player.energy, 103)

    def test_first_per_combat_is_independent_of_once_per_turn(self):
        for once in (False, True):
            with self.subTest(once=once):
                card = self.add(STRIKE_SPEC.create())
                self.attach_effect(card, MatOp.GAIN_ENERGY, timing=Timing.FIRST_CARRIER_PLAY_EACH_COMBAT, once=once)
                resolver = MaterialEffectResolver(self.combat)
                energy = self.player.energy
                resolver.resolve_after_carrier_played(card, self.enemy)
                resolver.resolve_after_carrier_played(card, self.enemy)
                self.combat.round_number += 1
                resolver.resolve_after_carrier_played(card, self.enemy)
                self.assertEqual(self.player.energy, energy + 1)

    def test_return_to_hand_after_effect_and_one_shot_consumption(self):
        card = self.add(STRIKE_SPEC.create())
        self.attach_effect(card, MatOp.RETURN_CARRIER_TO_HAND, consumes=True)
        self.play(card)
        self.assertTrue(self.player.piles.pile(PileType.HAND).contains(card))
        self.assertEqual(get_loadout(card).material_count, 0)
        self.assertEqual(self.count(card), 1)
        self.play(card)
        self.assertTrue(self.player.piles.pile(PileType.DISCARD).contains(card))

    def test_exhaust_overrides_return_and_full_hand_returns_to_discard(self):
        card = self.add(STRIKE_SPEC.create())
        card.base_keywords.append(CardKeyword.EXHAUST)
        self.attach_effect(card, MatOp.RETURN_CARRIER_TO_HAND)
        self.play(card)
        self.assertTrue(self.player.piles.pile(PileType.EXHAUST).contains(card))
        card = self.add(reward("桌面清点"))
        self.attach_effect(card, MatOp.RETURN_CARRIER_TO_HAND)
        for _ in range(9):
            self.add(DEFEND_SPEC.create())
        self.add(STRIKE_SPEC.create(), PileType.DRAW)
        self.play(card)
        self.assertEqual(len(self.player.piles.pile(PileType.HAND).cards), 10)
        self.assertTrue(self.player.piles.pile(PileType.DISCARD).contains(card))
        self.assertEqual(self.count(card), 1)

    def test_discard_to_draw_top_is_next_drawn(self):
        card = self.add(STRIKE_SPEC.create())
        self.attach_effect(card, MatOp.PUT_OTHER_NON_MATERIAL_FROM_DISCARD_ON_DRAW_PILE)
        wanted = self.add(DEFEND_SPEC.create(), PileType.DISCARD)
        self.add(reward("桌面清点"), PileType.DRAW)
        self.play(card)
        self.assertIs(self.player.piles.draw(1)[0], wanted)

    def test_negative_temporary_strength_works_and_expires(self):
        card = self.add(STRIKE_SPEC.create())
        card.base_effects = [RewardEffectSpec(Op.LOWER_ENEMY_STRENGTH_THIS_TURN, 3)]
        self.play(card)
        self.assertEqual(self.enemy.get_power_amount(Powers.TEMP_STRENGTH), -3)
        self.assertEqual(compute_attack_damage(7, self.enemy, self.player), 4)
        self.enemy.end_turn_tick()
        self.assertEqual(self.enemy.get_power_amount(Powers.TEMP_STRENGTH), 0)

    def test_two_wounds_remain_two_unplayable_instances(self):
        card = self.add(STRIKE_SPEC.create())
        self.attach_effect(card, MatOp.ADD_WOUND_TO_DISCARD, 2)
        self.play(card)
        wounds = [item for item in self.player.piles.pile(PileType.DISCARD).cards if item.card_id == "wound"]
        self.assertEqual(len(wounds), 2)
        self.assertIsNot(wounds[0], wounds[1])
        wounds[0].upgrade()
        self.assertIn(CardKeyword.UNPLAYABLE, wounds[0].keywords)

    def test_equal_materials_store_and_merge_as_distinct_instances(self):
        a, b = make_material("button_battery"), make_material("button_battery")
        left, right = store(self.player, a), store(self.player, b)
        self.assertIs(store(self.player, a), left)
        self.assertEqual(len(get_materials(self.player)), 2)
        self.assertEqual(len(self.player.piles.pile(PileType.HAND).cards), 2)
        merged = try_merge_from_box(self.player, left, right)
        self.assertIsNotNone(merged)
        self.assertEqual(merged.components, [a, b])
        self.assertEqual(get_materials(self.player), [merged])
        carrier = self.add(STRIKE_SPEC.create())
        try_attach_from_box(self.player, merged, carrier, 0)
        self.assertEqual(get_materials(self.player), [])
        self.assertTrue(self.player.piles.pile(PileType.EXHAUST).contains(a))
        self.assertTrue(self.player.piles.pile(PileType.EXHAUST).contains(b))

    def test_invalid_attachment_does_not_consume_box(self):
        bundle = store(self.player, make_material("button_battery"))
        card = self.add(STRIKE_SPEC.create())
        with self.assertRaises(IndexError):
            try_attach_from_box(self.player, bundle, card, 99)
        self.assertEqual(get_materials(self.player), [bundle])

    def test_seeded_multi_combat_preserves_piles_and_terminal_states(self):
        """100 局随机合法操作，覆盖升级牌、多次洗牌与胜负收尾。"""
        from soyoi_game.content.character import build_character
        outcomes = set()
        total_actions = 0
        for seed in range(100):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                specs = build_character().starting_deck + list(PLAYABLE_REWARD_CARDS)
                cards = [spec.create() for spec in specs]
                for card in cards:
                    if rng.random() < 0.5:
                        card.upgrade()
                p = Player(name="测试", max_hp=72, deck=cards)
                p.piles.rng.seed(seed)
                e = Enemy(name="测试敌人", max_hp=100 + seed % 3 * 60,
                          act_pattern=[Intent(IntentAction.ATTACK, 8),
                                       Intent(IntentAction.DEFEND, 12),
                                       Intent(IntentAction.ATTACK, 5, hits=3)])
                combat = CombatState(player=p, enemies=[e], rng=rng)
                setup_soyoi_combat(combat)
                combat.start_combat()
                expected_ids = {id(card) for card in cards}
                for step in range(400):
                    all_cards = [card for pile in p.piles.piles.values() for card in pile.cards]
                    self.assertEqual({id(card) for card in all_cards}, expected_ids)
                    self.assertEqual(len(all_cards), len(expected_ids))
                    self.assertLessEqual(len(p.piles.pile(PileType.HAND).cards), p.hand_limit)
                    self.assertGreaterEqual(p.hp, 0)
                    self.assertLessEqual(p.hp, p.max_hp)
                    self.assertGreaterEqual(p.energy, 0)
                    self.assertGreaterEqual(e.hp, 0)
                    if combat.phase in ("victory", "defeat"):
                        outcomes.add(combat.phase)
                        break
                    self.assertEqual(combat.phase, "player")
                    playable = [card for card in p.piles.pile(PileType.HAND).cards
                                if card.cost <= p.energy and CardKeyword.UNPLAYABLE not in card.keywords]
                    if not playable or rng.random() < 0.25:
                        combat.end_player_turn()
                    else:
                        card = rng.choice(playable)
                        combat.play_card(card, p if card.target == TargetType.SELF else e)
                    total_actions += 1
                else:
                    self.fail(f"seed={seed}: 战斗在400次操作后仍未结束")
                before = (p.hp, e.hp, p.energy, combat.round_number, combat.phase)
                combat.end_player_turn()
                with self.assertRaises(ValueError):
                    combat.play_card(cards[0])
                self.assertEqual((p.hp, e.hp, p.energy, combat.round_number, combat.phase), before)
        self.assertEqual(outcomes, {"victory", "defeat"})
        self.assertGreater(total_actions, 1000)

    def test_material_generation_at_full_hand_goes_to_discard(self):
        for _ in range(10):
            self.add(STRIKE_SPEC.create())
        token = make_material("button_battery")
        store(self.player, token)
        store(self.player, token)
        self.assertEqual(len(self.player.piles.pile(PileType.HAND).cards), 10)
        self.assertTrue(self.player.piles.pile(PileType.DISCARD).contains(token))
        self.assertEqual(self.count(token), 1)
        self.assertEqual(len(get_materials(self.player)), 1)

    def test_negative_strength_material_and_self_attack_thorns(self):
        card = self.add(STRIKE_SPEC.create())
        material = self.attach_effect(card, MatOp.LOSE_STRENGTH_THIS_TURN, 3)
        from soyoi_game.soyoi.materials import MaterialEffectTarget
        material.material_effects[0].target = MaterialEffectTarget.INHERITED
        self.play(card)
        self.assertEqual(self.enemy.get_power_amount(Powers.TEMP_STRENGTH), -3)
        self.player.add_power(Powers.THORNS, 8)
        self.player.take_attack(3, self.player)
        self.assertEqual(self.player.hp, 69)

    def test_poison_bypasses_block_without_reflection(self):
        self.player.block = 10
        self.player.add_power(Powers.THORNS, 2)
        self.player.add_power(Powers.POISON, 3)
        self.player.end_turn_tick()
        self.assertEqual((self.player.hp, self.player.block), (69, 10))


class UIRegressionTests(unittest.TestCase):
    def setUp(self):
        import pygame
        from soyoi_game.ui.pygame_demo import PygameCombatDemo
        self.pygame = pygame
        self.demo = PygameCombatDemo()

    def tearDown(self):
        self.pygame.display.quit()

    def test_default_second_round_defend_preserves_all_instances(self):
        demo = self.demo
        demo.draw()
        before = {id(card) for pile in demo.combat.player.piles.piles.values() for card in pile.cards}
        demo.end_turn()
        demo.draw()
        card = next(c for c in demo.combat.player.piles.pile(PileType.HAND).cards if c.card_id == "defend_soyoi")
        demo.select_or_play(card)
        after = [id(c) for pile in demo.combat.player.piles.piles.values() for c in pile.cards]
        self.assertEqual(set(after), before)
        self.assertEqual(len(after), len(set(after)))
        self.assertFalse(demo.combat.player.piles.pile(PileType.HAND).contains(card))

    def test_defeat_and_victory_shortcut_cannot_resume(self):
        for phase in ("defeat", "victory"):
            self.demo.reset_combat()
            card = next(c for c in self.demo.combat.player.piles.pile(PileType.HAND).cards if c.target == TargetType.SELF)
            self.demo.combat.phase = phase
            energy = self.demo.combat.player.energy
            self.demo.select_or_play(card)  # 数字键调用此公共入口
            self.assertEqual(self.demo.combat.phase, phase)
            self.assertEqual(self.demo.combat.player.energy, energy)
            self.assertTrue(self.demo.combat.player.piles.pile(PileType.HAND).contains(card))

    def test_material_token_renders_without_loadout_or_play(self):
        token = make_material("button_battery")
        store(self.demo.combat.player, token)
        self.demo.draw()
        energy = self.demo.combat.player.energy
        self.demo.select_or_play(token)
        self.assertEqual(self.demo.combat.player.energy, energy)
        self.assertTrue(self.demo.combat.player.piles.pile(PileType.HAND).contains(token))


if __name__ == "__main__":
    unittest.main()
