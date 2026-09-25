"""创作端数据层：校验、卡牌记录、JSON 往返、卡组，以及命令行入口。"""

from __future__ import annotations
from pathlib import Path
from soyoi_game import card_creator as cc
from soyoi_game.core.cards import CardKeyword, CardType, PileType, RewardEffectOperation, TargetType
from soyoi_game.soyoi.card import get_loadout
from soyoi_game.soyoi.material_runtime import equip_from_hand
from soyoi_game.soyoi.materials import MaterialCategory, MaterialEffectOperation, MaterialEffectTiming
from soyoi_game.tkinter_ui import create_sample, list_cards
from soyoi_game.tkinter_ui import main as ui_main
import base64
import json
import shutil
import struct
import unittest
import uuid
import zlib


# 测试用的临时目录放在仓库内（tests/.tmp/），避免依赖系统临时目录权限
TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def write_png(path: Path, width: int = 4, height: int = 4, color: tuple = (200, 80, 60)) -> Path:
    """写一张真正合法的 PNG 当"玩家挑的图"。"""
    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return path


def fields(**overrides) -> dict:
    """一张合法卡的默认参数：2 费、造成 12 点伤害、目标单个敌人。"""
    data = {
        "title": "重击",
        "cost": "2",
        "card_type": "attack",
        "rarity": "common",
        "target": "enemy",
        "keywords": [],
        "text": "",
        "effects": [{"op": "damage", "value": "12", "hits": "1"}],
    }
    data.update(overrides)
    return data


class CheckTests(unittest.TestCase):
    """输入检查：每个错误都要给出人话提示。"""

    def test_effect_range_depends_on_effect_type(self):
        # 抽 500 张牌不行，但 500 点伤害是可以的
        _effects, errors = cc.check_effects([{"op": "draw", "value": "500", "hits": "1"}])
        self.assertIn("effect_0", errors)

        effects, errors = cc.check_effects([{"op": "damage", "value": "500", "hits": "1"}])
        self.assertEqual(errors, {})
        self.assertEqual(effects[0]["value"], 500)

    def test_unknown_effect_and_duplicates_are_rejected(self):
        _effects, errors = cc.check_effects([{"op": "delete_save", "value": "1", "hits": "1"}])
        self.assertIn("effect_0", errors)

        _effects, errors = cc.check_effects([
            {"op": "damage", "value": "6", "hits": "1"},
            {"op": "damage", "value": "6", "hits": "2"},
        ])
        self.assertIn("effect_1", errors)

class RecordTests(unittest.TestCase):
    """表单 -> 卡牌记录。"""

    def test_valid_form_becomes_record(self):
        record, errors = cc.make_card_record(**fields())

        self.assertEqual(errors, {})
        self.assertEqual(record["title"], "重击")
        self.assertEqual(record["cost"], 2)
        self.assertEqual(record["text"], "造成12点伤害。")
        self.assertEqual(record["effects"], [{"op": "damage", "value": 12, "hits": 1}])
        self.assertEqual(record["schema_version"], cc.SCHEMA_VERSION)

    def test_each_invalid_field_is_reported_by_name(self):
        _record, errors = cc.make_card_record(**fields(title="  ", cost="两点", target="everyone"))

        self.assertIn("title", errors)
        self.assertIn("cost", errors)
        self.assertIn("target", errors)

    def test_card_id_rules(self):
        self.assertEqual(cc.make_card_id("Heavy Strike"), "heavy_strike")
        chinese_id = cc.make_card_id("重击")
        self.assertTrue(chinese_id.startswith("user_"))
        self.assertLessEqual(len(chinese_id), 32)


class SpecTests(unittest.TestCase):
    """卡牌记录 -> 战斗框架认识的 CardSpec。"""

    def test_record_maps_to_card_spec(self):
        record, _errors = cc.make_card_record(**fields())

        spec = cc.make_card_spec(record)

        self.assertEqual(spec.card_type, CardType.ATTACK)
        self.assertEqual(spec.target, TargetType.ANY_ENEMY)
        self.assertEqual(spec.base_cost, 2)
        self.assertEqual(spec.base_effects[0].operation, RewardEffectOperation.DAMAGE)
        self.assertEqual(spec.base_effects[0].amount, 12)

