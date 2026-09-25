"""造牌端界面（tkinter）：填表、看卡面、存卡、管卡组。"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Optional

from . import card_creator as cc

# 配色沿用战斗界面的手工布艺风格，保证两边观感一致
INK = "#23282c"
PAPER = "#efe5cf"
PAPER_DARK = "#cbbda3"
TEAL = "#248184"
TEAL_DARK = "#18494e"
CORAL = "#da5b4b"
YELLOW = "#ebb12f"
WHITE = "#ffffff"
BG = "#31383d"

# 效果下拉框里显示的中文名（顺序就是下拉框里的顺序）
EFFECT_CHOICES = list(cc.EFFECT_LABELS.values())
# 素材牌用的是另一套效果（装到别的牌上才生效）
MATERIAL_EFFECT_CHOICES = list(cc.MATERIAL_EFFECT_LABELS.values())
# 下拉框里显示中文、JSON 里存英文，所以反查表也要有一份
OPERATION_KEYS = {label: key for key, label in cc.EFFECT_LABELS.items()}
MATERIAL_OPERATION_KEYS = {label: key for key, label in cc.MATERIAL_EFFECT_LABELS.items()}
# 切换效果类型时给个合理默认值：抽牌填"张数"、伤害填"伤害"
OPERATION_DEFAULTS = {
    "damage": "6",
    "block": "5",
    "draw": "1",
    "energy": "1",
    "vulnerable": "2",
    "weak": "2",
    "strength": "1",
    "heal": "4",
    "lose_hp": "3",
    "attach_material": "0",
}
MATERIAL_OPERATION_DEFAULTS = {
    "material_damage": "3",
    "material_block": "4",
    "material_vulnerable": "1",
    "material_weak": "1",
    "material_energy": "1",
    "material_draw": "1",
    "material_plating": "1",
    "material_retain": "0",
    "material_cost": "1",
}
# 下拉框显示中文、JSON 存英文，两边都要能互查
CARD_TYPE_KEYS = {choice.label: key for key, choice in cc.CARD_TYPE_CHOICES.items()}
RARITY_KEYS = {choice.label: key for key, choice in cc.RARITY_CHOICES.items()}
TARGET_KEYS = {choice.label: key for key, choice in cc.TARGET_CHOICES.items()}
# 素材牌没有稀有度，第三个下拉框在素材模式下变成"类别"
MATERIAL_CATEGORY_KEYS = {choice.label: key for key, choice in cc.MATERIAL_CATEGORY_CHOICES.items()}
CARD_TYPE_LABELS = {key: label for label, key in CARD_TYPE_KEYS.items()}
RARITY_LABELS = {key: label for label, key in RARITY_KEYS.items()}
TARGET_LABELS = {key: label for label, key in TARGET_KEYS.items()}
MATERIAL_CATEGORY_LABELS = {key: label for label, key in MATERIAL_CATEGORY_KEYS.items()}
KEYWORD_LABELS = {key: name for key, (name, _enum) in cc.KEYWORD_DEFS.items()}
MATERIAL_TYPE_KEY = "material"
# 挑图时默认开在哪儿：仓库自带的卡面目录（自己配的图也可以从这里挑）
# （用 ASSETS_DIR：打包后 assets 在解包目录，不在 exe 旁边）
ART_PICK_DIR = cc.ASSETS_DIR / "card_art"


def choice_key(value: str, labels: dict[str, str], default: str) -> str:
    """把下拉框的值统一成英文键。"""
    if value in labels:          # 中文名 -> 英文键
        return labels[value]
    if value in labels.values():  # 本来就是英文键
        return value
    return default


class EffectRow:
    """一行效果编辑控件：效果下拉框 + 数值 + 段数 + 删除。"""

    def __init__(self, parent: tk.Widget, app: "CardCreatorApp", index: int) -> None:
        self.app = app
        self.index = index
        self.is_material = False
        self.frame = tk.Frame(parent, bg=BG)
        self.frame.pack(fill="x", pady=2)

        self.operation = tk.StringVar(value="damage")
        self.value = tk.StringVar(value="6")
        self.hits = tk.StringVar(value="1")
        # 上一次的下拉框选择：用来判断"数值还是不是上一种效果的默认值"
        self._last_operation: Optional[str] = None
        # 数值/段数一改就重画卡面：卡面描述永远是"照着当前效果生成的"
        for variable in (self.value, self.hits):
            variable.trace_add("write", lambda *_args: app.refresh_preview())

        self.operation_box = ttk.Combobox(
            self.frame, state="readonly", width=10,
            values=EFFECT_CHOICES, textvariable=self.operation,
        )
        self.operation_box.grid(row=0, column=0, padx=(0, 6))
        self.operation_box.set(cc.EFFECT_LABELS["damage"])
        self.operation_box.bind("<<ComboboxSelected>>", self._on_operation_changed)

        self.value_label = tk.Label(self.frame, text="伤害", width=9, bg=BG, fg=PAPER)
        self.value_label.grid(row=0, column=1)
        self.value_entry = tk.Entry(self.frame, width=6, textvariable=self.value)
        self.value_entry.grid(row=0, column=2, padx=6)
        tk.Label(self.frame, text="段数", width=4, bg=BG, fg=PAPER).grid(row=0, column=3)
        self.hits_entry = tk.Entry(self.frame, width=4, textvariable=self.hits)
        self.hits_entry.grid(row=0, column=4, padx=6)

        tk.Button(self.frame, text="移除", width=6, bg=CORAL, fg=WHITE, relief="flat",
                  command=lambda: app.remove_effect(self)).grid(row=0, column=5)
        self.error_label = tk.Label(self.frame, text="", bg=BG, fg="#ffd08a", anchor="w")
        self.error_label.grid(row=1, column=0, columnspan=6, sticky="w")

    @property
    def labels(self) -> dict[str, str]:
        """当前这套下拉框：英文键 -> 中文名。"""
        return cc.MATERIAL_EFFECT_LABELS if self.is_material else cc.EFFECT_LABELS
    @property
    def defaults(self) -> dict[str, str]:
        return MATERIAL_OPERATION_DEFAULTS if self.is_material else OPERATION_DEFAULTS
    @property
    def operation_keys(self) -> dict[str, str]:
        """当前这套下拉框：中文名 -> 英文键（读下拉框时用）。"""
        return MATERIAL_OPERATION_KEYS if self.is_material else OPERATION_KEYS

    def set_kind(self, is_material: bool) -> None:
        """在"普通牌效果"和"素材效果"之间切换，并把这一行恢复成该套的第一个效果。"""
        self.is_material = is_material
        choices = MATERIAL_EFFECT_CHOICES if is_material else EFFECT_CHOICES
        self.operation_box.config(values=choices)
        self.operation_box.set(choices[0])
        self._last_operation = None
        self._on_operation_changed()

    @property
    def operation_value(self) -> str:
        """下拉框里显示的是中文，这里找回对应的英文键（存进 JSON 用的就是它）。"""
        return self.operation_keys[self.operation_box.get()]

    def to_fields(self) -> dict[str, Any]:
        return {"op": self.operation_value, "value": self.value.get(), "hits": self.hits.get()}

    def load(self, effect: dict[str, Any]) -> None:
        """把一条已保存的效果填回这一行（先填数值，最后再同步下拉框）。"""
        self.operation_box.set(self.labels[effect["op"]])
        self._last_operation = self.operation_value
        self.value.set(str(effect.get("value", 0)))
        self.hits.set(str(effect.get("hits", 1)))
        self._on_operation_changed()

    def set_error(self, message: str) -> None:
        self.error_label.config(text=message)

    def _on_operation_changed(self, _event: object = None) -> None:
        """切换效果时改标签（抽牌填张数、伤害填伤害），并把数值换成该效果的默认值。"""
        previous = self._last_operation
        operation = self.operation_value
        # 标签只留关键词：「造成伤害」->「伤害」，宽度有限
        self.value_label.config(
            text=self.labels[operation].replace("造成", "").replace("获得", "").replace("施加", ""))
        # 只有数值还等于默认值时才替换，不覆盖玩家填好的数字
        if previous is None or self.value.get().strip() == self.defaults[previous]:
            self.value.set(self.defaults[operation])
        # 只有伤害分多段，别的效果不需要段数
        self.hits_entry.config(state="normal" if operation in cc.DAMAGE_EFFECTS else "disabled")
        # 有些效果不用填数值（生成素材、承载牌可保留），把数值框锁上
        limits = cc.MATERIAL_VALUE_LIMITS if self.is_material else cc.VALUE_LIMITS
        self.value_entry.config(state="normal" if limits[operation] != (0, 0) else "disabled")
        self._last_operation = operation
        self.app.refresh_preview()


# 卡面缓存：key = (文件, 修改时间, 宽, 高) -> 能画的图片对象。
# 预览每敲一个字就重画，缓存一下省得反复解码 jpg / webp。
_ART_IMAGE_CACHE: dict[tuple, object] = {}
_ART_CACHE_LIMIT = 8


def load_art_image(path: Optional[Path | str], width: int, height: int):
    """读一张卡面插画，等比缩到能放进 width×height 的大小。"""
    if not path:
        return None
    path = Path(path)
    if not path.is_file():
        return None
    key = (str(path), path.stat().st_mtime, width, height)
    if key in _ART_IMAGE_CACHE:
        return _ART_IMAGE_CACHE[key]

    try:
        image = tk.PhotoImage(file=str(path))
        factor = max(1, -(-image.width() // width), -(-image.height() // height))
        image = image.subsample(factor, factor)
    except tk.TclError:
        image = _decode_art_with_pygame(path, width, height)

    if image is not None:
        if len(_ART_IMAGE_CACHE) >= _ART_CACHE_LIMIT:
            _ART_IMAGE_CACHE.pop(next(iter(_ART_IMAGE_CACHE)))
        _ART_IMAGE_CACHE[key] = image
    return image


def _decode_art_with_pygame(path: Path, width: int, height: int):
    """用 pygame 解码 Tk 不认的图片格式，再转成 Tk 能画的图片。"""
    try:
        import pygame
    except ImportError:                  # 只有 tkinter 的机器：那就只能预览 PNG / GIF
        return None
    if not pygame.get_init():
        pygame.init()
    try:
        source = pygame.image.load(str(path))
    except (pygame.error, FileNotFoundError):
        return None

    scale = min(width / source.get_width(), height / source.get_height(), 1.0)
    size = (max(1, int(source.get_width() * scale)), max(1, int(source.get_height() * scale)))
    small = pygame.transform.smoothscale(source, size)

    handle, temp_name = tempfile.mkstemp(prefix="soyoi-card-art-", suffix=".png")
    os.close(handle)
    try:
        pygame.image.save(small, temp_name)
        return tk.PhotoImage(file=temp_name)
    except (pygame.error, tk.TclError, OSError):
        return None
    finally:
        Path(temp_name).unlink(missing_ok=True)


class CardPreview(tk.Canvas):
    """卡面预览：把当前填的内容画成一张牌，样子和对战界面里的牌一致。"""

    WIDTH, HEIGHT = 240, 240

    # 各种类型的主色，和对战界面保持一致
    TYPE_COLORS = {
        "attack": ("#be483d", "攻击"),
        "skill": ("#237780", "技能"),
        "power": ("#b0812d", "能力"),
        "material": ("#9969ae", "素材"),
    }
    RARITY_STARS = {"basic": 0, "common": 1, "uncommon": 2, "rare": 3}

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, width=self.WIDTH, height=self.HEIGHT,
                         bg=BG, highlightthickness=0)
        self.preview_message = tk.StringVar(value="填左侧表单")
        # 画布文字不支持 textvariable，变了要自己改文字
        self.preview_message.trace_add("write", self._sync_message)
        self._message_item: int | None = None
        self._art_image = None            # 卡面插画的引用（不存住会被回收成空白）
        self._draw_placeholder()

    # ---- 画 ----
    def _draw_placeholder(self) -> None:
        self.delete("all")
        self.create_rectangle(6, 6, self.WIDTH - 6, self.HEIGHT - 6,
                              outline=PAPER_DARK, dash=(4, 4), width=2)
        self.create_text(self.WIDTH // 2, self.HEIGHT // 2, text="卡牌预览",
                         fill=PAPER_DARK, font=("Microsoft YaHei UI", 12, "bold"))
        self._message_item = self.create_text(
            self.WIDTH // 2, self.HEIGHT // 2 + 60, text=self.preview_message.get(),
            fill=PAPER_DARK, width=self.WIDTH - 40,
            font=("Microsoft YaHei UI", 9), justify="center",
        )

    def _sync_message(self, *_args) -> None:
        """提示文字变了就刷新画布上那一行（还没画过就先不管）。"""
        if self._message_item is not None and self.find_withtag(self._message_item):
            self.itemconfigure(self._message_item, text=self.preview_message.get())

    def show_card(self, record: dict, art_path: Optional[Path | str] = None) -> None:
        """把一条整理好的卡牌记录画出来。art_path 是玩家设的卡面插画，没有就画纯文字版。"""
        self.delete("all")
        is_material = record.get("card_type") == "material"
        color, type_name = self.TYPE_COLORS.get(record.get("card_type", "attack"), self.TYPE_COLORS["skill"])
        x0, y0, x1, y1 = 10, 10, self.WIDTH - 10, self.HEIGHT - 10

        # 卡牌底：深色描边 + 类型色卡身 + 米色正文区
        self.create_rectangle(x0 + 3, y0 + 4, x1 + 3, y1 + 4, fill="#12171b", outline="")
        self.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, fill=INK, outline="")
        self.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

        body = (x0 + 12, y0 + 62, x1 - 12, y1 - 34)
        self.create_rectangle(*body, fill=PAPER, outline=PAPER_DARK, width=2)

        # 卡面插画：有图就画在正文区顶上，文字往下让一让
        text_top = body[1] + 10
        image = load_art_image(art_path, body[2] - body[0] - 16, 54) if art_path else None
        self._art_image = image          # 存住引用：局部变量被回收的话画布上的图会变空白
        if image is not None:
            self.create_image((body[0] + body[2]) / 2, body[1] + 8, image=image, anchor="n")
            text_top = body[1] + 70

        # 费用圆圈：素材牌不花能量，画一个横杠
        self.create_oval(x0 + 6, y0 + 6, x0 + 50, y0 + 50, fill=YELLOW, outline=INK, width=2)
        cost_text = "—" if is_material else str(record.get("cost", 0))
        self.create_text(x0 + 28, y0 + 28, text=cost_text, fill=INK,
                         font=("Microsoft YaHei UI", 18, "bold"))

        # 卡名按实际像素宽裁，太长才加省略号（中文短、英文长，统一处理）
        self.create_rectangle(x0 + 56, y0 + 14, x1 - 12, y0 + 48, fill="#f4ead3", outline=PAPER_DARK)
        raw_title = str(record.get("title", ""))
        title = raw_title
        available = (x1 - 12) - (x0 + 56) - 14
        while title and self._text_width(title, 13, bold=True) > available:
            title = title[:-1]
        if title != raw_title:
            title = (title[:-1] + "…") if len(title) > 1 else "…"
        self.create_text((x0 + 56 + x1 - 12) / 2, y0 + 31, text=title, fill=INK,
                         font=("Microsoft YaHei UI", 13, "bold"))

        # 类型 / 目标 / 稀有度（素材牌这里显示类别）
        target_names = {"self": "自己", "enemy": "单体", "all": "全体"}
        if is_material:
            info = f"{type_name} · {cc.MATERIAL_CATEGORY_NAMES.get(record.get('rarity'), '')}"
        else:
            info = f"{type_name} · {target_names.get(record.get('target'), '') }"
        self.create_text((x0 + x1) / 2, y0 + 55, text=info, fill="#f7f0dd",
                         font=("Microsoft YaHei UI", 9))

        # 卡面文字（自动换行；上面画了插画就从插画下面开始写）
        text = str(record.get("text", ""))
        self.create_text(body[0] + 8, text_top, text=text, fill=INK, anchor="nw",
                         width=body[2] - body[0] - 16,
                         font=("Microsoft YaHei UI", 11), justify="left")

        # 关键字标签
        chip_x = body[0] + 6
        for keyword in record.get("keywords", []):
            label = KEYWORD_LABELS.get(keyword, keyword)
            box = self.create_rectangle(chip_x, y1 - 40, chip_x + 46, y1 - 18,
                                        fill="#f4ead3", outline=color, width=1)
            self.create_text(chip_x + 23, y1 - 29, text=label, fill=INK,
                             font=("Microsoft YaHei UI", 9, "bold"))
            chip_x += 54

        # 稀有度小星
        stars = self.RARITY_STARS.get(record.get("rarity", "common"), 0)
        for index in range(stars):
            cx = x1 - 18 - index * 16
            self._star(cx, y1 - 28, 7, YELLOW)

    def _star(self, cx: float, cy: float, size: int, color: str) -> None:
        self.create_polygon(
            [(cx, cy - size), (cx + size * 0.35, cy - size * 0.3), (cx + size, cy - size * 0.2),
             (cx + size * 0.5, cy + size * 0.3), (cx + size * 0.65, cy + size),
             (cx, cy + size * 0.5), (cx - size * 0.65, cy + size),
             (cx - size * 0.5, cy + size * 0.3), (cx - size, cy - size * 0.2),
             (cx - size * 0.35, cy - size * 0.3)],
            fill=color, outline="",
        )

    def _text_width(self, text: str, size: int, *, bold: bool = False) -> int:
        """量一段文字在实际字体下的像素宽度（tkinter 没有现成的测量接口，用临时文字项量）。"""
        item = self.create_text(-1000, -1000, text=text,
                                font=("Microsoft YaHei UI", size, "bold" if bold else "normal"))
        box = self.bbox(item)
        self.delete(item)
        return 0 if box is None else box[2] - box[0]


class CardCreatorApp:
    """创作端主窗口。表单读出来都是字符串，检查与保存都交给 card_creator。"""

    def __init__(self, root: tk.Tk, directory: Optional[Path | str] = None,
                 decks_directory: Optional[Path | str] = None) -> None:
        self.root = root
        self.directory = directory
        self.decks_directory = decks_directory
        self.effects: list[EffectRow] = []
        self.records: list[dict] = []
        self.card_specs: list[Any] = []
        self.saved_count = 0                 # 列表里"自制卡"的条数（后面还会补上示例卡组的系统卡）
        self.decks: list[dict] = []          # 示例卡组 + 玩家自己存的卡组
        self.current_deck: dict = {}         # 编辑区里正在改的那一副
        self._last_user_deck_id = ""         # 玩家自己那副卡组的编号（保存卡牌时优先放它）
        self._editing_id: Optional[str] = None
        # _art_saved 是已保存的相对路径，_art_choice 是刚挑还没保存的，只会有一个起作用。
        self._art_saved = ""
        self._art_choice = ""
        self._art_last_dir = ""              # 上次挑图所在的目录（下次对话框开在这里）

        root.title("卡牌创作工坊")
        root.configure(bg=BG)
        # 窗口大小按屏幕来：屏幕够高就开大一点，小屏也不至于顶到边
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{max(980, min(1120, screen_w - 80))}x{max(680, min(820, screen_h - 100))}")
        root.minsize(980, 680)

        self.title_var = tk.StringVar()
        self.cost_var = tk.StringVar(value="1")
        # 下拉框变量：没选过是英文键，选过之后是中文名，两种都认
        self.type_var = tk.StringVar(value="attack")
        self.rarity_var = tk.StringVar(value="common")
        self.target_var = tk.StringVar(value="enemy")
        self.text_var = tk.StringVar()
        self.exhaust_var = tk.BooleanVar(value=False)
        self.retain_var = tk.BooleanVar(value=False)
        self.copies_var = tk.StringVar(value="1")
        self.deck_var = tk.StringVar()
        self.deck_name_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")

        self._build_layout()
        # 控件都建好之后再挂监听：名字 / 费用 / 卡面描述一改就重画预览
        for variable in (self.title_var, self.cost_var, self.text_var):
            variable.trace_add("write", lambda *_args: self.refresh_preview())
        self.refresh_cards()

    # ---- 界面 ----
    def _build_layout(self) -> None:
        self.card_dir = cc.cards_folder(self.directory)

        header = tk.Frame(self.root, bg=TEAL_DARK)
        header.pack(fill="x")
        tk.Label(header, text="  卡牌创作工坊", bg=TEAL_DARK, fg=PAPER,
                 font=("Microsoft YaHei UI", 18, "bold")).pack(side="left", pady=10)
        # 主要操作固定放在标题栏上：不管下面内容多长，"保存卡牌"永远看得见
        toolbar = tk.Frame(header, bg=TEAL_DARK)
        toolbar.pack(side="right", padx=12)
        self._button(toolbar, "保存卡牌", CORAL, self.save_card, width=10, active="#b74a3c").pack(side="left")
        self._button(toolbar, "清空表单", TEAL, self.clear_form, width=8).pack(side="left", padx=6)
        self._button(toolbar, "打开目录", TEAL, self.open_folder, width=8).pack(side="left")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)

        # 左栏放进可滚动区域：效果加到 3 条、窗口再小，也不会把下面挤没
        left_outer = tk.Frame(body, bg=BG)
        left_outer.pack(side="left", fill="both", expand=True)
        self.form_canvas = tk.Canvas(left_outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_outer, orient="vertical", command=self.form_canvas.yview)
        left = tk.Frame(self.form_canvas, bg=BG)
        window = self.form_canvas.create_window((0, 0), window=left, anchor="nw")
        self.form_canvas.configure(yscrollcommand=scrollbar.set)
        self.form_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        left.bind("<Configure>",
                  lambda _event: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all")))
        self.form_canvas.bind("<Configure>",
                              lambda event: self.form_canvas.itemconfigure(window, width=event.width))
        # 鼠标停在表单上时才接管滚轮，免得滚动右侧卡牌列表时把表单也带着滚
        self.form_canvas.bind("<Enter>", lambda _event: self.form_canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.form_canvas.bind("<Leave>", lambda _event: self.form_canvas.unbind_all("<MouseWheel>"))

        right = tk.Frame(body, bg=BG)
        right.pack(side="right", fill="both", padx=(10, 0))
        self._build_form(left)
        self._build_card_list(right)

        status_bar = tk.Frame(self.root, bg=PAPER)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self.status_var, anchor="w", bg=PAPER, fg=INK,
                 font=("Microsoft YaHei UI", 10)).pack(side="left", fill="x", expand=True, padx=10, pady=6)
        tk.Label(status_bar, text=f"保存位置：{self.card_dir}", bg=PAPER, fg="#6b6a63",
                 font=("Microsoft YaHei UI", 9)).pack(side="right", padx=10)

    def _on_wheel(self, event) -> None:
        """鼠标滚轮滚左栏。"""
        self.form_canvas.yview_scroll(-int(event.delta / 120), "units")

    def _build_form(self, parent: tk.Widget) -> None:
        tk.Label(parent, text="① 卡牌信息", bg=BG, fg=YELLOW,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(2, 2))
        grid = tk.Frame(parent, bg=BG)
        grid.pack(fill="x")

        self._add_row(grid, 0, "名称", tk.Entry(grid, textvariable=self.title_var, width=22))
        self.cost_box = tk.Spinbox(
            grid, from_=cc.MIN_COST, to=cc.MAX_COST, width=5, textvariable=self.cost_var)
        self._add_row(grid, 1, "费用", self.cost_box)
        self.type_box = self._add_choice(grid, 2, "类型", list(CARD_TYPE_KEYS), self.type_var)
        self.target_box = self._add_choice(grid, 3, "目标", list(TARGET_KEYS), self.target_var)
        self.rarity_box = self._add_choice(grid, 4, "稀有度", list(RARITY_KEYS), self.rarity_var)

        keyword_row = tk.Frame(parent, bg=BG)
        keyword_row.pack(fill="x", pady=(6, 0))
        tk.Label(keyword_row, text="关键字", bg=BG, fg=PAPER, width=6, anchor="w").pack(side="left")
        self.exhaust_check = tk.Checkbutton(keyword_row, text="消耗", variable=self.exhaust_var, bg=BG, fg=PAPER,
                                            selectcolor=TEAL_DARK, activebackground=BG)
        self.exhaust_check.pack(side="left")
        self.retain_check = tk.Checkbutton(keyword_row, text="保留", variable=self.retain_var, bg=BG, fg=PAPER,
                                           selectcolor=TEAL_DARK, activebackground=BG)
        self.retain_check.pack(side="left", padx=8)

        tk.Label(parent, text="② 效果", bg=BG, fg=YELLOW,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(8, 2))
        self.effects_container = tk.Frame(parent, bg=BG)
        self.effects_container.pack(fill="x")
        tk.Button(parent, text="+ 再加一条效果", bg=TEAL, fg=WHITE, relief="flat",
                  activebackground=TEAL_DARK, command=self.add_effect).pack(anchor="w", pady=4)
        self.add_effect()
        # 类型改成「素材」后，费用/目标/关键字失效，效果和第三栏换成素材那套
        self.type_var.trace_add("write", self._on_type_changed)

        tk.Label(parent, text="③ 卡面预览", bg=BG, fg=YELLOW,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(8, 2))
        art_row = tk.Frame(parent, bg=BG)
        art_row.pack(fill="x")
        tk.Label(art_row, text="卡面图片", bg=BG, fg=PAPER, width=6, anchor="w").pack(side="left")
        self._button(art_row, "选择图片…", TEAL, self.choose_art, width=10).pack(side="left")
        self._button(art_row, "清除", TEAL_DARK, self.clear_art, width=5, active=TEAL).pack(side="left", padx=4)
        self.art_label = tk.Label(art_row, text="未设置", bg=BG, fg=PAPER_DARK, anchor="w",
                                  font=("Microsoft YaHei UI", 9))
        self.art_label.pack(side="left", padx=4)

        preview_row = tk.Frame(parent, bg=BG)
        preview_row.pack(fill="x", pady=(6, 0))
        # 左边是"玩家写什么"，右边实时画出这张牌长什么样
        self.text_entry = tk.Entry(preview_row, textvariable=self.text_var, width=34)
        self.text_entry.pack(side="left", fill="x", expand=True)

        card_row = tk.Frame(parent, bg=BG)
        card_row.pack(fill="x", pady=(8, 0))
        self.preview = CardPreview(card_row)
        self.preview.pack(side="left")
        self.preview_label = self.preview  # 旧名字保留一份，指的就是这块预览画布
        summary = tk.Frame(card_row, bg=BG)
        summary.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.stat_label = tk.Label(summary, text="", bg=BG, fg="#bfe0dc", anchor="nw",
                                   justify="left", font=("Microsoft YaHei UI", 10), wraplength=220)
        self.stat_label.pack(anchor="w")

    @staticmethod
    def _button(parent: tk.Widget, text: str, color: str, command, *, width: int = 10, active: str = "") -> tk.Button:
        """统一按钮样式，省得每个按钮都写一遍配色。"""
        return tk.Button(parent, text=text, bg=color, fg=WHITE, relief="flat", width=width,
                         activebackground=active or color, cursor="hand2", command=command)

    def _add_row(self, grid: tk.Widget, row: int, label: str, widget: tk.Widget) -> None:
        tk.Label(grid, text=label, bg=BG, fg=PAPER, width=6, anchor="w").grid(
            row=row, column=0, sticky="w", pady=3)
        widget.grid(row=row, column=1, sticky="w")

    def _add_choice(self, grid: tk.Widget, row: int, label: str, values: list[str], variable: tk.StringVar) -> ttk.Combobox:
        box = ttk.Combobox(grid, state="readonly", width=10, values=values, textvariable=variable)
        self._add_row(grid, row, label, box)
        return box

    def _build_card_list(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=BG)
        header.pack(fill="x", pady=(6, 2))
        tk.Label(header, text="已保存的卡牌", bg=BG, fg=YELLOW,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        self.count_label = tk.Label(header, text="共 0 张", bg=BG, fg=PAPER_DARK,
                                    font=("Microsoft YaHei UI", 9))
        self.count_label.pack(side="right")

        self.card_listbox = tk.Listbox(parent, width=42, height=15, bg=PAPER, fg=INK,
                                       activestyle="none", selectbackground=TEAL,
                                       selectforeground=WHITE, font=("Microsoft YaHei UI", 10),
                                       relief="flat", highlightthickness=0, borderwidth=0)
        self.card_listbox.pack(fill="both", expand=True)
        self.card_listbox.bind("<Double-Button-1>", lambda _event: self.load_selected())
        self.card_listbox.bind("<<ListboxSelect>>", lambda _event: self.sync_copies_box())

        tk.Label(parent, text="④ 卡组", bg=BG, fg=YELLOW,
                 font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(10, 2))
        deck_row = tk.Frame(parent, bg=BG)
        deck_row.pack(fill="x")
        self.deck_box = ttk.Combobox(deck_row, state="readonly", width=13, textvariable=self.deck_var)
        self.deck_box.pack(side="left")
        self.deck_box.bind("<<ComboboxSelected>>", lambda _event: self.load_selected_deck())
        self._button(deck_row, "新建卡组", TEAL, self.new_deck, width=9).pack(side="left", padx=(6, 0))
        self._button(deck_row, "删除卡组", CORAL, self.delete_deck, width=9).pack(side="left", padx=4)

        name_row = tk.Frame(parent, bg=BG)
        name_row.pack(fill="x", pady=(6, 0))
        tk.Label(name_row, text="名称", bg=BG, fg=PAPER).pack(side="left")
        tk.Entry(name_row, width=12, textvariable=self.deck_name_var).pack(side="left", padx=4)
        self._button(name_row, "保存卡组", CORAL, self.save_deck, width=9).pack(side="left")
        self._button(name_row, "另存为", TEAL_DARK, self.save_deck_as, width=7, active=TEAL).pack(side="left", padx=4)

        add_row = tk.Frame(parent, bg=BG)
        add_row.pack(fill="x", pady=(6, 0))
        tk.Label(add_row, text="份数", bg=BG, fg=PAPER).pack(side="left")
        tk.Spinbox(add_row, from_=1, to=cc.MAX_DECK_COPIES, width=4,
                   textvariable=self.copies_var).pack(side="left", padx=4)
        self._button(add_row, "加入卡组", TEAL, self.add_to_deck, width=9).pack(side="left")
        self._button(add_row, "移出", TEAL_DARK, self.remove_from_deck, width=6, active=TEAL).pack(side="left", padx=4)

        self.deck_label = tk.Label(parent, text="", bg=BG, fg="#bfe0dc", anchor="w",
                                   justify="left", wraplength=340)
        self.deck_label.pack(fill="x", pady=6)

        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill="x", pady=(8, 0))
        tk.Button(actions, text="载入表单", bg=TEAL_DARK, fg=PAPER, relief="flat", width=9,
                  activebackground=TEAL, command=self.load_selected).pack(side="left")
        tk.Button(actions, text="删除卡牌", bg=CORAL, fg=WHITE, relief="flat", width=9,
                  activebackground="#b74a3c", command=self.delete_selected).pack(side="left", padx=6)
        tk.Button(actions, text="刷新", bg=TEAL_DARK, fg=PAPER, relief="flat", width=6,
                  activebackground=TEAL, command=self.refresh_cards).pack(side="left")

    # ---- 效果行 ----
    def add_effect(self) -> None:
        if len(self.effects) >= cc.MAX_EFFECTS:
            self.set_status(f"最多 {cc.MAX_EFFECTS} 条效果")
            return
        row = EffectRow(self.effects_container, self, len(self.effects))
        if self.is_material():
            row.set_kind(True)
        self.effects.append(row)

    def is_material(self) -> bool:
        """表单当前选的类型是不是"素材牌"。"""
        return choice_key(self.type_var.get(), CARD_TYPE_KEYS, "attack") == MATERIAL_TYPE_KEY

    def _on_type_changed(self, *_args) -> None:
        """切换类型时换掉下拉框内容：素材牌不填费用/目标，稀有度位置改成素材类别。"""
        material = self.is_material()
        self.rarity_box.config(
            values=list(MATERIAL_CATEGORY_KEYS) if material else list(RARITY_KEYS))
        # 两种模式下都默认回到"普通"那一档
        self.rarity_var.set(
            MATERIAL_CATEGORY_LABELS["normal"] if material else RARITY_LABELS["common"])
        self.cost_box.config(state="disabled" if material else "normal")
        self.target_box.config(state="disabled" if material else "readonly")
        for check in (self.exhaust_check, self.retain_check):
            check.config(state="disabled" if material else "normal")
        for row in self.effects:
            row.set_kind(material)
        self.update_preview()

    def remove_effect(self, row: EffectRow) -> None:
        if len(self.effects) <= 1:
            self.set_status("至少留一条效果")
            return
        row.frame.destroy()
        self.effects.remove(row)
        self.update_preview()

    # ---- 读表单内容 ----
    def collect_fields(self) -> dict[str, Any]:
        """从界面读一遍当前填的内容（都是字符串）。"""
        material = self.is_material()
        keywords = []
        if not material:  # 素材牌没有关键字：它天生不能打出、回合结束不掉
            if self.exhaust_var.get():
                keywords.append("exhaust")
            if self.retain_var.get():
                keywords.append("retain")
        rarity_keys = MATERIAL_CATEGORY_KEYS if material else RARITY_KEYS
        return {
            "title": self.title_var.get(),
            "cost": self.cost_var.get(),
            "card_type": choice_key(self.type_var.get(), CARD_TYPE_KEYS, "attack"),
            "rarity": choice_key(self.rarity_var.get(), rarity_keys, "normal" if material else "common"),
            "target": choice_key(self.target_var.get(), TARGET_KEYS, "enemy"),
            "keywords": keywords,
            "text": self.text_var.get(),
            "effects": [row.to_fields() for row in self.effects],
            "art": self._art_saved,
        }

    def load_record(self, record: dict[str, Any]) -> None:
        self._editing_id = str(record.get("card_id", "")) or None
        self.title_var.set(record["title"])
        self.cost_var.set(str(record["cost"]))
        # 先切类型：切完下拉框和效果行才换成对应的那一套
        self.type_var.set(CARD_TYPE_LABELS[record["card_type"]])
        rarity_labels = (MATERIAL_CATEGORY_LABELS if record["card_type"] == "material" else RARITY_LABELS)
        self.rarity_var.set(rarity_labels[record["rarity"]])
        self.target_var.set(TARGET_LABELS[record["target"]])
        self.exhaust_var.set("exhaust" in record.get("keywords", []))
        self.retain_var.set("retain" in record.get("keywords", []))
        generated = cc.describe_effects(record.get("effects") or [], record["card_type"])
        self.text_var.set("" if record.get("text", "") == generated else record.get("text", ""))
        self._art_saved = str(record.get("art", "") or "")
        self._art_choice = ""

        for row in list(self.effects):
            row.frame.destroy()
        self.effects.clear()
        for effect in record["effects"]:
            self.add_effect()
            self.effects[-1].load(effect)
        self.refresh_art_label()
        self.update_preview()
        self.set_status(f"已载入「{record['title']}」")

    def clear_form(self) -> None:
        self._editing_id = None
        self._art_saved = ""
        self._art_choice = ""
        self.title_var.set("")
        self.cost_var.set("1")
        self.text_var.set("")
        self.exhaust_var.set(False)
        self.retain_var.set(False)
        for row in list(self.effects):
            row.frame.destroy()
        self.effects.clear()
        self.add_effect()
        self.refresh_art_label()
        self.set_status("表单已清空")

    # ---- 卡面图片 ----
    def choose_art(self) -> None:
        """挑一张卡面插画：先只是记住它，点「保存卡牌」时才复制进 art/ 目录。"""
        patterns = " ".join(f"*{suffix}" for suffix in cc.ART_EXTENSIONS)
        start = self._art_last_dir or (ART_PICK_DIR if ART_PICK_DIR.is_dir() else self.card_dir)
        path = filedialog.askopenfilename(
            title="选一张卡面图片",
            initialdir=str(start),
            filetypes=[("图片", patterns), ("所有文件", "*.*")],
        )
        if not path:
            return
        if load_art_image(path, CardPreview.WIDTH, CardPreview.HEIGHT) is None:
            self.set_status("这张图读不了，换一张试试")
            messagebox.showerror("图片读不了", f"「{Path(path).name}」不是能用的图片，换一张试试。")
            return
        self._art_choice = path
        self._art_last_dir = str(Path(path).parent)      # 下次还开在上次那个目录
        self.refresh_art_label()

    def clear_art(self) -> None:
        """清掉卡面插画：保存时 art/ 里那张也会跟着删掉。"""
        self._art_saved = ""
        self._art_choice = ""
        self.refresh_art_label()

    def art_path(self) -> Optional[Path]:
        """当前该显示哪张图：刚挑的优先，其次是已保存的那张。"""
        if self._art_choice:
            return Path(self._art_choice)
        return cc.find_card_art(self._art_saved, self.directory)

    def refresh_art_label(self) -> None:
        """插画那行的小字：显示正在用的是哪个文件。"""
        path = self.art_path()
        self.art_label.config(text=path.name if path else "未设置")
        self.refresh_preview()

    # ---- 预览 ----
    def refresh_preview(self) -> None:
        """给控件回调用的安全入口：预览画布还没建好时什么都不做。"""
        if getattr(self, "preview", None) is not None:
            self.update_preview()

    def update_preview(self) -> None:
        """填的东西一有变化就重画卡面，并把错误落到出错的那些行上。"""
        record, errors = cc.make_card_record(**self.collect_fields())
        for index, row in enumerate(self.effects):
            row.set_error(errors.get(f"effect_{index}", ""))

        if record is None:
            self.preview._draw_placeholder()
            if not self.title_var.get().strip() and "title" in errors:
                # 还没开始填，就别一上来就报红：只提示一下
                self.preview.preview_message.set("填左侧表单")
                self.stat_label.config(text="", fg="#bfe0dc")
                return
            self.preview.preview_message.set("⚠ " + list(errors.values())[0])
            self.stat_label.config(text="\n".join(f"· {tip}" for tip in errors.values()), fg="#ffd08a")
            return

        self.preview.show_card(record, self.art_path())
        self.stat_label.config(text=self._summary(record), fg="#bfe0dc")

    def _summary(self, record: dict) -> str:
        """预览右边那几行小字：这张牌的关键属性，跟着表单变。"""
        if record["card_type"] == "material":
            return (
                "费用　—\n"
                "类型　素材\n"
                f"类别　{cc.MATERIAL_CATEGORY_NAMES[record['rarity']]}"
            )
        cost = record["cost"]
        type_name = cc.CARD_TYPE_NAMES[record["card_type"]]
        target_name = cc.TARGET_NAMES[record["target"]]
        rarity_name = cc.RARITY_NAMES[record["rarity"]]
        keywords = "、".join(KEYWORD_LABELS.get(key, key) for key in record["keywords"]) or "无"
        return (
            f"费用　{cost}\n"
            f"类型　{type_name}\n"
            f"目标　{target_name}\n"
            f"稀有度　{rarity_name}\n"
            f"关键字　{keywords}"
        )

    # ---- 保存 ----
    def save_card(self) -> None:
        record, errors = cc.make_card_record(**self.collect_fields())
        if record is None:
            for index, row in enumerate(self.effects):
                row.set_error(errors.get(f"effect_{index}", ""))
            self.set_status("保存失败，检查一下表单")
            messagebox.showerror("保存失败", "\n".join(f"· {tip}" for tip in errors.values()))
            return

        # 载入老卡且没改名 -> 覆盖；否则新建，避免同名互相覆盖。
        titles = {item["card_id"]: item["title"] for item in self.records}
        overwrite = self._editing_id is not None and titles.get(self._editing_id) == record["title"]
        if overwrite:
            record["card_id"] = self._editing_id
        try:
            path = cc.save_card(record, self.directory, overwrite=overwrite,
                                art_source=self._art_choice or None)
        except (OSError, ValueError, FileExistsError) as error:
            self.set_status(f"保存失败：{error}")
            messagebox.showerror("保存失败", str(error))
            return
        # 撞名时编号会变（猛击A 也会被算成 a），所以要用真正落盘的那个编号
        saved_id = cc.saved_card_id(path)
        self._editing_id = saved_id                  # 接着改这张牌时还是覆盖它
        copies = self.copies_in_box()                # 先记住份数：刷新列表会把「份数」刷成真实份数
        # 插画以落盘后的记录为准（编号可能带后缀，图片名跟着编号走）
        saved = cc.read_card(path)
        self._art_choice = ""
        self._art_saved = str(saved.get("art", "") or "")
        if not self._art_saved:
            cc.remove_card_art(saved_id, self.directory)   # 清空了插画：art/ 里那张也删掉
        self.refresh_art_label()
        self.refresh_cards(select_id=saved_id)       # 存完就把刚保存的这张选中
        self.set_status(f"已保存：{path.name}")
        self.add_saved_card_to_deck(saved_id, copies)

    def user_deck(self) -> dict:
        """玩家自己那副卡组：优先用上次选中的，其次第一副，都没有才新建一副。"""
        deck = cc.find_deck(self.decks, self._last_user_deck_id)
        if deck is None:
            deck = next((item for item in self.decks if not item.get("builtin")), None)
        if deck is None:
            deck = cc.new_deck(self.unique_deck_name("我的卡组"))
            cc.save_deck(deck, self.decks_directory)
        return deck

    def add_saved_card_to_deck(self, card_id: str, copies: Optional[int] = None) -> None:
        """刚保存的牌顺手加进卡组 —— 造完牌马上就能进对局试。"""
        deck = self.current_deck or {}
        if deck.get("builtin") or not deck:
            deck = self.user_deck()
            self.current_deck = deck
        if self.copies_in_deck(card_id) == 0:
            cc.add_card_to_deck(deck, card_id, copies if copies else self.copies_in_box())
        cc.save_deck(deck, self.decks_directory)
        cc.set_selected_deck(self.decks_directory, deck["deck_id"])
        self.refresh_decks(deck["deck_id"])
        self.fill_card_list(card_id)         # 从示例卡组切到自己那副时，列表也跟着换过来
        now = self.copies_in_deck(card_id)
        self.set_status(f"已保存「{deck['name']}」里 {now} 份")

    def refresh_cards(self, select_id: str = "") -> None:
        """重读卡牌列表；select_id 是重读之后要选中的那张卡（保存完就选上，方便接着加/移出）。"""
        self.records, errors = cc.load_cards(self.directory)
        self.card_specs = [cc.make_card_spec(item) for item in self.records]
        self.saved_count = len(self.card_specs)
        self.refresh_decks()                 # 先定下"当前卡组"，列表要按它来画
        self.fill_card_list(select_id)
        self.sync_copies_box()
        if errors:
            self.set_status("有文件读不了：" + "；".join(errors))
        else:
            self.update_preview()

    def fill_card_list(self, select_id: str = "") -> None:
        """画右边的列表：自制卡在前，内置示例卡组的牌跟在后面。

        示例卡组里的牌都是系统卡（打击 / 防御 / 那批奖励牌），没有 JSON 文件，
        改不了也删不掉，但一直列出来才能选中它们、按「加入卡组」放进自己的卡组。
        """
        self.card_specs = self.card_specs[: self.saved_count]      # 去掉上一次补进去的系统卡
        self.card_listbox.delete(0, tk.END)
        for index, spec in enumerate(self.card_specs):
            self.card_listbox.insert(tk.END, f"{spec.title}　{spec.base_cost}费　{spec.base_text}")
            if select_id and spec.card_id == select_id:
                self.card_listbox.selection_set(index)
                self.card_listbox.see(index)
        extras = self.sample_deck_specs()
        for spec in extras:
            self.card_listbox.insert(
                tk.END, f"示例卡组 · {spec.title}　{spec.base_cost}费　{spec.base_text}")
            self.card_specs.append(spec)
        count = f"共 {self.saved_count} 张" if self.saved_count else "还没有自制卡（表单里造一张）"
        if extras:
            count += f"　＋ 示例卡组 {len(extras)} 种（选中后按「加入卡组」）"
        self.count_label.config(text=count)

    def sample_deck_specs(self) -> list:
        """内置示例卡组里的牌（都是系统卡），自制卡里已经有的就不重复列。"""
        table = cc.spec_table(self.directory)
        listed = {spec.card_id for spec in self.card_specs}
        specs = []
        for card_id in cc.sample_deck().get("cards", {}):
            spec = table.get(str(card_id))
            if spec is not None and spec.card_id not in listed:
                specs.append(spec)
        return specs

    def _selected_spec(self):
        """当前"要操作的那张卡"：优先用列表里选中的，没选就按表单里的卡名去找。"""
        selection = self.card_listbox.curselection()
        if selection and selection[0] < len(self.card_specs):
            return self.card_specs[selection[0]]

        title = self.title_var.get().strip()
        if title:
            for index, spec in enumerate(self.card_specs):
                if spec.title == title:
                    self.card_listbox.selection_set(index)
                    self.card_listbox.see(index)
                    return spec

        if not self.card_specs:
            self.set_status("先点「保存卡牌」")
        else:
            self.set_status("先在列表里点一张卡")
        return None

    def load_selected(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return
        record = next((item for item in self.records if item.get("card_id") == spec.card_id), None)
        if record is None:
            self.set_status(f"「{spec.title}」是系统卡，改不了；可以按「加入卡组」放进自己的卡组")
            return
        self.load_record(record)

    def delete_selected(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return
        if spec.card_id not in {item.get("card_id") for item in self.records}:
            self.set_status(f"「{spec.title}」是系统卡，删不掉；只能从卡组里移出")
            return
        if not messagebox.askyesno("删除确认", f"确定删除「{spec.title}」吗？"):
            return
        path = cc.cards_folder(self.directory) / f"{spec.card_id}.json"
        path.unlink(missing_ok=True)
        cc.remove_card_art(spec.card_id, self.directory)      # 卡面插画一起删掉，别留孤儿文件
        # 顺手把它从各个卡组里拿掉，免得卡组里留一个造不出来的编号
        cc.remove_card_from_all_decks(spec.card_id, self.decks_directory)
        self.refresh_cards()
        self.set_status(f"已删除「{spec.title}」")

    def change_deck(self, direction: int) -> None:
        """兼容旧入口：+1 加入当前卡组，-1 从卡组移出。"""
        if direction < 0:
            self.remove_from_deck()
        else:
            self.add_to_deck()

    # ---- 卡组 ----
    def refresh_decks(self, select_id: Optional[str] = None) -> None:
        """重新读卡组清单，填下拉框，并把要用的那副载入编辑区。"""
        self.decks = cc.all_decks(self.decks_directory)
        self.deck_box.config(values=[deck["name"] for deck in self.decks])
        want = select_id or cc.selected_deck_id(self.decks_directory)
        deck = cc.find_deck(self.decks, want) or self.decks[0]
        self.current_deck = dict(deck)
        self.current_deck["cards"] = dict(deck["cards"])
        if not deck.get("builtin"):
            self._last_user_deck_id = deck["deck_id"]     # 记住玩家自己那副
        self.deck_var.set(deck["name"])
        self.deck_name_var.set(deck["name"])
        self.update_deck_label()
        self.sync_copies_box()          # 换卡组了，份数要跟着变成这副卡组里的真实份数

    def copies_in_deck(self, card_id: str) -> int:
        """这张牌在当前卡组里放了几份（没放就是 0）。"""
        deck = self.current_deck or {}
        try:
            return int(deck.get("cards", {}).get(str(card_id), 0))
        except (TypeError, ValueError):
            return 0

    def copies_in_box(self) -> int:
        """「份数」框里的数字，填错了就按 1 算。"""
        try:
            copies = int(str(self.copies_var.get()).strip())
        except ValueError:
            return 1
        return max(1, min(copies, cc.MAX_DECK_COPIES))

    def sync_copies_box(self) -> None:
        """把「份数」显示成选中的这张牌在卡组里的真实份数（不在卡组里就显示 1）。"""
        selection = self.card_listbox.curselection()
        if not selection or selection[0] >= len(self.card_specs):
            return
        card_id = self.card_specs[selection[0]].card_id
        self.copies_var.set(str(self.copies_in_deck(card_id) or 1))

    def deck_of_selection(self) -> dict:
        """下拉框里现在选的是哪副卡组：按位置取，重名也不会认错。"""
        index = self.deck_box.current()
        if 0 <= index < len(self.decks):
            return self.decks[index]
        return cc.find_deck(self.decks, self.deck_var.get()) or self.decks[0]

    def unique_deck_name(self, name: str) -> str:
        """卡组重名就自动加个 -2、-3，免得下拉框里两行一模一样。"""
        taken = {deck["name"] for deck in self.decks}
        if name not in taken:
            return name
        for suffix in range(2, 100):
            candidate = f"{name} {suffix}"
            if candidate not in taken:
                return candidate
        return name

    def load_selected_deck(self) -> None:
        """换卡组：载入它，并把它设成"对局要用的那副"。"""
        deck = self.deck_of_selection()
        self.current_deck = dict(deck)
        self.current_deck["cards"] = dict(deck["cards"])
        if not deck.get("builtin"):
            self._last_user_deck_id = deck["deck_id"]     # 记住玩家自己那副
        self.deck_name_var.set(deck["name"])
        cc.set_selected_deck(self.decks_directory, deck["deck_id"])
        self.update_deck_label()
        self.fill_card_list()            # 切到示例卡组时，把它的牌也列到右边
        self.set_status(f"对局用「{deck['name']}」")

    def editable_deck(self) -> dict:
        """拿到能改的那副卡组。"""
        if self.current_deck.get("builtin"):
            deck = self.user_deck()
            self.current_deck = deck
            self.refresh_decks(deck["deck_id"])      # 界面上会直接切到你自己那副卡组
            return self.current_deck
        return self.current_deck

    def new_deck(self) -> None:
        """新建卡组：先问名字，再交给 create_deck()。"""
        name = simpledialog.askstring("新建卡组", "给卡组起个名字：", initialvalue="我的卡组", parent=self.root)
        if name is None:
            return
        self.create_deck(name)

    def create_deck(self, name: str) -> dict:
        """按名字建一副新卡组（底子 4 张打击 + 4 张防御），存下来并选中它。"""
        deck = cc.new_deck(self.unique_deck_name(name.strip() or "我的卡组"))
        cc.save_deck(deck, self.decks_directory)
        cc.set_selected_deck(self.decks_directory, deck["deck_id"])
        self.refresh_decks(deck["deck_id"])
        self.set_status(f"已新建「{deck['name']}」")
        return deck

    def save_deck(self) -> None:
        """保存键：把当前卡组（连同改过的名字）存下来，对局就用它。"""
        deck = self.editable_deck()
        name = self.deck_name_var.get().strip() or deck["name"]
        others = {item["name"] for item in self.decks
                  if item["deck_id"] != deck["deck_id"] and not item.get("builtin")}
        if name in others:                       # 名字撞了：先提示，按"另存为"处理更清楚
            self.set_status(f"已有叫「{name}」的卡组，换个名字或点「另存为」")
            return
        deck["name"] = name
        cc.save_deck(deck, self.decks_directory)
        cc.set_selected_deck(self.decks_directory, deck["deck_id"])
        self.refresh_decks(deck["deck_id"])
        self.set_status(f"已保存「{name}」")

    def save_deck_as(self) -> None:
        """另存为新卡组：用名字框里的名字存一份，原来那副留着。"""
        name = self.unique_deck_name(self.deck_name_var.get().strip() or "新卡组")
        deck = cc.new_deck(name)
        deck["cards"] = dict(self.current_deck.get("cards", {}))
        cc.save_deck(deck, self.decks_directory)
        cc.set_selected_deck(self.decks_directory, deck["deck_id"])
        self.refresh_decks(deck["deck_id"])
        self.set_status(f"已另存为「{name}」")

    def delete_deck(self) -> None:
        deck = self.deck_of_selection()
        if deck.get("builtin"):
            self.set_status("示例卡组不能删")
            return
        if not messagebox.askyesno("删除卡组", f"确定删掉卡组「{deck['name']}」吗？"):
            return
        cc.delete_deck(deck["deck_id"], self.decks_directory)
        self.refresh_decks()
        self.set_status(f"已删除「{deck['name']}」")

    def add_to_deck(self) -> None:
        """把列表里选中的卡按「份数」放进当前卡组：框里填几份，卡组里就是几份。"""
        spec = self._selected_spec()
        if spec is None:
            return
        copies = self.copies_in_box()      # 先读框里的数字：切卡组会把框刷成真实份数
        deck = self.editable_deck()
        cc.add_card_to_deck(deck, spec.card_id, copies)
        cc.save_deck(deck, self.decks_directory)
        cc.set_selected_deck(self.decks_directory, deck["deck_id"])
        self.refresh_decks(deck["deck_id"])
        self.fill_card_list(spec.card_id)
        self.set_status(f"「{spec.title}」×{self.copies_in_deck(spec.card_id)}")
        self.sync_copies_box()

    def remove_from_deck(self) -> None:
        """把列表里选中的卡从当前卡组移出（卡牌文件不动）。"""
        spec = self._selected_spec()
        if spec is None:
            return
        deck = self.editable_deck()
        if not cc.remove_card_from_deck(deck, spec.card_id):
            self.set_status(f"「{spec.title}」不在卡组里")
            return
        cc.save_deck(deck, self.decks_directory)
        self.refresh_decks(deck["deck_id"])
        self.fill_card_list(spec.card_id)
        self.set_status(f"已移出「{spec.title}」")

    def update_deck_label(self) -> None:
        """卡组内容一行显示：卡名×份数，种类多了就截断，末尾是总数。"""
        deck = self.current_deck or {}
        cards = deck.get("cards", {})
        if not cards:
            self.deck_label.config(text="空卡组")
            return
        titles = {spec.card_id: spec.title for spec in cc.spec_table(self.directory).values()}
        parts = [f"{titles.get(card_id, card_id)}×{copies}" for card_id, copies in cards.items()]
        text = " · ".join(parts[:6])
        if len(parts) > 6:
            text += f" · 等 {len(parts)} 种"
        text += f"　共 {cc.deck_size(deck)} 张"
        if deck.get("builtin"):
            text += "（只读）"
        self.deck_label.config(text=text)

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def open_folder(self) -> None:
        """在资源管理器里打开卡牌目录，方便直接看那些 JSON 文件。"""
        folder = cc.cards_folder(self.directory)
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform != "win32":            # os.startfile 只有 Windows 有
            self.set_status(f"卡牌目录：{folder}")
            return
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except OSError as error:               # 没有资源管理器、路径没权限之类
            self.set_status(f"打不开目录（{error}）：{folder}")


# ---- CLI ----
# 下面几个函数不开窗口也能用，命令行和自动化测试都调它们。
def list_cards(directory: Optional[Path | str] = None,
               decks_directory: Optional[Path | str] = None) -> int:
    """列出卡牌与卡组，返回退出码（有坏文件就算失败）。"""
    records, errors = cc.load_cards(directory)
    print(f"卡牌目录：{cc.cards_folder(directory)}")
    if not records:
        print("（还没有保存任何卡牌）")
    for record in records:
        print(f"- {record['title']}（{record['card_id']}）{record['cost']} 费　{record['text']}")
    decks, deck_errors = cc.load_decks(decks_directory)
    selected = cc.selected_deck_id(decks_directory)
    print(f"卡组目录：{cc.decks_folder(decks_directory)}")
    for deck in cc.all_decks(decks_directory):
        mark = "→" if deck["deck_id"] == selected else "　"
        print(f"{mark} {cc.describe_deck(deck)}" + ("（内置示例卡组）" if deck.get("builtin") else ""))
    for message in errors + deck_errors:
        print(f"[跳过] {message}", file=sys.stderr)
    return 1 if errors or deck_errors else 0


def create_sample(directory: Optional[Path | str] = None,
                  decks_directory: Optional[Path | str] = None) -> int:
    """无界面地生成示例卡「重击」，并加进卡组，用于演示与自动测试。"""
    record, errors = cc.make_card_record(
        title="重击", cost=2, card_type="attack", target="enemy", rarity="common",
        keywords=[], effects=[{"op": "damage", "value": 12, "hits": 1}],
    )
    if record is None:
        print(f"示例卡都存不下来：{errors}", file=sys.stderr)
        return 1
    path = cc.save_card(record, directory)

    deck, _notes = cc.resolve_deck(directory, decks_directory)
    if deck.get("builtin"):
        deck = cc.new_deck("我的卡组")          # 内置的示例卡组只读
    cc.add_card_to_deck(deck, cc.saved_card_id(path), cc.CARDS_PER_TEST_DECK)
    cc.save_deck(deck, decks_directory)
    cc.set_selected_deck(decks_directory, deck["deck_id"])
    print(f"已生成示例卡牌：{path}")
    print(f"卡面：〔{record['cost']} 费〕{record['title']} — {record['text']}")
    print(f"已加入卡组「{deck['name']}」（{cc.deck_size(deck)} 张），对局用它")
    return 0


def run_window(directory: Optional[Path | str] = None,
               decks_directory: Optional[Path | str] = None) -> None:
    """打开创作端窗口。"""
    root = tk.Tk()
    CardCreatorApp(root, directory, decks_directory)
    root.mainloop()


def main(argv: Optional[list[str]] = None) -> int:
    # Windows 控制台默认 GBK，直接打印中文会乱码
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="卡牌创作工坊（Tkinter 界面）")
    parser.add_argument("--dir", type=Path, default=None, help="卡牌目录（默认 user_cards/）")
    parser.add_argument("--decks-dir", type=Path, default=None, help="卡组目录（默认 user_decks/）")
    parser.add_argument("--list", action="store_true", help="只列出已保存的卡牌和卡组")
    parser.add_argument("--demo", action="store_true", help="生成一张示例卡后退出")
    args = parser.parse_args(argv)

    if args.list:
        return list_cards(args.dir, args.decks_dir)
    if args.demo:
        return create_sample(args.dir, args.decks_dir)
    print("正在打开卡牌创作工坊窗口……（关掉窗口即退出）")
    run_window(args.dir, args.decks_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
