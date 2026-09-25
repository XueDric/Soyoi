"""战斗层：结算与素材、敌人与脚本敌人、战斗端界面，以及关键回归。"""

from __future__ import annotations
from pathlib import Path
from soyoi_game import card_creator as cc
from soyoi_game.content import enemy_scripts
from soyoi_game.content.character import (
    ASK_AROUND_SPEC,
    DEFEND_SPEC,
    RUSH_JOB_SPEC,
    STRIKE_SPEC,
    TOUCH_UP_SPEC,
    build_character,
    setup_soyoi_combat,
)
from soyoi_game.content.character import ASK_AROUND_SPEC
from soyoi_game.content.character import STRIKE_SPEC, DEFEND_SPEC, setup_soyoi_combat
from soyoi_game.content.enemies import (
    BOSS_ENEMY_IDS,
    BUILTIN_ENEMIES,
    ENEMY_TYPES,
    NORMAL_ENEMY_IDS,
    WOUND_SPEC,
    Cultist,
    JawWorm,
    Looter,
    ScrapColossus,
    Sentry,
    enemy_choices,
    enemy_list,
    make_enemy,
    make_enemy_by_name,
    make_wound,
    random_enemy,
)
from soyoi_game.content.enemies import ENEMY_TYPES, make_enemy_by_name
from soyoi_game.content.materials import make_material
from soyoi_game.content.soyoi_cards import (
    COMMON_CARDS,
    PLAYABLE_REWARD_CARDS,
    RARE_CARDS,
    UNCOMMON_CARDS,
)
from soyoi_game.content.soyoi_cards import PLAYABLE_REWARD_CARDS
from soyoi_game.core.cards import CardKeyword, PileType, RewardEffectOperation as Op, RewardEffectSpec, TargetType
from soyoi_game.core.cards import PileType
from soyoi_game.core.cards import PileType, TargetType
from soyoi_game.core.combat import CombatState
from soyoi_game.core.enemy import Enemy, Intent, IntentAction
from soyoi_game.core.enemy import IntentAction
from soyoi_game.core.player import Player
from soyoi_game.core.powers import Powers, compute_attack_damage
from soyoi_game.pygame_ui import HEIGHT, WIDTH, PygameCombatDemo
from soyoi_game.soyoi.card import get_loadout
from soyoi_game.soyoi.material_effect_resolver import MaterialEffectResolver
from soyoi_game.soyoi.material_runtime import (
    attach,
    attach_next_available,
    equip_from_hand,
    get_materials,
    store,
    try_attach_from_box,
    try_merge_from_box,
)
from soyoi_game.soyoi.materials import MaterialEffectOperation as MatOp, MaterialEffectTiming as Timing
import os
import pygame
import random
import shutil
import unittest
import uuid


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

    def test_material_card_puts_a_material_card_into_hand(self):
        card = COMMON_CARDS[0].create()
        combat, enemy = self.make_combat(card)

        combat.play_card(card, enemy)

        self.assertEqual(enemy.hp, enemy.max_hp - 7)
        # 打出的牌身上不再自动挂素材，素材变成一张手牌等玩家自己安排
        self.assertEqual(get_loadout(card).material_count, 0)
        hand = combat.player.piles.pile(PileType.HAND).cards
        self.assertEqual([item.title for item in hand if getattr(item, "is_material", False)], ["拼豆色包"])
        # 素材还没装上去，所以"本回合打出素材"的计数不该动
        self.assertEqual(combat.materials_played_this_round, 0)

    def test_player_equips_the_material_onto_a_chosen_card(self):
        from soyoi_game.soyoi.material_runtime import equip_from_hand

        card = COMMON_CARDS[0].create()
        carrier = COMMON_CARDS[1].create()
        combat, enemy = self.make_combat(card)
        combat.player.piles.pile(PileType.HAND).add(carrier)
        combat.play_card(card, enemy)
        material = next(
            item for item in combat.player.piles.pile(PileType.HAND).cards
            if getattr(item, "is_material", False)
        )

        equipped, _note = equip_from_hand(combat.player, material, carrier, combat=combat)

        self.assertTrue(equipped)
        self.assertEqual(get_loadout(carrier).material_count, 1)
        self.assertEqual(combat.materials_played_this_round, 1)
        self.assertTrue(combat.player.piles.pile(PileType.EXHAUST).contains(material))
        # 装上之后才轮到素材效果结算：8 点本体 + 3 点素材
        old_hp = enemy.hp
        combat.play_card(carrier, enemy)
        self.assertEqual(old_hp - enemy.hp, 11)

    def test_starting_relic_hands_out_a_material_card_each_turn(self):
        card = COMMON_CARDS[1].create()
        player = Player(name="所依", max_hp=72, deck=[card], draw_per_turn=1)
        combat = CombatState(
            player=player,
            enemies=[Enemy(name="测试木桩", max_hp=100)],
            rng=random.Random(3),
        )
        setup_soyoi_combat(combat)

        combat.start_combat()

        hand = player.piles.pile(PileType.HAND).cards
        self.assertEqual(len([item for item in hand if getattr(item, "is_material", False)]), 1)
        # 遗物只发素材牌，装到哪张牌上由玩家决定
        self.assertEqual(get_loadout(card).material_count, 0)
        self.assertEqual(combat.materials_played_this_round, 0)