class FileTests(unittest.TestCase):
    """JSON 读写。"""

    def setUp(self):
        self.directory = TMP_ROOT / f"cards-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def _save(self, title="Heavy Strike", **overrides):
        record, _errors = cc.make_card_record(**fields(title=title, **overrides))
        return cc.save_card(record, self.directory)

    def test_write_then_read(self):
        path = self._save()
        loaded = cc.read_card(path)

        self.assertEqual(path.name, "heavy_strike.json")
        self.assertEqual(loaded["title"], "Heavy Strike")
        self.assertEqual(loaded["effects"], [{"op": "damage", "value": 12, "hits": 1}])

    def test_same_name_gets_a_suffix_instead_of_overwriting(self):
        first = self._save(title="Heavy Strike", cost="2")
        second = self._save(title="Heavy Strike", cost="3")

        self.assertEqual(first.name, "heavy_strike.json")
        self.assertEqual(second.name, "heavy_strike-2.json")
        self.assertEqual(len(cc.load_cards(self.directory)[0]), 2)

    def test_broken_file_is_skipped_and_reported(self):
        self._save()
        (self.directory / "broken.json").write_text("{ 这不是 JSON", encoding="utf-8")
        (self.directory / "wrong.json").write_text(
            json.dumps({"card_id": "x", "title": "缺效果"}), encoding="utf-8"
        )

        records, errors = cc.load_cards(self.directory)

        self.assertEqual([record["title"] for record in records], ["Heavy Strike"])
        self.assertEqual(len(errors), 2)

