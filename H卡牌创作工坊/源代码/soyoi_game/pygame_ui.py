"""战斗端界面（pygame）：只管画和收点击，数值都交给战斗框架算。"""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

if "--screenshot" in sys.argv:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from . import card_creator as cc
from . import resource_root
from .content.character import build_character, setup_soyoi_combat
from .content.enemies import enemy_catalog, make_enemy_by_name
from .core.cards import Card, CardRarity, CardType, PileType, RewardEffectOperation, TargetType
from .core.combat import CombatState
from .core.creature import Creature
from .core.enemy import Enemy, Intent, IntentAction
from .core.player import Player
from .soyoi.card import can_carry_materials, get_loadout
from .soyoi.material_runtime import equip_from_hand, gives_material, material_targets


WIDTH = 1280
HEIGHT = 720
FPS = 60
ROOT = resource_root()      # 只读资源（assets/）的根目录：打包成 exe 后指向解包目录
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "craft_club_room.png"
CHARACTER_PATH = ROOT / "assets" / "characters" / "soyoi_idle.webp"
# 卡面文件名 = 卡牌编号（soyoi_reward_001.webp 对应那张牌），
# 加新图不用改代码，按编号命名丢进来就行。
CARD_ART_DIR = ROOT / "assets" / "card_art"
MATERIAL_ART_NAME = "card"   # 素材牌共用的那张卡面（assets/card_art/card.webp）
MATERIAL_ART_PATH = CARD_ART_DIR / f"{MATERIAL_ART_NAME}.webp"
CARD_ART_PATHS = {
    path.stem: path
    for path in CARD_ART_DIR.glob("*.webp")
    if path.stem != MATERIAL_ART_NAME
}

# 敌人立绘：assets/enemies/<敌人编号>.png（或 .webp）。
# 8 只敌人的图都在仓库里；要重新出图跑 scripts/render_enemy_art.py。
ENEMY_ART_DIR = ROOT / "assets" / "enemies"

INK = (35, 40, 44)
PAPER = (239, 229, 207)
WHITE = (255, 255, 255)
TEAL = (36, 129, 132)
TEAL_DARK = (24, 73, 78)
CORAL = (218, 91, 75)
CORAL_DARK = (139, 54, 48)
YELLOW = (235, 177, 47)
BLUE = (65, 115, 158)
GREEN = (73, 153, 106)
MUTED = (176, 178, 166)
THREAD = (232, 216, 177)
PAPER_DARK = (203, 190, 163)
SHADOW = (11, 17, 24, 170)

CARD_COLORS = {
    CardType.ATTACK: (190, 72, 61),
    CardType.SKILL: (35, 119, 128),
    CardType.POWER: (176, 129, 45),
}

# 卡面上那行类型标签（中文名统一放这儿，画的时候按枚举取）
TYPE_LABELS = {
    CardType.ATTACK: "攻击",
    CardType.SKILL: "技能",
    CardType.POWER: "能力",
}
MATERIAL_TYPE_LABEL = "素材"

MATERIAL_COLORS = {
    "perler_color_pack": (236, 96, 102),
    "felt_scrap": (58, 155, 151),
    "button_battery": (238, 190, 62),
    "badge_blank": (104, 142, 193),
    "liquid_glue": (153, 105, 174),
    "self_sealing_bag": (90, 170, 102),
}

# 状态显示：显示名 + 颜色，键与 powers.Powers 一致。
STATUS_STYLE: dict[str, tuple[str, tuple[int, int, int]]] = {
    "Strength": ("力量", (232, 184, 76)),
    "Dexterity": ("敏捷", (104, 142, 193)),
    "Vulnerable": ("易伤", (218, 96, 83)),
    "Weak": ("虚弱", (153, 105, 174)),
    "Poison": ("中毒", (90, 170, 102)),
    "Thorns": ("荆棘", (146, 129, 100)),
    "Vigor": ("活力", (238, 190, 62)),
    "Plating": ("覆甲", (74, 121, 176)),
    "TempStrength": ("临时力量", (232, 184, 76)),
}

# 自制素材牌（card_id 不在上面的表里）用的默认配色：素材蓝紫
MATERIAL_FALLBACK_COLOR = (153, 105, 174)


def font(size: int, bold: bool = False) -> pygame.font.Font:
    names = ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"]
    return pygame.font.SysFont(names, size, bold=bold)


def draw_text(
    surface: pygame.Surface,
    text: str,
    size: int,
    color,
    pos,
    *,
    bold: bool = False,
    anchor: str = "topleft",
) -> pygame.Rect:
    image = font(size, bold).render(text, True, color)
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(image, rect)
    return rect


def wrap_text(text: str, max_width: int, size: int, max_lines: int = 4) -> list[str]:
    face = font(size)
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and face.size(candidate)[0] > max_width:
            lines.append(current)
            current = char
            if len(lines) == max_lines:
                break
        else:
            current = candidate
    if len(lines) < max_lines and current:
        lines.append(current)
    if len(lines) == max_lines and sum(len(line) for line in lines) < len(text):
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, color=(24, 31, 38, 220), border=MUTED) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, color, panel.get_rect(), border_radius=6)
    pygame.draw.rect(panel, border, panel.get_rect(), 1, border_radius=6)
    surface.blit(panel, rect)


def draw_bar(surface: pygame.Surface, rect: pygame.Rect, value: int, maximum: int, color) -> None:
    pygame.draw.rect(surface, (35, 40, 45), rect, border_radius=4)
    ratio = 0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
    fill = rect.copy()
    fill.width = round(rect.width * ratio)
    if fill.width:
        pygame.draw.rect(surface, color, fill, border_radius=4)
    pygame.draw.rect(surface, (225, 228, 230), rect, 1, border_radius=4)


def load_optional_image(path: Path) -> pygame.Surface | None:
    """读一张可选的图，没有就返回 None（缺图不该让程序起不来）。"""
    if not path.exists():
        return None
    return pygame.image.load(str(path)).convert_alpha()


def cover_scale(image: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """等比放大到铺满，再从中间裁一块，卡面就不会留黑边。"""
    target_w, target_h = size
    scale = max(target_w / image.get_width(), target_h / image.get_height())
    scaled = pygame.transform.smoothscale(
        image,
        (max(1, round(image.get_width() * scale)), max(1, round(image.get_height() * scale))),
    )
    crop = pygame.Rect(0, 0, target_w, target_h)
    crop.center = scaled.get_rect().center
    result = pygame.Surface(size, pygame.SRCALPHA)
    result.blit(scaled, (0, 0), crop)
    return result


def draw_stitches(surface: pygame.Surface, rect: pygame.Rect, color=THREAD, inset: int = 7) -> None:
    """沿着边画一圈虚线，看着像缝上去的。"""
    left, right = rect.left + inset, rect.right - inset
    top, bottom = rect.top + inset, rect.bottom - inset
    for x in range(left, right, 13):
        pygame.draw.line(surface, color, (x, top), (min(x + 7, right), top), 1)
        pygame.draw.line(surface, color, (x, bottom), (min(x + 7, right), bottom), 1)
    for y in range(top, bottom, 13):
        pygame.draw.line(surface, color, (left, y), (left, min(y + 7, bottom)), 1)
        pygame.draw.line(surface, color, (right, y), (right, min(y + 7, bottom)), 1)


def draw_cloth_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill,
    border=INK,
    *,
    stitch=THREAD,
    shadow: bool = True,
) -> None:
    """画一块布：底色 + 描边 + 缝线。"""
    if shadow:
        pygame.draw.rect(surface, (10, 15, 18, 135), rect.move(5, 6), border_radius=4)
    pygame.draw.rect(surface, border, rect.inflate(4, 4), border_radius=5)
    pygame.draw.rect(surface, fill, rect, border_radius=4)
    draw_stitches(surface, rect, stitch)