if __name__ == "__main__":
    unittest.main()


class RosterTests(unittest.TestCase):
    """敌人表：五只内置 + 能按编号/中文名/随机造出来。"""

    def test_five_builtin_enemies_are_registered(self):
        self.assertEqual(len(BUILTIN_ENEMIES), 5)
        self.assertEqual(len(NORMAL_ENEMY_IDS), 4)   # 四只普通怪
        self.assertEqual(len(BOSS_ENEMY_IDS), 1)     # 一个 Boss

    def test_make_enemy_by_id_and_chinese_name(self):
        self.assertIsInstance(make_enemy("jaw_worm"), JawWorm)
        self.assertIsInstance(make_enemy("邪教徒"), Cultist)
        self.assertIsInstance(make_enemy_by_name("scrap_colossus"), ScrapColossus)

    def test_bad_id_lists_the_options(self):
        with self.assertRaises(ValueError) as ctx:
            make_enemy("dragon")

        self.assertIn("jaw_worm", str(ctx.exception))

class IntentPatternTests(unittest.TestCase):
    """每只怪的套路（意图只有攻击 / 防御 / 强化三种）。"""

    def _intents(self, enemy, turns: int) -> list[str]:
        """模拟回合推进，收集前几回合的意图文本。"""
        return [enemy._choose(enemy, None).text for _ in range(turns)]

    def test_jaw_worm_cycles_three_actions(self):
        texts = self._intents(JawWorm(), 6)

        self.assertEqual(texts[0], "啃咬 11")
        self.assertIn("硬化", texts[1])
        self.assertEqual(texts[3], "啃咬 11")     # 第 4 回合回到起点

    def test_cultist_buffs_first_then_keeps_attacking(self):
        cultist = Cultist()
        first = cultist._choose(cultist, None)

        self.assertEqual(first.action, IntentAction.BUFF)
        self.assertEqual(first.amount, 3)
        self.assertEqual(cultist._choose(cultist, None).action, IntentAction.ATTACK)

    def test_attack_can_carry_an_effect_or_a_junk_card(self):
        looter_intents = []
        looter = Looter()
        for _ in range(4):
            looter_intents.append(looter._choose(looter, None))

        self.assertTrue(any(intent.effect_operation is not None for intent in looter_intents))