class MaterialCardTests(unittest.TestCase):
    """素材牌：造一张能装到别的牌上的素材（相当于装备）。"""

    def setUp(self):
        self.directory = TMP_ROOT / f"material-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def material_fields(self, **overrides) -> dict:
        """一张合法素材牌的默认参数：承载牌打出后额外造成 3 点伤害。"""
        data = {
            "title": "亮片贴纸",
            "cost": "1",
            "card_type": "material",
            "rarity": "normal",
            "target": "enemy",
            "keywords": [],
            "text": "",
            "effects": [{"op": "material_damage", "value": "3", "hits": "1"}],
        }
        data.update(overrides)
        return data

    def test_record_becomes_a_material_card(self):
        record, _errors = cc.make_card_record(**self.material_fields())

        card = cc.make_card_spec(record).create()

        self.assertTrue(card.is_material)
        self.assertEqual(card.material_category, MaterialCategory.NORMAL)
        self.assertEqual(card.category_text, "普通")
        self.assertEqual(card.material_effects[0].operation, MaterialEffectOperation.MATERIAL_DAMAGE)
        self.assertIn(CardKeyword.UNPLAYABLE, card.keywords)
        self.assertIn(CardKeyword.RETAIN, card.keywords)

    def test_material_round_trips_through_json(self):
        record, _errors = cc.make_card_record(**self.material_fields())

        path = cc.save_card(record, self.directory)
        loaded = cc.read_card(path)

        self.assertEqual(loaded["card_type"], "material")
        self.assertEqual(loaded["rarity"], "normal")
        self.assertEqual(loaded["text"], "承载牌打出后额外造成3点伤害。")

    def test_material_from_creator_enters_the_deck_and_can_be_equipped(self):
        """端到端：自制素材跟着卡组进对局，装到一张手牌上让它的伤害变高。"""
        decks = TMP_ROOT / f"materialdecks-{uuid.uuid4().hex[:8]}"
        decks.mkdir(parents=True, exist_ok=True)
        record, _errors = cc.make_card_record(**self.material_fields())
        cc.save_card(record, self.directory)
        deck = cc.new_deck("素材测试组")
        cc.add_card_to_deck(deck, record["card_id"], 1)
        cc.save_deck(deck, decks)
        cc.set_selected_deck(decks, deck["deck_id"])
        combat = cc.build_combat(self.directory, decks)
        combat.start_combat()
        piles = combat.player.piles
        material = next(
            card for card in combat.player.deck if getattr(card, "is_material", False)
        )
        carrier = next(card for card in combat.player.deck if card.card_id == "strike_soyoi")
        piles.put_in_hand(material, combat.player.hand_limit)
        piles.put_in_hand(carrier, combat.player.hand_limit)
        enemy = combat.enemies[0]
        combat.player.energy = 3

        equipped, _note = equip_from_hand(combat.player, material, carrier, combat=combat)
        old_hp = enemy.hp
        combat.play_card(carrier, enemy)

        self.assertTrue(equipped)
        self.assertEqual(old_hp - enemy.hp, 6 + 3)
        self.assertTrue(piles.pile(PileType.EXHAUST).contains(material))
        shutil.rmtree(decks, ignore_errors=True)

    def test_one_shot_material_is_used_up_but_normal_material_is_not(self):
        """类别要管用：一次性素材结算完就没了，普通素材一直留在槽里。"""
        decks = TMP_ROOT / f"oneshotdecks-{uuid.uuid4().hex[:8]}"
        decks.mkdir(parents=True, exist_ok=True)
        try:
            left = self._play_carrier_twice(decks, "one_shot")
            again = self._play_carrier_twice(decks, "normal")
        finally:
            shutil.rmtree(decks, ignore_errors=True)

        self.assertEqual(left, (9, 0, 6))     # 一次性：9 点 -> 用完 -> 只剩本体 6 点
        self.assertEqual(again, (9, 1, 9))    # 普通：每次都 9 点，素材还在

    def _play_carrier_twice(self, decks, category):
        """造一张该类别素材 + 一张 6 点攻击牌，装好后打两次，返回 (首次伤害, 剩余素材, 二次伤害)。"""
        decks = Path(decks)
        material_record, _errors = cc.make_card_record(
            **self.material_fields(title=f"亮片贴纸{category}", rarity=category))
        material_id = cc.saved_card_id(cc.save_card(material_record, self.directory))
        carrier_record, _errors = cc.make_card_record(**fields(
            title=f"承载{category}", cost="0",
            effects=[{"op": "damage", "value": "6", "hits": "1"}]))
        carrier_id = cc.saved_card_id(cc.save_card(carrier_record, self.directory))
        deck = cc.new_deck("一次性素材组")
        cc.add_card_to_deck(deck, material_id, 1)
        cc.add_card_to_deck(deck, carrier_id, 1)
        cc.save_deck(deck, decks)
        cc.set_selected_deck(decks, deck["deck_id"])
        combat = cc.build_combat(self.directory, decks)
        combat.start_combat()
        piles = combat.player.piles
        material = next(c for c in combat.player.deck if getattr(c, "is_material", False))
        carrier = next(c for c in combat.player.deck if c.card_id == carrier_id)
        piles.move(carrier, PileType.HAND)
        piles.move(material, PileType.HAND)
        equip_from_hand(combat.player, material, carrier, combat=combat)
        enemy = combat.enemies[0]

        combat.player.energy = 3
        before = enemy.hp
        combat.play_card(carrier, enemy)
        first = before - enemy.hp
        remaining = get_loadout(carrier).material_count
        combat.player.energy = 3
        piles.move(carrier, PileType.HAND)
        before = enemy.hp
        combat.play_card(carrier, enemy)
        return first, remaining, before - enemy.hp