def draw_paper_panel(surface: pygame.Surface, rect: pygame.Rect, fill=PAPER, border=PAPER_DARK) -> None:
    """画一张边上撕过的纸。"""
    points = [
        (rect.left + 8, rect.top),
        (rect.right - 13, rect.top + 2),
        (rect.right, rect.top + 9),
        (rect.right - 3, rect.bottom - 7),
        (rect.right - 12, rect.bottom),
        (rect.left + 6, rect.bottom - 2),
        (rect.left, rect.bottom - 11),
        (rect.left + 3, rect.top + 7),
    ]
    pygame.draw.polygon(surface, (12, 17, 20, 120), [(x + 4, y + 5) for x, y in points])
    pygame.draw.polygon(surface, fill, points)
    pygame.draw.lines(surface, border, True, points, 2)


def draw_heart(surface: pygame.Surface, center: tuple[int, int], color=CORAL, scale: int = 12) -> None:
    x, y = center
    pygame.draw.circle(surface, color, (x - scale // 2, y - scale // 3), scale // 2)
    pygame.draw.circle(surface, color, (x + scale // 2, y - scale // 3), scale // 2)
    pygame.draw.polygon(
        surface,
        color,
        [(x - scale, y - scale // 3), (x + scale, y - scale // 3), (x, y + scale)],
    )


def draw_shield(surface: pygame.Surface, center: tuple[int, int], color=BLUE, scale: int = 13) -> None:
    x, y = center
    points = [(x, y - scale), (x + scale, y - scale // 2), (x + scale - 2, y + 5), (x, y + scale), (x - scale + 2, y + 5), (x - scale, y - scale // 2)]
    pygame.draw.polygon(surface, color, points)
    pygame.draw.lines(surface, PAPER, True, points, 2)


class PygameCombatDemo:
    def __init__(
        self,
        cards_dir: str | Path | None = None,
        *,
        use_user_cards: bool = True,
        enemy: str = "random",
        scripts_dir: str | Path | None = None,
        decks_dir: str | Path | None = None,
        deck: str = "",
    ) -> None:
        # 卡牌目录默认 user_cards/，卡组放 user_decks/（跟着 --cards-dir 走）
        self.cards_dir = cards_dir
        self.decks_dir = decks_dir
        self.deck_id = deck          # 指定用哪副卡组；空字符串 = 用创作端选中的那副
        self.deck_name = ""
        self.deck_size = 0
        self.deck_notes: list[str] = []
        self.use_user_cards = use_user_cards
        self.enemy_name = enemy  # 打谁：敌人编号、中文名、脚本敌人，或 "random"
        self.scripts_dir = scripts_dir
        self.user_card_titles: list[str] = []
        self.user_card_errors: list[str] = []
        self.script_errors: list[str] = []
        # 敌人脚本在开战前加载好（自带示例 + 命令行额外指定的目录）
        self.script_errors = cc.load_enemy_scripts([scripts_dir] if scripts_dir else None)
        pygame.init()
        pygame.display.set_caption("所依：酱油部作战 Demo")
        self.window = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        self.canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.clock = pygame.time.Clock()
        self.background = pygame.transform.smoothscale(
            pygame.image.load(str(BACKGROUND_PATH)).convert(), (WIDTH, HEIGHT)
        )
        character_source = load_optional_image(CHARACTER_PATH)
        self.character_art = (
            pygame.transform.smoothscale(character_source, (350, 350))
            if character_source is not None
            else None
        )
        self.card_art = {
            card_id: cover_scale(image, (128, 82))
            for card_id, path in CARD_ART_PATHS.items()
            if (image := load_optional_image(path)) is not None
        }
        material_source = load_optional_image(MATERIAL_ART_PATH)
        self.material_art = cover_scale(material_source, (128, 82)) if material_source is not None else None
        # 敌人立绘缓存：编号 -> 图片（None = 这只怪没有立绘）
        self._enemy_art: dict[str, pygame.Surface | None] = {}
        # 玩家自设卡面缓存：相对路径 -> 图片（None = 图读不了）
        self._user_card_art: dict[str, pygame.Surface | None] = {}
        self.card_rects: list[tuple[Card, pygame.Rect]] = []
        self._material_slots: list[tuple[Card, int, object, pygame.Rect]] = []
        self.enemy_rect = pygame.Rect(958, 151, 270, 270)
        self.end_turn_rect = pygame.Rect(1044, 27, 187, 82)
        # 换敌人：点按钮弹出「选择对手」浮层，点一行就换到那只
        self.switch_enemy_rect = pygame.Rect(864, 27, 168, 82)
        self.enemy_picker_rect = pygame.Rect(280, 96, 720, 500)
        self.enemy_picker_open = False
        self.enemy_row_rects: list[tuple[str, pygame.Rect]] = []   # (敌人编号, 这一行的位置)
        self.restart_rect = pygame.Rect(540, 405, 200, 54)
        self.selected_card: Card | None = None
        self.hovered_card: Card | None = None
        # 正在等玩家挑目标的那张素材牌（点它 -> 再点一张手牌就装上去了）
        self.pending_material: Card | None = None
        self.message = "选择一张牌"
        self.feedback = ""
        self.feedback_color = PAPER
        self.reset_combat()

    def reset_combat(self) -> None:
        """开一局新战斗：用哪副牌组由卡组决定（关掉自制卡时回到角色的起始牌组）。"""
        character = build_character()
        records = []
        self.user_card_errors = []
        if self.use_user_cards:
            # 自制卡从 JSON 读进来：先把坏文件跳过的原因记下来，再拼进卡组。
            records, self.user_card_errors = cc.load_cards(self.cards_dir)
        self.user_card_titles = [record["title"] for record in records]

        notes = []
        if not self.use_user_cards and not self.deck_id:
            # --no-user-cards：不碰玩家的卡和卡组，跑角色原本的起始牌组
            deck_name = f"{character.name}的起始牌组"
            specs = list(character.starting_deck)
        else:
            # 用哪副牌组：--deck 指定 > 创作端选中的 > 内置示例卡组
            deck_record, notes = cc.resolve_deck(self.cards_dir, self.decks_dir, self.deck_id)
            specs, missing = cc.deck_specs(deck_record, self.cards_dir)
            deck_name = deck_record["name"]
            if not specs:
                specs = list(character.starting_deck)
                deck_name = f"{character.name}的起始牌组"
                notes.append("卡组里没有可用的牌，已退回角色的起始牌组")
            elif missing:
                notes.append(f"卡组里有 {len(missing)} 个编号找不到卡牌，已跳过")
        self.deck_name = deck_name
        self.deck_size = len(specs)

        deck = [spec.create() for spec in specs]
        player = Player(name=character.name, max_hp=character.starting_hp, deck=deck)
        player.piles.rng.seed(2026)
        # 打谁由 --enemy 定：编号 / 中文名 / random（随机普通怪）
        opponent = make_enemy_by_name(self.enemy_name)
        self.combat = CombatState(player=player, enemies=[opponent], rng=random.Random(2026))
        setup_soyoi_combat(self.combat)
        self.combat.start_combat()
        self.combat.next_enemy_intents()
        self.selected_card = None
        self.hovered_card = None
        self.pending_material = None
        self.message = f"卡组「{self.deck_name}」：{self.deck_size} 张"
        if self.user_card_errors:
            self.message = "有卡牌无法读取，已跳过"
        if self.script_errors:
            self.message = f"有敌人脚本写错了（{len(self.script_errors)} 个），已跳过"
        self.deck_notes = notes
        self.feedback = ""
        self.feedback_color = PAPER

    @property
    def enemy(self) -> Enemy:
        return self.combat.enemies[0]

    def window_to_canvas(self, position: tuple[int, int]) -> tuple[int, int] | None:
        win_w, win_h = self.window.get_size()
        scale = min(win_w / WIDTH, win_h / HEIGHT)
        draw_w, draw_h = WIDTH * scale, HEIGHT * scale
        offset_x = (win_w - draw_w) / 2
        offset_y = (win_h - draw_h) / 2
        x, y = position
        if not (offset_x <= x <= offset_x + draw_w and offset_y <= y <= offset_y + draw_h):
            return None
        return round((x - offset_x) / scale), round((y - offset_y) / scale)

    def hand_layout(self, mouse_pos: tuple[int, int] | None = None) -> list[tuple[Card, pygame.Rect]]:
        cards = self.combat.player.piles.pile(PileType.HAND).cards
        if not cards:
            return []
        card_w, card_h = 156, 232
        step = min(143, (930 - card_w) / max(1, len(cards) - 1))
        total_w = card_w + step * (len(cards) - 1)
        start_x = (WIDTH - total_w) / 2
        result = []
        center_index = (len(cards) - 1) / 2
        for index, card in enumerate(cards):
            curve = round(abs(index - center_index) * 7)
            rect = pygame.Rect(round(start_x + index * step), 468 + curve, card_w, card_h)
            if card is self.selected_card:
                rect.y -= 26
            elif mouse_pos is not None and rect.collidepoint(mouse_pos):
                rect.y -= 13
            result.append((card, rect))
        return result

    def card_at(self, position: tuple[int, int]) -> Card | None:
        for card, rect in reversed(self.hand_layout(position)):
            if rect.collidepoint(position):
                return card
        return None

    def select_or_play(self, card: Card) -> None:
        # 素材牌不是"打出去"的：点它的意思是"我要把它装到某张手牌上"。
        if card.is_material:
            self.begin_material_choice(card)
            return
        # 带「生成素材」的牌必须先有地方装：手牌里没有别的可加工牌就不让打。
        if gives_material(card) and not material_targets(self.combat.player, exclude=card):
            self.selected_card = None
            self.message = "手牌里没有可以加工的牌，先留一张其他手牌再打它"
            return
        target = self.enemy if card.target in (TargetType.ANY_ENEMY, TargetType.ALL_ENEMIES) else self.combat.player
        try:
            self.combat.validate_card_play(card, target)
        except ValueError as exc:
            self.selected_card = None
            self.message = str(exc)
            return
        if card.target in (TargetType.ANY_ENEMY, TargetType.ALL_ENEMIES):
            self.selected_card = None if self.selected_card is card else card
            self.message = "选择敌人" if self.selected_card else "选择一张牌"
            return
        self.play_card(card, self.combat.player)

    # ---- 素材：先点素材牌，再点一张手牌 ----
    def material_choice_targets(self) -> list[Card]:
        """当前能接收素材的手牌（正在等玩家挑目标时才非空）。"""
        if self.pending_material is None:
            return []
        return material_targets(self.combat.player, exclude=self.pending_material)

    def begin_material_choice(self, material: Card) -> None:
        """进入"选择加工目标"状态；没有可选目标就当场说明原因。"""
        if not material_targets(self.combat.player, exclude=material):
            self.pending_material = None
            self.selected_card = None
            self.message = "手牌里没有可以加工的牌（素材牌本身不能再装素材）"
            return
        self.pending_material = material
        self.selected_card = None
        self.message = f"点一张手牌，把「{material.title}」加工上去"

    def cancel_material_choice(self) -> None:
        self.pending_material = None
        self.selected_card = None
        self.message = "选择一张牌"

    def choose_material_target(self, carrier: Card) -> None:
        """把待加工的素材装到玩家点中的这张牌上。"""
        material = self.pending_material
        if material is None:
            return
        equipped, note = equip_from_hand(
            self.combat.player, material, carrier, combat=self.combat
        )
        self.pending_material = None
        self.selected_card = None
        self.message = note
        if equipped:
            self.feedback = f"{carrier.title} 素材 +1"
            self.feedback_color = YELLOW
        else:
            self.feedback = ""

    def play_card(self, card: Card, target) -> None:
        old_enemy_hp = self.enemy.hp
        old_block = self.combat.player.block
        old_hp = self.combat.player.hp
        hand_before = {id(item) for item in self.combat.player.piles.pile(PileType.HAND).cards}
        try:
            self.combat.play_card(card, target)
        except ValueError as exc:
            self.message = str(exc)
            return
        damage = old_enemy_hp - self.enemy.hp
        block = self.combat.player.block - old_block
        healing = self.combat.player.hp - old_hp
        if damage > 0:
            self.feedback = f"敌人 -{damage} 生命"
            self.feedback_color = CORAL
        elif block > 0:
            self.feedback = f"所依 +{block} 格挡"
            self.feedback_color = BLUE
        elif healing > 0:
            self.feedback = f"所依 +{healing} 生命"
            self.feedback_color = GREEN
        else:
            self.feedback = ""
        self.selected_card = None
        self.message = f"已打出：{card.title}"
        # 「生成素材」的牌只发素材牌：告诉玩家接下来点它就能加工。
        gained = [
            item for item in self.combat.player.piles.pile(PileType.HAND).cards
            if id(item) not in hand_before and item.is_material
        ]
        if gained:
            self.message = f"获得素材牌「{gained[0].title}」：点它，再点一张手牌加工"
        if self.combat.phase == "victory":
            self.message = "制作完成"
        elif self.combat.phase == "defeat":
            self.message = "本次返工失败"

    def end_turn(self) -> None:
        if self.combat.phase != "player":
            return
        old_hp = self.combat.player.hp
        self.selected_card = None
        self.pending_material = None
        self.combat.end_player_turn()
        damage = old_hp - self.combat.player.hp
        if damage > 0:
            self.feedback = f"所依 -{damage} 生命"
            self.feedback_color = CORAL
        if self.combat.phase == "player":
            self.combat.next_enemy_intents()
            self.message = f"第 {self.combat.round_number} 回合"

    def switch_enemy(self, enemy_id: str = "") -> None:
        """换对手：给了编号就换到那一只，没给就换下一只（按清单循环）。"""
        choices = [item["enemy_id"] for item in enemy_catalog()]
        if not choices:
            self.feedback = "没有别的对手可换"
            self.feedback_color = CORAL
            return
        if enemy_id in choices:
            self.enemy_name = enemy_id
        else:
            current = self.enemy.enemy_id
            index = choices.index(current) if current in choices else -1
            self.enemy_name = choices[(index + 1) % len(choices)]
        self.reset_combat()
        self.feedback = f"换对手：{self.enemy.name}"
        self.feedback_color = YELLOW

    def toggle_enemy_picker(self) -> None:
        """打开 / 关掉「选择对手」浮层。"""
        self.enemy_picker_open = not self.enemy_picker_open
        self.selected_card = None            # 开着浮层的时候不留选中的手牌
        self.cancel_material_choice()

    def layout_enemy_rows(self) -> list[tuple[str, pygame.Rect]]:
        """算出"选择对手"浮层里每一行的位置 —— 画和点击共用同一份，保证点得准。"""
        items = enemy_catalog()
        panel = self.enemy_picker_rect
        columns = 2
        per_column = (len(items) + columns - 1) // columns
        row_width = (panel.width - 56 - 18) // columns
        row_height = 62
        layout: list[tuple[str, pygame.Rect]] = []
        for index, item in enumerate(items):
            column, line = divmod(index, per_column)
            layout.append((item["enemy_id"], pygame.Rect(
                panel.x + 28 + column * (row_width + 18),
                panel.y + 74 + line * (row_height + 10),
                row_width, row_height,
            )))
        self.enemy_row_rects = layout
        return layout

    def enemy_row_at(self, position: tuple[int, int]) -> str:
        """浮层里点到哪一行：返回那只敌人的编号，没点到就返回空字符串。"""
        if not self.enemy_row_rects:
            self.layout_enemy_rows()
        for enemy_id, rect in self.enemy_row_rects:
            if rect.collidepoint(position):
                return enemy_id
        return ""

    def handle_click(self, position: tuple[int, int]) -> None:
        if self.enemy_picker_open:            # 浮层开着时只认浮层里的点击，别穿透到牌桌上
            enemy_id = self.enemy_row_at(position)
            if enemy_id:
                self.enemy_picker_open = False
                self.switch_enemy(enemy_id)
            elif not self.enemy_picker_rect.collidepoint(position):
                self.enemy_picker_open = False        # 点面板外面 = 取消
            return
        if self.switch_enemy_rect.collidepoint(position):
            self.toggle_enemy_picker()        # 打完一局也能直接打开
            return
        if self.combat.phase in ("victory", "defeat"):
            if self.restart_rect.collidepoint(position):
                self.reset_combat()
            return
        # 正在挑加工目标：只认手牌，点空白处算取消。
        if self.pending_material is not None:
            card = self.card_at(position)
            if card is None:
                self.cancel_material_choice()
            else:
                self.choose_material_target(card)
            return
        if self.end_turn_rect.collidepoint(position):
            self.end_turn()
            return
        if self.selected_card is not None and self.enemy_rect.collidepoint(position):
            self.play_card(self.selected_card, self.enemy)
            return
        card = self.card_at(position)
        if card is not None:
            self.select_or_play(card)

    def update(self, dt: float) -> None:
        # 现在只有静态界面，留个 update 接口方便以后加动画。
        del dt

    def draw_background(self) -> None:
        self.canvas.blit(self.background, (0, 0))
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((10, 18, 22, 66))
        pygame.draw.rect(shade, (8, 13, 16, 188), (0, 452, WIDTH, 268))
        pygame.draw.line(shade, (222, 204, 163, 110), (0, 460), (WIDTH, 460), 4)
        self.canvas.blit(shade, (0, 0))

    def draw_header(self) -> None:
        player = self.combat.player

        energy_patch = pygame.Rect(29, 26, 207, 82)
        draw_cloth_panel(self.canvas, energy_patch, TEAL_DARK, (17, 43, 47), stitch=(185, 224, 219))
        pygame.draw.circle(self.canvas, YELLOW, (70, 67), 26)
        pygame.draw.polygon(self.canvas, INK, [(66, 48), (79, 48), (72, 63), (81, 63), (61, 88), (67, 69), (58, 69)])
        draw_text(self.canvas, f"{player.energy}/3", 28, PAPER, (112, 47), bold=True)
        draw_text(self.canvas, f"回合 {self.combat.round_number}", 14, (181, 220, 216), (113, 80))

        order = pygame.Rect(292, 25, 560, 84)
        draw_paper_panel(self.canvas, order)
        pygame.draw.circle(self.canvas, INK, (327, 66), 7, 2)
        pygame.draw.line(self.canvas, INK, (327, 47), (327, 85), 2)
        pygame.draw.line(self.canvas, INK, (308, 66), (346, 66), 2)
        draw_text(self.canvas, "酱油部作战", 15, TEAL_DARK, (360, 42), bold=True)
        draw_text(self.canvas, self.message, 20, INK, (360, 64), bold=True)
        if self.feedback:
            draw_text(self.canvas, self.feedback, 14, self.feedback_color, (824, 88), bold=True, anchor="bottomright")

        button_color = CORAL if self.end_turn_rect.collidepoint(self.current_mouse()) else CORAL_DARK
        draw_cloth_panel(self.canvas, self.end_turn_rect, button_color, (92, 34, 31), stitch=(255, 201, 178))
        pygame.draw.circle(self.canvas, PAPER, (1080, 68), 21, 3)
        pygame.draw.line(self.canvas, PAPER, (1068, 68), (1077, 77), 4)
        pygame.draw.line(self.canvas, PAPER, (1077, 77), (1092, 57), 4)
        draw_text(self.canvas, "结束回合", 19, PAPER, (1156, 67), bold=True, anchor="center")

    def draw_enemy_switch(self) -> None:
        """「换敌人」按钮：单独画在最后，所以结算浮层遮不住它，打完一局也能直接换。"""
        rect = self.switch_enemy_rect
        hovered = rect.collidepoint(self.current_mouse())
        draw_cloth_panel(self.canvas, rect, TEAL if hovered else TEAL_DARK, (17, 43, 47), stitch=(185, 224, 219))
        # 图标：一上一下两个箭头，表示"换一个"
        cx, cy = rect.x + 38, rect.centery
        pygame.draw.line(self.canvas, PAPER, (cx - 13, cy - 7), (cx + 11, cy - 7), 3)
        pygame.draw.polygon(self.canvas, PAPER, [(cx + 10, cy - 13), (cx + 10, cy - 1), (cx + 20, cy - 7)])
        pygame.draw.line(self.canvas, PAPER, (cx + 13, cy + 7), (cx - 11, cy + 7), 3)
        pygame.draw.polygon(self.canvas, PAPER, [(cx - 10, cy + 1), (cx - 10, cy + 13), (cx - 20, cy + 7)])
        draw_text(self.canvas, "换敌人", 18, PAPER, (rect.x + 114, cy), bold=True, anchor="center")

    def draw_player(self) -> None:
        player = self.combat.player

        if self.character_art is not None:
            self.canvas.blit(self.character_art, (210, 112))
        else:
            pygame.draw.circle(self.canvas, PAPER, (350, 255), 75)
            draw_text(self.canvas, "所依", 28, INK, (350, 255), bold=True, anchor="center")

        name_patch = pygame.Rect(38, 154, 202, 58)
        draw_cloth_panel(self.canvas, name_patch, TEAL, (16, 62, 65), stitch=(189, 226, 217))
        draw_text(self.canvas, "所依", 25, PAPER, (60, 167), bold=True)
        draw_text(self.canvas, "酱油部", 13, (194, 231, 224), (176, 184), anchor="center")

        stat_paper = pygame.Rect(38, 220, 218, 170)
        draw_paper_panel(self.canvas, stat_paper)
        draw_heart(self.canvas, (66, 259), CORAL, 13)
        hp_rect = pygame.Rect(88, 247, 145, 23)
        draw_bar(self.canvas, hp_rect, player.hp, player.max_hp, CORAL)
        draw_text(self.canvas, f"{player.hp}/{player.max_hp}", 14, WHITE, hp_rect.center, bold=True, anchor="center")

        pygame.draw.line(self.canvas, PAPER_DARK, (58, 291), (235, 291), 2)
        draw_shield(self.canvas, (67, 319), BLUE, 13)
        draw_text(self.canvas, "格挡", 15, INK, (91, 309), bold=True)
        draw_text(self.canvas, str(player.block), 20, BLUE, (224, 307), bold=True, anchor="topright")

        pygame.draw.line(self.canvas, PAPER_DARK, (58, 345), (235, 345), 2)
        draw_text(self.canvas, "状态", 13, TEAL_DARK, (60, 357), bold=True)
        self.draw_statuses(player, 106, 353, max_width=126, line_height=20)

    def draw_enemy(self) -> None:
        target = self.enemy_rect
        if self.selected_card is not None:  # 选中手牌时高亮敌人，提示"可以打它"
            glow = pygame.Surface((target.width + 24, target.height + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow, (238, 184, 76, 90), glow.get_rect(), border_radius=6)
            self.canvas.blit(glow, (target.x - 12, target.y - 12))

        draw_cloth_panel(self.canvas, target, TEAL_DARK, (13, 46, 50), stitch=(224, 186, 88))

        # 名字 + 出场台词：让每只怪有性格（Boss 换阶段时会换一句）
        draw_text(self.canvas, self.enemy.name, 22, PAPER, (target.centerx, 166), bold=True, anchor="center")
        flavor = self.enemy.flavor
        if self.enemy.phase >= 2:
            flavor = "第二阶段：它开始不顾一切地砸。"
        if flavor:
            draw_text(self.canvas, flavor, 12, (196, 214, 210), (target.centerx, 192), anchor="center")

        # 主体：立绘（assets/enemies/<敌人编号>.png）
        portrait = self.enemy_portrait()
        if portrait is not None:
            art_rect = pygame.Rect(target.x + 24, target.y + 54, target.width - 48, 176)
            self.canvas.blit(cover_scale(portrait, art_rect.size), art_rect.topleft)

        hp_rect = pygame.Rect(986, 377, 214, 22)
        draw_bar(self.canvas, hp_rect, self.enemy.hp, self.enemy.max_hp, CORAL)
        draw_text(self.canvas, f"{self.enemy.hp}/{self.enemy.max_hp}", 14, WHITE, hp_rect.center, bold=True, anchor="center")

        self.draw_statuses(self.enemy, 987, 405, max_width=210, line_height=20)
        self.draw_intent()

    def enemy_portrait(self) -> pygame.Surface | None:
        """取当前敌人的立绘（第一次用到时才读文件，之后走缓存）。"""
        enemy_id = self.enemy.enemy_id
        if not enemy_id:
            return None
        if enemy_id not in self._enemy_art:
            image = None
            for suffix in (".png", ".webp"):
                image = load_optional_image(ENEMY_ART_DIR / f"{enemy_id}{suffix}")
                if image is not None:
                    break
            self._enemy_art[enemy_id] = image
        return self._enemy_art[enemy_id]

    def card_art_for(self, card: Card) -> pygame.Surface | None:
        """一张牌的卡面插画：玩家自己设的优先，其次按编号找到的那张，都没有返回 None。"""
        if card.art:
            if card.art not in self._user_card_art:
                path = cc.find_card_art(card.art, self.cards_dir)
                image = load_optional_image(path) if path else None
                self._user_card_art[card.art] = cover_scale(image, (128, 82)) if image else None
            if self._user_card_art[card.art] is not None:
                return self._user_card_art[card.art]
        return self.card_art.get(card.card_id) or (self.material_art if card.is_material else None)

    # 三种意图的配色：攻击红、防御蓝、强化金
    INTENT_STYLE = {
        IntentAction.ATTACK: ("攻击", CORAL_DARK, (232, 132, 114)),
        IntentAction.DEFEND: ("防御", (52, 84, 120), (140, 178, 220)),
        IntentAction.BUFF: ("强化", (122, 92, 24), (238, 190, 62)),
        IntentAction.UNKNOWN: ("未知", (70, 72, 74), MUTED),
    }

    def draw_intent(self) -> None:
        """画敌人下回合要做什么 —— 攻击 / 防御 / 强化，这是最核心的信息展示。"""
        intent = self.enemy.intent
        name, text_color, chip_color = self.INTENT_STYLE.get(intent.action, self.INTENT_STYLE[IntentAction.UNKNOWN])

        panel = pygame.Rect(760, 172, 186, 96)
        draw_paper_panel(self.canvas, panel, (223, 211, 183), (132, 113, 82))
        draw_text(self.canvas, "下回合意图", 12, TEAL_DARK, (panel.centerx, panel.y + 8), bold=True, anchor="midtop")

        # 图标：攻击画刀、防御画盾、强化画向上箭头
        icon_center = (panel.x + 30, panel.centery + 8)
        if intent.action == IntentAction.ATTACK:
            pygame.draw.polygon(self.canvas, chip_color, [
                (icon_center[0] - 4, icon_center[1] - 14), (icon_center[0] + 4, icon_center[1] - 14),
                (icon_center[0] + 4, icon_center[1] + 6), (icon_center[0], icon_center[1] + 14),
                (icon_center[0] - 4, icon_center[1] + 6),
            ])
        elif intent.action == IntentAction.DEFEND:
            draw_shield(self.canvas, icon_center, chip_color, 12)
        elif intent.action == IntentAction.BUFF:
            pygame.draw.polygon(self.canvas, chip_color, [
                (icon_center[0], icon_center[1] - 14), (icon_center[0] + 12, icon_center[1] + 2),
                (icon_center[0] + 4, icon_center[1] + 2), (icon_center[0] + 4, icon_center[1] + 13),
                (icon_center[0] - 4, icon_center[1] + 13), (icon_center[0] - 4, icon_center[1] + 2),
                (icon_center[0] - 12, icon_center[1] + 2),
            ])
        else:
            pygame.draw.rect(self.canvas, chip_color, (icon_center[0] - 11, icon_center[1] - 11, 22, 22), border_radius=4)

        # 类别标签 + 具体数值 + 附加效果提示
        draw_text(self.canvas, name, 12, chip_color, (panel.x + 52, panel.y + 24), bold=True)
        draw_text(self.canvas, intent.text, 17, text_color, (panel.x + 52, panel.y + 45), bold=True)
        extra = self.intent_extra_text(intent)
        if extra:
            draw_text(self.canvas, extra, 11, (110, 96, 70), (panel.x + 52, panel.y + 68))
        pygame.draw.line(self.canvas, PAPER, (panel.right, panel.centery), (self.enemy_rect.x + 8, panel.centery), 4)

    @staticmethod
    def intent_extra_text(intent) -> str:
        """攻击附带的额外效果，单独一行提示玩家（比如"附带虚弱"）。"""
        names = {
            RewardEffectOperation.APPLY_WEAK: "虚弱",
            RewardEffectOperation.APPLY_VULNERABLE: "易伤",
            RewardEffectOperation.LOSE_HP: "掉血",
        }
        parts = []
        if intent.effect_operation is not None:
            parts.append(f"附带{names.get(intent.effect_operation, '状态')}")
        if intent.card_spec is not None:
            parts.append(f"塞{intent.hits}张铁屑")
        return "、".join(parts)

    def draw_piles(self) -> None:
        piles = self.combat.player.piles
        items = [
            ("抽牌", len(piles.pile(PileType.DRAW).cards), pygame.Rect(30, 522, 78, 112), TEAL_DARK),
            ("弃牌", len(piles.pile(PileType.DISCARD).cards), pygame.Rect(1171, 504, 76, 104), CORAL_DARK),
            ("消耗", len(piles.pile(PileType.EXHAUST).cards), pygame.Rect(1171, 615, 76, 84), (65, 67, 69)),
        ]
        for label, count, rect, color in items:
            for offset in (8, 4):
                pygame.draw.rect(self.canvas, INK, rect.move(offset, -offset), border_radius=4)
                pygame.draw.rect(self.canvas, PAPER_DARK, rect.move(offset, -offset), 1, border_radius=4)
            draw_cloth_panel(self.canvas, rect, color, (13, 34, 36), stitch=THREAD, shadow=False)
            cx, cy = rect.centerx, rect.centery - 10
            pygame.draw.polygon(self.canvas, PAPER, [(cx, cy - 17), (cx + 17, cy), (cx, cy + 17), (cx - 17, cy)])
            pygame.draw.polygon(self.canvas, color, [(cx, cy - 8), (cx + 8, cy), (cx, cy + 8), (cx - 8, cy)])
            count_rect = pygame.Rect(rect.right - 18, rect.bottom - 20, 36, 30)
            pygame.draw.circle(self.canvas, INK, count_rect.center, 18)
            draw_text(self.canvas, str(count), 18, PAPER, count_rect.center, bold=True, anchor="center")
            draw_text(self.canvas, label, 12, PAPER, (rect.centerx, rect.bottom - 19), bold=True, anchor="center")

    def draw_statuses(self, creature: Creature, x: int, y: int, *, max_width: int = 280, align: str = "left", line_height: int = 22) -> None:
        """渲染一个生物当前持有的状态（力量/易伤/虚弱等）为一行小胶囊。"""
        powers = creature.powers
        # 负力量等也需要显示，避免实际伤害与界面状态不符。
        active = [(k, v.amount) for k, v in powers.items() if v.amount != 0]
        if not active:
            return y
        # 按 key 排序，保证稳定展示顺序
        active.sort(key=lambda kv: kv[0])
        cursor = x
        for key, amount in active:
            label = STATUS_STYLE.get(key, (key, MUTED))[0]
            color = STATUS_STYLE.get(key, (key, MUTED))[1]
            text = f"{label} {amount}"
            image = font(13).render(text, True, (255, 255, 255))
            w, h = image.get_size()
            pad_x, pad_y = 6, 3
            pill_w, pill_h = w + pad_x * 2, h + pad_y * 2
            if cursor + pill_w > x + max_width:
                break
            rect = pygame.Rect(cursor, y, pill_w, pill_h)
            pygame.draw.rect(self.canvas, (*color, 235), rect, border_radius=pill_h // 2)
            pygame.draw.rect(self.canvas, (255, 255, 255), rect, 1, border_radius=pill_h // 2)
            self.canvas.blit(image, image.get_rect(center=rect.center))
            cursor += pill_w + 6
        return y + line_height

    def draw_material_tooltip(self, mouse: tuple[int, int]) -> None:
        """鼠标悬停在素材圆圈上时显示该素材的效果说明。"""
        for card, slot, bundle, slot_rect in self._material_slots:
            if not slot_rect.collidepoint(mouse):
                continue
            # 收集该槽素材组件的效果文本
            title = card.title
            comp_texts = []
            for comp in bundle.components:
                text = comp.effect_text or comp.text
                comp_texts.append((comp.title, comp.category_text, text))
            if not comp_texts:
                return
            lines = [f"素材槽 {slot + 1}：{title}"]
            for cname, cat, text in comp_texts:
                lines.append(f"{cat}{(' ' + text) if text else ''}")
            # draw tooltip panel near the slot
            self._draw_tooltip_panel(slot_rect.x + slot_rect.width, slot_rect.y - 8, lines)
            return

    def _draw_tooltip_panel(self, x: int, y: int, lines: list[str]) -> None:
        """绘制一个简易 tooltip 浮层。"""
        pad = 8
        widths = [font(14).size(line)[0] for line in lines]
        h = len(lines) * 20 + pad * 2
        w = max(widths) + pad * 2
        w = min(w, 300)
        # clamp to screen
        if x + w > WIDTH - 8:
            x = WIDTH - 8 - w
        if y + h > HEIGHT - 8:
            y = HEIGHT - 8 - h
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.canvas, (24, 31, 38, 240), rect, border_radius=6)
        pygame.draw.rect(self.canvas, (238, 184, 76), rect, 1, border_radius=6)
        yy = rect.y + pad
        for i, line in enumerate(lines):
            color = (176, 129, 45) if i == 0 else (240, 240, 240)
            draw_text(self.canvas, line, 14, color, (rect.x + pad, yy), anchor="topleft")
            yy += 20

    def draw_card(self, card: Card, rect: pygame.Rect, hovered: bool) -> None:
        # 素材牌用素材色画，和普通牌一眼能分开。
        is_material = card.is_material
        color = (
            MATERIAL_COLORS.get(card.card_id, MATERIAL_FALLBACK_COLOR)
            if is_material else CARD_COLORS[card.card_type]
        )
        shadow = rect.move(6, 7)
        pygame.draw.rect(self.canvas, (7, 11, 13), shadow, border_radius=5)
        pygame.draw.rect(self.canvas, INK, rect.inflate(6, 6), border_radius=6)
        pygame.draw.rect(self.canvas, color, rect, border_radius=4)
        draw_stitches(self.canvas, rect, (231, 210, 168), inset=6)

        body = pygame.Rect(rect.x + 9, rect.y + 34, rect.width - 18, rect.height - 44)
        pygame.draw.rect(self.canvas, PAPER, body, border_radius=3)
        pygame.draw.rect(self.canvas, PAPER_DARK, body, 2, border_radius=3)

        title_strip = pygame.Rect(rect.x + 28, rect.y + 7, rect.width - 36, 34)
        draw_paper_panel(self.canvas, title_strip, (244, 234, 211), PAPER_DARK)
        draw_text(self.canvas, card.title, 15, INK, (title_strip.centerx + 4, title_strip.centery), bold=True, anchor="center")

        pygame.draw.circle(self.canvas, YELLOW, (rect.x + 23, rect.y + 22), 19)
        pygame.draw.circle(self.canvas, (111, 74, 27), (rect.x + 23, rect.y + 22), 19, 2)
        draw_text(self.canvas, str(card.cost), 18, INK, (rect.x + 23, rect.y + 21), bold=True, anchor="center")

        art_rect = pygame.Rect(rect.x + 14, rect.y + 46, rect.width - 28, 82)
        # 素材牌没有各自的插画，统一用那张共用的素材卡面。
        art = self.card_art_for(card)
        if art is not None:
            self.canvas.blit(art, art_rect)
        else:
            # 没有插画的牌用"卡片本色压暗"当底，素材牌因此也一眼能认出来
            pygame.draw.rect(self.canvas, tuple(max(0, channel - 62) for channel in color), art_rect)
            pygame.draw.line(self.canvas, THREAD, art_rect.topleft, art_rect.bottomright, 3)
            pygame.draw.line(self.canvas, THREAD, art_rect.topright, art_rect.bottomleft, 3)
        pygame.draw.rect(self.canvas, INK, art_rect, 2)

        type_label = MATERIAL_TYPE_LABEL if is_material else TYPE_LABELS[card.card_type]
        type_chip = pygame.Rect(rect.centerx - 27, rect.y + 120, 54, 22)
        pygame.draw.rect(self.canvas, (246, 238, 220), type_chip, border_radius=4)
        pygame.draw.rect(self.canvas, color, type_chip, 1, border_radius=4)
        draw_text(self.canvas, type_label, 12, color, type_chip.center, bold=True, anchor="center")
        text_lines = wrap_text(card.text, rect.width - 30, 13, 3)
        for line_no, line in enumerate(text_lines):
            draw_text(self.canvas, line, 13, INK, (rect.x + 15, rect.y + 148 + line_no * 18))

        # 素材牌标出类别（一次性/普通/永久/诅咒），它自己不能再承载素材。
        if is_material:
            category = card.category_text
            chip = pygame.Rect(rect.x + 15, rect.bottom - 32, 78, 22)
            pygame.draw.rect(self.canvas, (246, 238, 220), chip, border_radius=4)
            pygame.draw.rect(self.canvas, color, chip, 1, border_radius=4)
            draw_text(self.canvas, f"{category}素材", 12, color, chip.center, bold=True, anchor="center")
            self._draw_selection_frame(card, rect, hovered)
            return

        loadout = get_loadout(card) if can_carry_materials(card) else None
        for slot in range(3 if loadout is not None else 0):
            center = (rect.x + 49 + slot * 29, rect.bottom - 18)
            bundle = loadout.slots[slot]
            if bundle is None:
                slot_box = pygame.Rect(center[0] - 10, center[1] - 10, 20, 20)
                pygame.draw.rect(self.canvas, (222, 214, 197), slot_box, border_radius=4)
                pygame.draw.rect(self.canvas, (151, 148, 139), slot_box, 1, border_radius=4)
            else:
                material_id = bundle.components[0].card_id
                pygame.draw.rect(self.canvas, MATERIAL_COLORS.get(material_id, TEAL), (center[0] - 10, center[1] - 10, 20, 20), border_radius=4)
                pygame.draw.rect(self.canvas, INK, (center[0] - 10, center[1] - 10, 20, 20), 1, border_radius=4)
                # 记录素材槽的可悬停区域（供 material tooltip 使用）
                slot_rect = pygame.Rect(center[0] - 10, center[1] - 10, 20, 20)
                self._material_slots.append((card, slot, bundle, slot_rect))

        # 追加素材效果描述：在卡面正文后追加该牌已装备素材的效果文本（金色）
        if loadout is not None and loadout.material_count > 0:
            effects = []
            for b in loadout.slots:
                if b is None:
                    continue
                for comp in b.components:
                    text = comp.effect_text or comp.text
                    if text:
                        effects.append(text)
            if effects:
                y_pos = rect.y + 148 + len(text_lines) * 18 + 3
                for line in wrap_text("◆ " + "；".join(effects), rect.width - 30, 12, 2):
                    draw_text(self.canvas, line, 12, (151, 105, 30), (rect.x + 15, y_pos))
                    y_pos += 16

        rarity_marks = {CardRarity.BASIC: 0, CardRarity.COMMON: 1, CardRarity.UNCOMMON: 2, CardRarity.RARE: 3}.get(card.rarity, 0)
        for index in range(rarity_marks):
            pygame.draw.polygon(
                self.canvas,
                YELLOW,
                [(rect.right - 13 - index * 9, rect.bottom - 25), (rect.right - 9 - index * 9, rect.bottom - 21), (rect.right - 13 - index * 9, rect.bottom - 17), (rect.right - 17 - index * 9, rect.bottom - 21)],
            )

        self._draw_selection_frame(card, rect, hovered)

    def _draw_selection_frame(self, card: Card, rect: pygame.Rect, hovered: bool) -> None:
        """选中/悬停边框。正在挑加工目标时，只高亮"能装"的那些牌。"""
        if self.pending_material is not None:
            if card is self.pending_material:
                pygame.draw.rect(self.canvas, YELLOW, rect.inflate(6, 6), 3, border_radius=6)
            elif any(card is target for target in self.material_choice_targets()):
                pygame.draw.rect(self.canvas, GREEN, rect.inflate(6, 6), 3, border_radius=6)
            return
        if hovered or card is self.selected_card:
            pygame.draw.rect(self.canvas, YELLOW, rect.inflate(4, 4), 3, border_radius=6)

    def draw_hand(self) -> None:
        mouse = self.current_mouse()
        self.card_rects = self.hand_layout(mouse)
        self._material_slots.clear()
        self.hovered_card = None
        for card, rect in self.card_rects:
            hovered = rect.collidepoint(mouse)
            if hovered:
                self.hovered_card = card
            self.draw_card(card, rect, hovered)
        # 鼠标悬停在素材槽上时，绘制素材效果 tooltip
        self.draw_material_tooltip(mouse)
        self.draw_hand_material_hint()

    def draw_hand_material_hint(self) -> None:
        """鼠标停在素材牌上时，提示"点它再点一张手牌"这个操作。"""
        card = self.hovered_card
        if card is None or not card.is_material:
            return
        draw_text(
            self.canvas, "点这张素材牌，再点一张手牌，就能加工上去", 15, PAPER,
            (WIDTH // 2, 450), bold=True, anchor="midbottom",
        )

    def draw_overlay(self) -> None:
        if self.combat.phase not in ("victory", "defeat"):
            return
        cover = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        cover.fill((8, 13, 18, 185))
        self.canvas.blit(cover, (0, 0))
        title = "制作完成" if self.combat.phase == "victory" else "本次返工失败"
        color = YELLOW if self.combat.phase == "victory" else CORAL
        draw_text(self.canvas, title, 42, color, (WIDTH // 2, 315), bold=True, anchor="center")
        pygame.draw.rect(self.canvas, TEAL, self.restart_rect, border_radius=6)
        pygame.draw.rect(self.canvas, (163, 222, 219), self.restart_rect, 1, border_radius=6)
        draw_text(self.canvas, "重新开始", 20, WHITE, self.restart_rect.center, bold=True, anchor="center")

    def draw_enemy_picker(self) -> None:
        """「选择对手」浮层：两列列出所有敌人（编号 / 名字 / 生命 / 档位），点一行就开打。"""
        if not self.enemy_picker_open:
            return
        cover = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        cover.fill((8, 13, 18, 190))
        self.canvas.blit(cover, (0, 0))

        panel = self.enemy_picker_rect
        draw_paper_panel(self.canvas, panel)
        items = enemy_catalog()
        layout = self.layout_enemy_rows()
        draw_text(self.canvas, "选择对手", 24, TEAL_DARK, (panel.x + 28, panel.y + 26), bold=True)
        draw_text(self.canvas, f"共 {len(items)} 只　·　点一行就开打，牌组不变",
                  14, (95, 90, 78), (panel.right - 28, panel.y + 32), anchor="topright")

        current = self.enemy.enemy_id
        mouse = self.current_mouse()
        for item, (enemy_id, rect) in zip(items, layout):
            hovered = rect.collidepoint(mouse)
            is_current = enemy_id == current
            fill = (226, 240, 238) if hovered else (244, 240, 230)
            pygame.draw.rect(self.canvas, fill, rect, border_radius=6)
            border = TEAL if hovered or is_current else (206, 198, 180)
            pygame.draw.rect(self.canvas, border, rect, 2 if (hovered or is_current) else 1, border_radius=6)
            draw_text(self.canvas, item["name"], 19, TEAL_DARK, (rect.x + 16, rect.y + 12), bold=True)
            draw_text(self.canvas, item["enemy_id"], 12, (128, 122, 110), (rect.x + 16, rect.y + 38))
            draw_text(self.canvas, f"生命 {item['hp']}", 14, INK, (rect.right - 16, rect.y + 14), anchor="topright")
            tag = "正在打" if is_current else item["kind"]
            tag_color = YELLOW if is_current else (120, 150, 146)
            draw_text(self.canvas, tag, 13, tag_color, (rect.right - 16, rect.y + 38),
                      bold=is_current, anchor="topright")

        draw_text(self.canvas, "点面板外面或按 Esc 取消", 14, (120, 114, 102),
                  (panel.centerx, panel.bottom - 24), anchor="midbottom")

    def current_mouse(self) -> tuple[int, int]:
        mapped = self.window_to_canvas(pygame.mouse.get_pos())
        return mapped or (-1000, -1000)

    def draw(self) -> None:
        self.draw_background()
        self.draw_header()
        self.draw_player()
        self.draw_enemy()
        self.draw_piles()
        self.draw_hand()
        self.draw_overlay()
        self.draw_enemy_switch()
        self.draw_enemy_picker()

    def present(self) -> None:
        win_w, win_h = self.window.get_size()
        scale = min(win_w / WIDTH, win_h / HEIGHT)
        target_size = (max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale)))
        frame = pygame.transform.smoothscale(self.canvas, target_size)
        self.window.fill((8, 12, 16))
        self.window.blit(frame, ((win_w - target_size[0]) // 2, (win_h - target_size[1]) // 2))
        pygame.display.flip()

    def run(self) -> None:
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.enemy_picker_open:               # 先关浮层，再退选目标，最后才是关窗口
                            self.toggle_enemy_picker()
                        elif self.pending_material is not None:
                            self.cancel_material_choice()
                        else:
                            running = False
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if not self.enemy_picker_open:
                            self.end_turn()
                    elif event.key == pygame.K_r and self.combat.phase in ("victory", "defeat"):
                        self.reset_combat()
                    elif event.key == pygame.K_e:
                        self.toggle_enemy_picker()
                    elif pygame.K_1 <= event.key <= pygame.K_9 and not self.enemy_picker_open:
                        index = event.key - pygame.K_1
                        hand = self.combat.player.piles.pile(PileType.HAND).cards
                        if index < len(hand):
                            if self.pending_material is not None:
                                self.choose_material_target(hand[index])
                            else:
                                self.select_or_play(hand[index])
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mapped = self.window_to_canvas(event.pos)
                    if mapped is not None:
                        self.handle_click(mapped)
            self.update(dt)
            self.draw()
            self.present()
        pygame.quit()


def run(argv: list[str] | None = None) -> None:
    """战斗界面入口：python main.py --battle"""
    from .content.enemies import enemy_list

    parser = argparse.ArgumentParser(
        description="所依卡牌战斗界面（pygame）",
        epilog=enemy_list(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--screenshot", type=Path, help="渲染一帧并保存 PNG 后退出")
    parser.add_argument("--cards-dir", type=Path, default=None, help="卡牌目录，默认 user_cards/")
    parser.add_argument("--decks-dir", type=Path, default=None, help="卡组目录，默认 user_decks/")
    parser.add_argument("--deck", default="", help="用哪副卡组（编号或名字；默认用创作端选中的那副）")
    parser.add_argument("--enemy", default="random", help="打哪个敌人（编号 / 中文名 / random）")
    parser.add_argument("--scripts", type=Path, default=None, help="额外的敌人脚本目录")
    parser.add_argument(
        "--no-user-cards",
        action="store_true",
        help="不加载自制卡，只用角色原本的起始牌组",
    )
    args = parser.parse_args(argv)
    demo = PygameCombatDemo(
        cards_dir=args.cards_dir,
        use_user_cards=not args.no_user_cards,
        enemy=args.enemy,
        scripts_dir=args.scripts,
        decks_dir=args.decks_dir,
        deck=args.deck,
    )
    demo.draw()
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(demo.canvas, str(args.screenshot))
        pygame.quit()
        return
    demo.run()


if __name__ == "__main__":  # pragma: no cover
    run()