class BossTests(unittest.TestCase):
    """Boss 的两个阶段与"塞废牌"（挂在攻击上的附加效果，不是新意图）。"""

    def test_boss_switches_phase_below_half_hp(self):
        boss = ScrapColossus()
        boss._choose(boss, None)

        self.assertEqual(boss.phase, 1)

        boss.hp = boss.max_hp // 2
        boss._choose(boss, None)

        self.assertEqual(boss.phase, 2)

    def test_junk_card_lands_in_the_discard_pile(self):
        combat = cc.build_combat(enemy="scrap_colossus")
        combat.start_combat()
        boss = combat.enemies[0]
        boss.hp = boss.max_hp // 2  # 进入二阶段
        boss.turn = 0               # 从二阶段第一招开始数

        while True:  # 找到"灌铁屑"那一回合
            intent = boss._choose(boss, combat)
            if intent.card_spec is not None:
                boss.set_intent(intent)
                break

        combat.execute_enemy_intent(boss)

        discard = combat.player.piles.pile(PileType.DISCARD).cards
        wounds = [card for card in discard if card.card_id == "wound_scrap"]
        self.assertEqual(len(wounds), intent.hits)
        self.assertTrue(all(not card.current_effects() for card in wounds))  # 废牌没有效果

class SelectionTests(unittest.TestCase):
    """战斗模拟器里换敌人的入口。"""

    def test_build_combat_can_pick_each_enemy(self):
        for enemy_id, (title, _cls) in ENEMY_TYPES.items():
            combat = cc.build_combat(enemy=enemy_id)
            combat.start_combat()
            with self.subTest(enemy=enemy_id):
                self.assertEqual(combat.enemies[0].name, title)
                self.assertNotEqual(combat.enemies[0].intent.action, IntentAction.UNKNOWN)

if __name__ == "__main__":
    unittest.main()


TMP_ROOT = Path(__file__).resolve().parent / ".tmp"

GOOD_SCRIPT = """\
# 测试用脚本：三段循环
name = 测试怪
hp = 33
flavor = 我是脚本造出来的。
appearance = robot / 100,110,120 / 218,91,75

attack 9
defend 6
buff 2
"""


class ParseTests(unittest.TestCase):
    """把脚本文字解析成敌人定义。"""

    def test_full_script_parses(self):
        script = enemy_scripts.parse_script(GOOD_SCRIPT, Path("测试怪.txt"))

        self.assertEqual(script.name, "测试怪")
        self.assertEqual(script.hp, 33)
        self.assertEqual(script.flavor, "我是脚本造出来的。")
        self.assertEqual(script.appearance["shape"], "robot")
        self.assertEqual(len(script.actions), 3)
        self.assertEqual(script.actions[0].action, IntentAction.ATTACK)
        self.assertEqual(script.actions[1].amount, 6)
        self.assertEqual(script.actions[2].action, IntentAction.BUFF)

    def test_unknown_action_is_reported_with_line_number(self):
        with self.assertRaises(enemy_scripts.ScriptError) as ctx:
            enemy_scripts.parse_script("name = 怪\nhp = 10\nattack 5\nfireball 9\n")

        message = str(ctx.exception)
        self.assertIn("第 4 行", message)
        self.assertIn("fireball", message)

    def test_bad_numbers_are_reported(self):
        with self.assertRaises(enemy_scripts.ScriptError):
            enemy_scripts.parse_script("name = 怪\nhp = 很多\nattack 5\n")
        with self.assertRaises(enemy_scripts.ScriptError):
            enemy_scripts.parse_script("name = 怪\nattack 0\n")   # 伤害必须是正数
        with self.assertRaises(enemy_scripts.ScriptError):
            enemy_scripts.parse_script("name = 怪\n")             # 一个动作都没有