class DeckTests(unittest.TestCase):
    """卡组：新建（底子 4 打击 + 4 防御）、存取、选中、展开成牌组。"""

    def setUp(self):
        self.directory = TMP_ROOT / f"deck-{uuid.uuid4().hex[:8]}"
        self.decks = TMP_ROOT / f"decks-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.decks.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        shutil.rmtree(self.decks, ignore_errors=True)

    def test_new_deck_starts_with_four_strikes_and_four_defends(self):
        deck = cc.new_deck("测试组")

        self.assertEqual(deck["name"], "测试组")
        self.assertEqual(deck["cards"], {"strike_soyoi": 4, "defend_soyoi": 4})
        self.assertEqual(cc.deck_size(deck), 8)

    def test_save_load_round_trip_and_selected_pointer(self):
        deck = cc.new_deck("我的卡组")
        cc.add_card_to_deck(deck, "heavy_strike", 3)

        path = cc.save_deck(deck, self.decks)
        cc.set_selected_deck(self.decks, deck["deck_id"])

        self.assertEqual(path.name, f"{deck['deck_id']}.json")
        loaded, errors = cc.load_decks(self.decks)
        self.assertEqual(errors, [])
        self.assertEqual(loaded[0]["cards"]["heavy_strike"], 3)
        self.assertEqual(cc.selected_deck_id(self.decks), deck["deck_id"])

    def test_add_and_remove_card_in_deck(self):
        deck = cc.new_deck("我的卡组")

        cc.add_card_to_deck(deck, "heavy_strike", 2)
        self.assertEqual(deck["cards"]["heavy_strike"], 2)
        cc.add_card_to_deck(deck, "heavy_strike", 5)          # 同编号改份数，不会加两条
        self.assertEqual(deck["cards"]["heavy_strike"], 5)

        self.assertTrue(cc.remove_card_from_deck(deck, "heavy_strike"))
        self.assertFalse(cc.remove_card_from_deck(deck, "heavy_strike"))

    def test_sample_deck_is_builtin_and_read_only(self):
        sample = cc.sample_deck()

        self.assertTrue(sample.get("builtin"))
        self.assertEqual(sample["name"], cc.SAMPLE_DECK_NAME)
        self.assertGreaterEqual(cc.deck_size(sample), 10)
        self.assertEqual(cc.all_decks(self.decks)[0]["deck_id"], cc.SAMPLE_DECK_ID)
        self.assertFalse(cc.delete_deck(cc.SAMPLE_DECK_ID, self.decks))

    def test_resolve_deck_prefers_given_then_selected_then_sample(self):
        mine = cc.new_deck("我的卡组")
        cc.save_deck(mine, self.decks)

        given, _notes = cc.resolve_deck(self.directory, self.decks, "我的卡组")   # 按名字也认
        self.assertEqual(given["deck_id"], mine["deck_id"])

        cc.set_selected_deck(self.decks, mine["deck_id"])
        selected, _notes = cc.resolve_deck(self.directory, self.decks)
        self.assertEqual(selected["deck_id"], mine["deck_id"])

        fallback, notes = cc.resolve_deck(self.directory, self.decks, "并不存在的卡组")
        self.assertEqual(fallback["deck_id"], mine["deck_id"])
        self.assertTrue(notes)


class BattleTests(unittest.TestCase):
    """自制卡进对战。"""

    def setUp(self):
        self.directory = TMP_ROOT / f"battle-{uuid.uuid4().hex[:8]}"
        self.decks = TMP_ROOT / f"battledecks-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.decks.mkdir(parents=True, exist_ok=True)
        record, _errors = cc.make_card_record(**fields(title="Heavy Strike"))
        cc.save_card(record, self.directory)
        deck = cc.new_deck("我的卡组")
        cc.add_card_to_deck(deck, "heavy_strike", 2)
        cc.save_deck(deck, self.decks)
        cc.set_selected_deck(self.decks, deck["deck_id"])

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        shutil.rmtree(self.decks, ignore_errors=True)

    def test_selected_deck_is_what_gets_played(self):
        combat = cc.build_combat(self.directory, self.decks)
        combat.start_combat()

        titles = [card.title for card in combat.player.deck]

        self.assertEqual(len(titles), 10)                    # 4 打击 + 4 防御 + 2 张自制卡
        self.assertEqual(titles.count("Heavy Strike"), 2)
        self.assertEqual(titles.count("打击"), 4)
        self.assertEqual(titles.count("防御"), 4)

    def test_user_card_actually_plays_in_combat(self):
        """端到端：自制「重击」打出后应该正好造成 12 点伤害。"""
        combat = cc.build_combat(self.directory, self.decks)
        combat.start_combat()
        piles = combat.player.piles
        card = next(c for c in piles.pile(PileType.DRAW).cards if c.card_id == "heavy_strike")
        piles.put_in_hand(card, combat.player.hand_limit)
        combat.player.energy = 3
        enemy = combat.enemies[0]
        old_hp = enemy.hp

        combat.play_card(card, enemy)

        self.assertEqual(old_hp - enemy.hp, 12)
        self.assertEqual(combat.player.energy, 1)

