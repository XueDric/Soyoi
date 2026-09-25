"""创作端界面：真控件跑一遍填表、预览、保存、卡组面板。"""

from __future__ import annotations
from pathlib import Path
from soyoi_game import card_creator as cc
import shutil
import tkinter as tk
import unittest
import uuid


TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


class CreatorUiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # 没有图形环境就跳过，而不是让整套测试失败
            self.skipTest(f"当前环境没有可用的 Tk：{exc}")
        self.root.withdraw()
        self.directory = TMP_ROOT / f"ui-{uuid.uuid4().hex[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.decks = TMP_ROOT / f"uidecks-{uuid.uuid4().hex[:8]}"
        self.decks.mkdir(parents=True, exist_ok=True)

        from soyoi_game.tkinter_ui import CardCreatorApp

        self.app = CardCreatorApp(self.root, self.directory, self.decks)
        self.root.update_idletasks()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        shutil.rmtree(self.directory, ignore_errors=True)
        shutil.rmtree(self.decks, ignore_errors=True)

    def _fill(self, title: str = "Heavy Strike", cost: str = "2", damage: str = "12") -> None:
        self.app.title_var.set(title)
        self.app.cost_var.set(cost)
        self.app.effects[0].operation_box.set("造成伤害")
        self.app.effects[0]._on_operation_changed()
        self.app.effects[0].value.set(damage)

    def test_form_starts_with_one_effect_row(self):
        self.assertEqual(len(self.app.effects), 1)
        self.assertEqual(self.app.effects[0].operation_value, "damage")

    def _preview_texts(self) -> list[str]:
        """把预览画布上所有文字取出来（画布上还有矩形，跳过它们）。"""
        canvas = self.app.preview
        texts = []
        for item in canvas.find_all():
            if canvas.type(item) == "text":
                texts.append(canvas.itemcget(item, "text"))
        return texts

    def test_preview_shows_generated_card_text(self):
        self._fill()

        self.app.update_preview()

        texts = self._preview_texts()
        self.assertTrue(any("造成12点伤害" in text for text in texts), texts)
        self.assertIn("费用", self.app.stat_label.cget("text"))

    def test_saving_writes_json_and_refreshes_list(self):
        self._fill()

        self.app.save_card()

        files = [path.name for path in self.directory.glob("*.json")]
        self.assertIn("heavy_strike.json", files)
        # 自制卡排在最前面，后面跟着内置示例卡组的牌
        self.assertEqual(self.app.card_specs[0].card_id, "heavy_strike")
        self.assertIn("Heavy Strike", self.app.card_listbox.get(0))
        self.assertIn("已保存", self.app.status_var.get())

        # 回归：示例卡组的牌也要列在右边（以前列表里只有自制卡，示例卡根本选不到），
        # 选中其中的「打击」就能按「加入卡组」放进自己的卡组。
        rows = [self.app.card_listbox.get(index) for index in range(self.app.card_listbox.size())]
        self.assertTrue(any("示例卡组" in row for row in rows), rows)
        sample_row = next(index for index, row in enumerate(rows) if "示例卡组 · 打击" in row)
        self.app.card_listbox.selection_clear(0, tk.END)     # 鼠标点击是"换选中"，这里也照做
        self.app.card_listbox.selection_set(sample_row)
        self.app.copies_var.set("2")

        self.app.add_to_deck()

        deck = cc.load_decks(self.decks)[0][0]
        self.assertEqual(deck["cards"]["strike_soyoi"], 2)

    def test_invalid_cost_is_reported_and_nothing_is_written(self):
        self._fill(cost="两点")
        # 校验失败会弹窗，测试里把弹窗换成空操作，只检查状态栏和磁盘结果
        from soyoi_game import tkinter_ui as ui_module

        original = ui_module.messagebox.showerror
        ui_module.messagebox.showerror = lambda *args, **kwargs: None
        try:
            self.app.save_card()
        finally:
            ui_module.messagebox.showerror = original

        self.assertEqual(list(self.directory.glob("*.json")), [])
        self.assertIn("保存失败", self.app.status_var.get())

    def test_copies_box_is_the_real_number_of_copies(self):
        """回归：份数框里填几份，卡组里就是几份（原来保存时写死 3 份，跟框里填的无关）。"""
        self._fill(title="狂击")
        self.app.copies_var.set("4")

        self.app.save_card()

        card_id = self.app.card_specs[0].card_id
        deck = cc.load_decks(self.decks)[0][0]
        self.assertEqual(deck["cards"][card_id], 4)

        # 选中这张牌时，份数框显示的就是卡组里的真实份数
        self.app.card_listbox.selection_set(0)
        self.assertEqual(self.app.copies_var.get(), "4")

        # 改成 2 再按「加入卡组」：卡组里就变成 2 份（不是再加 2 份）
        self.app.copies_var.set("2")
        self.app.add_to_deck()
        deck = cc.load_decks(self.decks)[0][0]
        self.assertEqual(deck["cards"][card_id], 2)

        # 换一副卡组，框里跟着显示新卡组里的份数（没放这张牌就是 1）
        self.app.create_deck("二号")
        self.app.card_listbox.selection_set(0)
        self.assertEqual(self.app.copies_var.get(), "1")

    def test_add_and_remove_card_in_deck_from_the_ui(self):
        self._fill()
        self.app.save_card()
        self.app.card_listbox.selection_set(0)
        self.app.copies_var.set("5")

        self.app.add_to_deck()
        deck = cc.load_decks(self.decks)[0][0]
        self.assertEqual(deck["cards"]["heavy_strike"], 5)

        self.app.remove_from_deck()
        deck = cc.load_decks(self.decks)[0][0]

        self.assertNotIn("heavy_strike", deck["cards"])
        self.assertEqual(deck["cards"]["strike_soyoi"], 4)      # 底子还在

    def test_new_deck_rename_and_select(self):
        self.app.create_deck("测试组")

        self.app.deck_name_var.set("改名了")
        self.app.save_deck()

        decks, _errors = cc.load_decks(self.decks)
        self.assertEqual([deck["name"] for deck in decks], ["改名了"])
        self.assertEqual(cc.selected_deck_id(self.decks), decks[0]["deck_id"])
        self.assertIn("改名了", self.app.deck_box.cget("values"))

    def test_sample_deck_cannot_be_edited_in_place(self):
        self._fill()
        self.app.save_card()                                     # 先有一副自己的卡组
        self.app.deck_box.set(cc.SAMPLE_DECK_NAME)
        self.app.load_selected_deck()
        self.assertTrue(self.app.current_deck.get("builtin"))

        self.app.delete_deck()                                   # 内置的删不掉

        decks, _errors = cc.load_decks(self.decks)
        self.assertEqual(len(decks), 1)

    def _card_face_text(self) -> str:
        canvas = self.app.preview
        return " ".join(canvas.itemcget(item, "text") for item in canvas.find_all()
                        if canvas.type(item) == "text")

    def test_saving_a_card_whose_id_clashes_adds_the_right_one_to_the_deck(self):
        """回归：「重击A」和「猛击A」的编号都会算成 a，第二张存成 a-2。"""
        self._fill(title="重击A", damage="5")
        self.app.save_card()
        self._fill(title="猛击A", damage="9")
        self.app.save_card()

        deck = cc.load_decks(self.decks)[0][0]
        self.assertEqual(sorted(set(deck["cards"]) & {"a", "a-2"}), ["a", "a-2"])   # 两张都进了卡组

        combat = cc.build_combat(self.directory, self.decks)
        combat.start_combat()
        cards = {card.card_id: card for card in combat.player.deck}
        self.assertEqual(cards["a"].title, "重击A")
        self.assertEqual(cards["a-2"].title, "猛击A")
        self.assertEqual(cards["a-2"].current_effects()[0].amount, 9)

    def test_joining_a_card_while_the_sample_deck_is_selected_goes_to_my_deck(self):
        """在只读示例卡组上点「加入卡组」：加到玩家自己的卡组，而不是复制一副新卡组。"""
        self._fill()
        self.app.save_card()
        card_id = self.app.card_specs[0].card_id
        self.app.deck_box.set(cc.SAMPLE_DECK_NAME)
        self.app.load_selected_deck()
        self.app.card_listbox.selection_set(0)
        self.app.copies_var.set("2")

        self.app.add_to_deck()

        decks, _errors = cc.load_decks(self.decks)
        self.assertEqual(len(decks), 1)                        # 没有出现「示例卡组 副本」
        self.assertEqual(decks[0]["cards"][card_id], 2)
        self.assertEqual(self.app.deck_name_var.get(), decks[0]["name"])

    def test_picking_a_card_image_shows_it_and_saves_it_with_the_card(self):
        """挑一张卡面图：预览里马上能看到，保存后图会跟着卡一起存进 art/ 目录。"""
        from soyoi_game import tkinter_ui as ui_module

        picture = self._write_picture("我的卡面.png")
        ui_module.filedialog.askopenfilename = lambda **_kwargs: str(picture)
        self._fill(title="带图的牌")

        self.app.choose_art()

        self.assertEqual(self.app.art_label.cget("text"), "我的卡面.png")
        self.assertGreater(self._preview_image_count(), 0)      # 预览画布上真的画了图

        self.app.save_card()

        records, _errors = cc.load_cards(self.directory)
        self.assertTrue(records[0]["art"].startswith("art/"))
        self.assertTrue((cc.art_folder(self.directory) / records[0]["art"].split("/")[-1]).is_file())
        self.assertEqual(self._preview_image_count(), 1)        # 保存后预览还留着这张图

    def test_jpg_card_image_previews_without_any_image_library(self):
        """回归：去掉 Pillow 之后，Tk 不认的格式（jpg / webp）交给 pygame 解码，预览照样能显示。"""
        import os

        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")     # 只要解码，不开窗口
        import pygame

        from soyoi_game import tkinter_ui as ui_module

        pygame.init()
        folder = TMP_ROOT / f"pictures-{uuid.uuid4().hex[:8]}"
        folder.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, folder, True)
        picture = folder / "卡面.jpg"
        surface = pygame.Surface((60, 40))
        surface.fill((70, 150, 130))
        pygame.image.save(surface, str(picture))

        self.assertIsNotNone(ui_module.load_art_image(picture, 180, 54))   # 能解码成可画的对象

        ui_module.filedialog.askopenfilename = lambda **_kwargs: str(picture)
        self._fill(title="带 jpg 的牌")
        self.app.choose_art()

        self.assertEqual(self.app.art_label.cget("text"), "卡面.jpg")
        self.assertGreater(self._preview_image_count(), 0)

        self.app.save_card()

        records, _errors = cc.load_cards(self.directory)
        self.assertTrue(records[0]["art"].endswith(".jpg"))

    def _write_picture(self, name: str):
        """写一张真正合法的 PNG（标准库手拼，不依赖图像库）。"""
        import struct
        import zlib

        folder = TMP_ROOT / f"pictures-{uuid.uuid4().hex[:8]}"
        folder.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, folder, True)
        path = folder / name
        raw = b"".join(b"\x00" + bytes((200, 80, 60)) * 4 for _ in range(4))

        def chunk(tag: bytes, data: bytes) -> bytes:
            body = tag + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
        return path

    def _preview_image_count(self) -> int:
        canvas = self.app.preview
        self.root.update_idletasks()
        return sum(1 for item in canvas.find_all() if canvas.type(item) == "image")


if __name__ == "__main__":
    unittest.main()