class LoadTests(unittest.TestCase):
    """从目录加载脚本，并且脚本敌人能真的进游戏。"""

    def setUp(self):
        self.directory = TMP_ROOT / f"scripts-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.enemy_id = f"script_enemy_{uuid.uuid4().hex[:6]}"

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        ENEMY_TYPES.pop(self.enemy_id, None)

    def _write(self, name: str, text: str) -> Path:
        path = self.directory / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_load_directory_registers_enemies(self):
        script_text = GOOD_SCRIPT.replace("name = 测试怪", f"id = {self.enemy_id}\nname = 测试怪")
        self._write("good.txt", script_text)

        report = enemy_scripts.load_scripts(self.directory)

        self.assertTrue(report.ok, report.errors)
        self.assertEqual(len(report.loaded), 1)
        self.assertIn(self.enemy_id, ENEMY_TYPES)

        enemy = make_enemy_by_name(self.enemy_id)
        self.assertEqual(enemy.name, "测试怪")
        self.assertEqual(enemy.hp, 33)
        self.assertEqual(enemy.intent.action, IntentAction.UNKNOWN)  # 开战前还没决定

    def test_a_script_enemy_can_be_fought(self):
        script_text = GOOD_SCRIPT.replace("name = 测试怪", f"id = {self.enemy_id}\nname = 测试怪")
        self._write("good.txt", script_text)
        enemy_scripts.load_scripts(self.directory)

        combat = cc.build_combat(enemy=self.enemy_id)
        combat.start_combat()

        enemy = combat.enemies[0]
        self.assertEqual(enemy.name, "测试怪")
        self.assertEqual(enemy.hp, 33)
        self.assertEqual(enemy.intent.action, IntentAction.ATTACK)   # 脚本第一行是 attack 9
        self.assertEqual(enemy.appearance["shape"], "robot")         # 外观也来自脚本




if __name__ == "__main__":
    unittest.main()


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")




def is_material(card) -> bool:
    return getattr(card, "is_material", False)