class KeywordReplicationTests(unittest.TestCase):
    """创作端勾的「消耗 / 保留」要跟着进对局。"""

    def setUp(self):
        self.directory = TMP_ROOT / f"keyword-{uuid.uuid4().hex[:8]}"
        self.decks = TMP_ROOT / f"keyworddecks-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.decks.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        shutil.rmtree(self.decks, ignore_errors=True)

    def _battle_with(self, title, **overrides):
        """造一张牌、存下来、放进卡组、开一局，返回 (战斗, 这张牌)。"""
        record, errors = cc.make_card_record(**fields(title=title, **overrides))
        self.assertEqual(errors, {})
        spec = cc.make_card_spec(cc.read_card(cc.save_card(record, self.directory)))
        deck = cc.new_deck("关键字卡组")
        cc.add_card_to_deck(deck, spec.card_id, 1)
        cc.save_deck(deck, self.decks)
        cc.set_selected_deck(self.decks, deck["deck_id"])
        combat = cc.build_combat(self.directory, self.decks)
        combat.start_combat()
        card = next(c for c in combat.player.deck if c.card_id == spec.card_id)
        combat.player.piles.put_in_hand(card, combat.player.hand_limit)
        combat.player.energy = 3
        return combat, card

    def test_exhaust_card_goes_to_the_exhaust_pile(self):
        combat, card = self._battle_with("消耗重击", keywords=["exhaust"])

        combat.play_card(card, combat.enemies[0])

        self.assertTrue(combat.player.piles.pile(PileType.EXHAUST).contains(card))

    def test_retain_card_stays_in_hand_at_turn_end(self):
        combat, card = self._battle_with("保留重击", keywords=["retain"])
        # 对照：一张没勾保留的牌，回合结束应该被丢掉
        plain = next(c for c in combat.player.deck if c.card_id == "strike_soyoi")
        combat.player.piles.put_in_hand(plain, combat.player.hand_limit)

        combat.discard_hand()

        self.assertTrue(combat.player.piles.pile(PileType.HAND).contains(card))
        self.assertTrue(combat.player.piles.pile(PileType.DISCARD).contains(plain))


class CardArtTests(unittest.TestCase):
    """卡面插画：玩家挑一张图，复制进 art/ 目录，记录里只留相对路径。"""

    def setUp(self):
        self.directory = TMP_ROOT / f"art-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.pictures = TMP_ROOT / f"pictures-{uuid.uuid4().hex[:8]}"
        self.pictures.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        shutil.rmtree(self.pictures, ignore_errors=True)

    def test_chosen_picture_is_copied_next_to_the_cards(self):
        picture = write_png(self.pictures / "我的图.png")
        record, _errors = cc.make_card_record(**fields(title="带图的牌"))

        path = cc.save_card(record, self.directory, art_source=picture)

        saved = cc.read_card(path)
        self.assertEqual(saved["art"], f"art/{cc.saved_card_id(path)}.png")
        self.assertTrue((cc.art_folder(self.directory) / f"{cc.saved_card_id(path)}.png").is_file())

    def test_changing_the_picture_removes_the_old_one(self):
        """换成 jpg 之后，原来那张 png 不应该留在 art/ 里当孤儿文件。"""
        record, _errors = cc.make_card_record(**fields(title="带图的牌"))
        first = cc.save_card(record, self.directory, art_source=write_png(self.pictures / "a.png"))
        card_id = cc.saved_card_id(first)
        second = self.pictures / "b.jpg"
        jpeg = write_png(self.pictures / "b.png").read_bytes()
        second.write_bytes(b"\xff\xd8\xff\xe0" + jpeg[8:])     # 换掉文件头，当一张 jpg 用

        again, _errors = cc.make_card_record(**fields(title="带图的牌"))
        again["card_id"] = card_id
        cc.save_card(again, self.directory, overwrite=True, art_source=second)

        files = [p.name for p in cc.art_folder(self.directory).iterdir()]
        self.assertEqual(files, [f"{card_id}.jpg"])

    def test_art_field_must_point_inside_the_art_folder(self):
        for bad in ("../../secret.png", "art/../secret.png", "C:/windows/system32/x.png",
                    "art/evil.exe", "我的图.png"):
            with self.subTest(bad=bad):
                _record, errors = cc.make_card_record(**fields(title="坏插画", art=bad))

                self.assertIn("art", errors)

    def test_a_file_that_is_not_really_an_image_is_rejected(self):
        """把 .txt 改名成 .png 交给程序：后缀对了，但文件头不对，要拦下来。"""
        fake = self.pictures / "fake.png"
        fake.write_text("这不是图片", encoding="utf-8")

        with self.assertRaises(ValueError):
            cc.save_card_art(fake, "some_card", self.directory)

if __name__ == "__main__":
    unittest.main()


TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


class CreatorCliTests(unittest.TestCase):
    def setUp(self):
        self.directory = TMP_ROOT / f"cli-{uuid.uuid4().hex[:8]}"
        self.decks = TMP_ROOT / f"clidecks-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.decks.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        shutil.rmtree(self.decks, ignore_errors=True)

    def test_demo_creates_card_and_puts_it_in_a_deck(self):
        code = create_sample(self.directory, self.decks)

        self.assertEqual(code, 0)
        records, errors = cc.load_cards(self.directory)
        self.assertEqual(errors, [])
        self.assertEqual([record["title"] for record in records], ["重击"])
        self.assertEqual(records[0]["cost"], 2)

        # 示例卡组是内置的，所以第一次生成会另建一副"我的卡组"：4 打击 + 4 防御 + 重击×3
        decks, _errors = cc.load_decks(self.decks)
        self.assertEqual(len(decks), 1)
        self.assertEqual(decks[0]["cards"]["strike_soyoi"], 4)
        self.assertEqual(decks[0]["cards"]["defend_soyoi"], 4)
        self.assertEqual(decks[0]["cards"][records[0]["card_id"]], 3)
        self.assertEqual(cc.selected_deck_id(self.decks), decks[0]["deck_id"])

    def test_list_reports_cards_and_is_clean_when_empty(self):
        self.assertEqual(list_cards(self.directory, self.decks), 0)

        create_sample(self.directory, self.decks)

        self.assertEqual(list_cards(self.directory, self.decks), 0)

if __name__ == "__main__":
    unittest.main()


ROOT = Path(__file__).resolve().parents[1]
BAT_FILES = ["启动创作端.bat", "启动战斗端.bat"]


class BatFileTests(unittest.TestCase):
    def test_bat_files_are_ascii_without_bom(self):
        """cmd 用系统代码页读 .bat：中文会变乱码，BOM 会被当成命令。"""
        for name in BAT_FILES:
            raw = (ROOT / name).read_bytes()
            with self.subTest(file=name):
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"{name} 不该有 UTF-8 BOM")
                non_ascii = [byte for byte in raw if byte > 127]
                self.assertEqual(non_ascii, [], f"{name} 含非 ASCII 字节，GBK 控制台会乱码")

    def test_bat_files_call_the_project_entry_point(self):
        """两个脚本要分别启动造牌端和战斗端，别都写成一个。"""
        creator = (ROOT / "启动创作端.bat").read_text(encoding="ascii")
        battle = (ROOT / "启动战斗端.bat").read_text(encoding="ascii")

        self.assertIn("python main.py", creator)
        self.assertIn("python main.py --battle", battle)


if __name__ == "__main__":
    unittest.main()