class PygameDemoTests(unittest.TestCase):
    def setUp(self):
        # 关掉玩家自制卡，确保断言的是「默认起始牌组」的行为，与创作端是否已保存卡无关。
        self.demo = PygameCombatDemo(use_user_cards=False)

    def tearDown(self):
        pygame.display.quit()

    def test_no_user_cards_falls_back_to_the_character_starting_deck(self):
        """回归：关掉自制卡时（--no-user-cards）要跑角色原本的起始牌组。"""
        self.assertEqual(self.demo.deck_name, "所依的起始牌组")
        self.assertEqual(len(self.demo.combat.player.deck), 10)
        self.assertEqual(self.demo.user_card_titles, [])

    def test_first_frame_is_rendered(self):
        self.demo.draw()

        self.assertEqual(self.demo.canvas.get_size(), (WIDTH, HEIGHT))
        self.assertNotEqual(self.demo.canvas.get_at((20, 20)), self.demo.canvas.get_at((640, 360)))
        hand = self.demo.combat.player.piles.pile(PileType.HAND).cards
        # 5 张起始手牌 + 遗物发的 1 张素材牌
        self.assertEqual(len(hand), 6)
        self.assertEqual(len([card for card in hand if getattr(card, "is_material", False)]), 1)

    def test_attack_selects_target_then_deals_damage(self):
        hand = self.demo.combat.player.piles.pile(PileType.HAND).cards
        card = next(card for card in hand if card.target == TargetType.ANY_ENEMY)
        old_hp = self.demo.enemy.hp

        self.demo.select_or_play(card)
        self.assertIs(self.demo.selected_card, card)
        self.demo.handle_click(self.demo.enemy_rect.center)

        self.assertLess(self.demo.enemy.hp, old_hp)
        self.assertIsNone(self.demo.selected_card)

    def test_end_turn_advances_round(self):
        old_round = self.demo.combat.round_number

        self.demo.end_turn()

        self.assertEqual(self.demo.combat.round_number, old_round + 1)
        self.assertEqual(self.demo.combat.phase, "player")

    def test_equipping_a_material_takes_two_clicks(self):
        """点素材牌 -> 点一张手牌，素材就装到那张牌上。"""
        hand = self.demo.combat.player.piles.pile(PileType.HAND).cards
        material = next(card for card in hand if is_material(card))
        carrier = next(card for card in hand if not is_material(card))
        self.demo.draw()
        card_rects = self.demo.card_rects

        material_rect = next(rect for card, rect in card_rects if card is material)
        carrier_rect = next(rect for card, rect in card_rects if card is carrier)
        self.demo.handle_click(material_rect.center)
        self.assertIs(self.demo.pending_material, material)
        self.assertIn("加工上去", self.demo.message)

        self.demo.handle_click(carrier_rect.center)

        self.assertIsNone(self.demo.pending_material)
        self.assertEqual(get_loadout(carrier).material_count, 1)
        self.assertTrue(self.demo.combat.player.piles.pile(PileType.EXHAUST).contains(material))

    def test_picking_a_row_switches_to_that_enemy(self):
        """点浮层里的一行：换到那只对手，牌组不变，直接开新局。"""
        deck_size = len(self.demo.combat.player.deck)
        self.demo.toggle_enemy_picker()
        row = next(rect for enemy_id, rect in self.demo.layout_enemy_rows() if enemy_id == "sentry")

        self.demo.handle_click(row.center)

        self.assertEqual(self.demo.enemy.enemy_id, "sentry")
        self.assertFalse(self.demo.enemy_picker_open)
        self.assertEqual(len(self.demo.combat.player.deck), deck_size)   # 只换对手，不换牌组
        self.assertEqual(self.demo.combat.phase, "player")
        self.assertIn("换对手", self.demo.feedback)

    def test_user_card_shows_its_own_card_art(self):
        """玩家自己设的卡面图，战斗端要优先用；没设的牌还是原来的占位/系统卡面。"""
        import shutil
        import struct
        import uuid
        import zlib
        from pathlib import Path

        from soyoi_game import card_creator as cc

        tmp = Path(__file__).resolve().parent / ".tmp"
        cards = tmp / f"pygame-art-cards-{uuid.uuid4().hex[:8]}"
        decks = tmp / f"pygame-art-decks-{uuid.uuid4().hex[:8]}"
        pictures = tmp / f"pygame-art-src-{uuid.uuid4().hex[:8]}"
        for folder in (cards, decks, pictures):
            folder.mkdir(parents=True, exist_ok=True)
        picture = pictures / "卡面.png"
        raw = b"".join(b"\x00" + bytes((70, 150, 130)) * 4 for _ in range(4))

        def chunk(tag: bytes, data: bytes) -> bytes:
            body = tag + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

        picture.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
        try:
            record, errors = cc.make_card_record(
                title="带图的牌", cost="1", card_type="attack", target="enemy",
                rarity="common", keywords=[], text="",
                effects=[{"op": "damage", "value": "6", "hits": "1"}],
            )
            self.assertEqual(errors, {})
            path = cc.save_card(record, cards, art_source=picture)
            deck = cc.new_deck("带图卡组")
            cc.add_card_to_deck(deck, cc.saved_card_id(path), 1)
            cc.save_deck(deck, decks)
            cc.set_selected_deck(decks, deck["deck_id"])

            demo = PygameCombatDemo(cards_dir=cards, decks_dir=decks, use_user_cards=True)

            card = next(c for c in demo.combat.player.deck if c.art)
            self.assertTrue(card.art.startswith("art/"))
            self.assertIsNotNone(demo.card_art_for(card))            # 取到了玩家的那张图
            # 没设图的系统牌：走原来的系统卡面（「打击」在 assets/card_art 里有图）
            strike = next(c for c in demo.combat.player.deck if c.card_id == "strike_soyoi")
            self.assertEqual(strike.art, "")
            self.assertIsNotNone(demo.card_art_for(strike))
        finally:
            for folder in (cards, decks, pictures):
                shutil.rmtree(folder, ignore_errors=True)
            pygame.display.quit()


if __name__ == "__main__":
    unittest.main()


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")



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
        self.combat.on_player_turn_start = [
            callback for callback in self.combat.on_player_turn_start
            if callback.__name__ != "badge_turn_start"
        ]

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

    def test_enemy_attack_intent_can_carry_an_extra_effect(self):
        """攻击可以附带减益：打你 5 点的同时让你虚弱 2 层。"""
        self.enemy.intent = Intent(
            IntentAction.ATTACK,
            5,
            effect_operation=Op.APPLY_WEAK,
            effect_amount=2,
        )

        self.combat.execute_enemy_intent(self.enemy)

        self.assertEqual(self.player.get_power_amount(Powers.WEAK), 2)

    def test_unsupported_consuming_material_is_not_removed(self):
        card = self.add(STRIKE_SPEC.create())
        material = self.attach_effect(card, MatOp.REDUCE_NEXT_COST, consumes=True)

        self.play(card)

        self.assertEqual(get_loadout(card).material_count, 1)
        self.assertIs(get_loadout(card).slots[0].components[0], material)

    def test_bag_card_still_retains_after_redraw(self):
        """自封袋不再自动上身：玩家把它加工到哪张牌上，那张牌才跨回合保留。"""
        bag_card = self.add(reward("自封袋收纳"))
        carrier = self.add(STRIKE_SPEC.create())
        self.play(bag_card)
        bag = next(
            item for item in self.player.piles.pile(PileType.HAND).cards
            if getattr(item, "is_material", False)
        )
        equipped, _note = equip_from_hand(self.player, bag, carrier, combat=self.combat)
        self.assertTrue(equipped)
        self.assertTrue(carrier.material_retain)
        self.player.draw_per_turn = 1
        self.combat.end_player_turn()
        self.player.draw_per_turn = 0
        for _ in range(4):
            self.combat.end_player_turn()
            self.assertTrue(self.player.piles.pile(PileType.HAND).contains(carrier))
            self.assertEqual(self.count(carrier), 1)

    def test_terminal_phases_reject_play_without_spending(self):
        card = self.add(STRIKE_SPEC.create())
        for phase in ("setup", "enemy", "resolving", "victory", "defeat", "error"):
            self.combat.phase = phase
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                self.play(card)
            self.assertEqual(self.player.energy, 99)
            self.assertTrue(self.player.piles.pile(PileType.HAND).contains(card))
            self.assertEqual(self.combat.phase, phase)

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

    def test_thorns_reflects_once_even_when_both_have_thorns(self):
        self.player.add_power(Powers.THORNS, 2)
        self.enemy.add_power(Powers.THORNS, 3)
        self.player.block = 10
        self.enemy.intent = Intent(IntentAction.ATTACK, 7)
        self.combat.execute_enemy_intent(self.enemy)
        self.assertEqual((self.player.hp, self.player.block, self.enemy.hp), (72, 3, 998))

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
                    # 对局中途会生成素材牌（生成素材效果/遗物），所以只对"起始牌组的牌"要求一张不丢不重。
                    deck_cards = [card for card in all_cards if not getattr(card, "is_material", False)]
                    self.assertEqual({id(card) for card in deck_cards}, expected_ids)
                    self.assertEqual(len(deck_cards), len(expected_ids))
                    self.assertEqual(len(all_cards), len({id(card) for card in all_cards}))
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

class UIRegressionTests(unittest.TestCase):
    def setUp(self):
        import pygame
        from soyoi_game.pygame_ui import PygameCombatDemo
        self.pygame = pygame
        # 显式关闭玩家自制卡：这些回归测试断言的是「默认 10 张起始牌组」的行为，
        # 不能因为仓库里存在 user_cards/ 就被改掉。
        self.demo = PygameCombatDemo(use_user_cards=False)

    def tearDown(self):
        self.pygame.display.quit()

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
