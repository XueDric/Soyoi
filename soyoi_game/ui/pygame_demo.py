"""所依卡牌战斗的 pygame 可视化 Demo。"""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

if "--screenshot" in sys.argv:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from ..content.character import build_character, setup_soyoi_combat
from ..content.soyoi_cards import PLAYABLE_REWARD_CARDS
from ..core.cards import Card, CardRarity, CardType, PileType, TargetType
from ..core.combat import CombatState
from ..core.creature import Creature
from ..core.enemy import Enemy, Intent, IntentAction
from ..core.player import Player
from ..soyoi.card import can_carry_materials, get_loadout


WIDTH = 1280
HEIGHT = 720
FPS = 60
ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "craft_club_room.png"
CHARACTER_PATH = ROOT / "assets" / "characters" / "soyoi_idle.webp"
CARD_ART_DIR = ROOT / "assets" / "card_art"

CARD_ART_PATHS = {
    "strike_soyoi": CARD_ART_DIR / "strike_soyoi.webp",
    "soyoi_reward_001": CARD_ART_DIR / "soyoi_reward_001.webp",
    "soyoi_reward_013": CARD_ART_DIR / "soyoi_reward_013.webp",
    "soyoi_reward_016": CARD_ART_DIR / "soyoi_reward_016.webp",
    "soyoi_reward_026": CARD_ART_DIR / "soyoi_reward_026.webp",
}

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

MATERIAL_COLORS = {
    "perler_color_pack": (236, 96, 102),
    "felt_scrap": (58, 155, 151),
    "button_battery": (238, 190, 62),
    "badge_blank": (104, 142, 193),
    "liquid_glue": (153, 105, 174),
    "self_sealing_bag": (90, 170, 102),
}

# 状态（Power）显示：显示名 + 颜色。键与前缀 powers.Powers 一致。
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
    """Load an optional art asset without making the demo unbootable."""
    if not path.exists():
        return None
    return pygame.image.load(str(path)).convert_alpha()


def cover_scale(image: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """Scale and center-crop an image to fill a fixed UI slot."""
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
    """Draw a simple dashed seam around a cloth panel."""
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
    """Draw a layered fabric patch inspired by the reference UI."""
    if shadow:
        pygame.draw.rect(surface, (10, 15, 18, 135), rect.move(5, 6), border_radius=4)
    pygame.draw.rect(surface, border, rect.inflate(4, 4), border_radius=5)
    pygame.draw.rect(surface, fill, rect, border_radius=4)
    draw_stitches(surface, rect, stitch)


def draw_paper_panel(surface: pygame.Surface, rect: pygame.Rect, fill=PAPER, border=PAPER_DARK) -> None:
    """Draw a deterministic torn-paper silhouette."""
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
    def __init__(self) -> None:
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
        self.card_rects: list[tuple[Card, pygame.Rect]] = []
        self._material_slots: list[tuple[Card, int, object, pygame.Rect]] = []
        self.enemy_rect = pygame.Rect(958, 151, 270, 270)
        self.end_turn_rect = pygame.Rect(1044, 27, 187, 82)
        self.restart_rect = pygame.Rect(540, 405, 200, 54)
        self.selected_card: Card | None = None
        self.hovered_card: Card | None = None
        self.message = "选择一张牌"
        self.feedback = ""
        self.feedback_color = PAPER
        self.reset_combat()

    def reset_combat(self) -> None:
        character = build_character()
        reward_indexes = (0, 3, 6, 10, 12, 15, 20, 24)
        specs = character.starting_deck + [PLAYABLE_REWARD_CARDS[i] for i in reward_indexes]
        deck = [spec.create() for spec in specs]
        player = Player(name=character.name, max_hp=character.starting_hp, deck=deck)
        player.piles.rng.seed(2026)
        pattern = [
            Intent(IntentAction.ATTACK, 7, label="敲击 7"),
            Intent(IntentAction.DEFEND, 6, label="加固 6"),
            Intent(IntentAction.ATTACK, 5, hits=2, label="连击 5×2"),
        ]
        enemy = Enemy(name="废料怪", max_hp=86, act_pattern=pattern, intent=pattern[0])
        self.combat = CombatState(player=player, enemies=[enemy], rng=random.Random(2026))
        setup_soyoi_combat(self.combat)
        self.combat.start_combat()
        self.combat.next_enemy_intents()
        self.selected_card = None
        self.hovered_card = None
        self.message = "选择一张牌"
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

    def play_card(self, card: Card, target) -> None:
        old_enemy_hp = self.enemy.hp
        old_block = self.combat.player.block
        old_hp = self.combat.player.hp
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
        self.selected_card = None
        self.message = f"已打出：{card.title}"
        if self.combat.phase == "victory":
            self.message = "制作完成"
        elif self.combat.phase == "defeat":
            self.message = "本次返工失败"

    def end_turn(self) -> None:
        if self.combat.phase != "player":
            return
        old_hp = self.combat.player.hp
        self.selected_card = None
        self.combat.end_player_turn()
        damage = old_hp - self.combat.player.hp
        if damage > 0:
            self.feedback = f"所依 -{damage} 生命"
            self.feedback_color = CORAL
        if self.combat.phase == "player":
            self.combat.next_enemy_intents()
            self.message = f"第 {self.combat.round_number} 回合"

    def handle_click(self, position: tuple[int, int]) -> None:
        if self.combat.phase in ("victory", "defeat"):
            if self.restart_rect.collidepoint(position):
                self.reset_combat()
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
        # 当前阶段使用纯静态 UI；保留 update 接口便于后续课程迭代动画。
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

        order = pygame.Rect(292, 25, 684, 84)
        draw_paper_panel(self.canvas, order)
        pygame.draw.circle(self.canvas, INK, (327, 66), 7, 2)
        pygame.draw.line(self.canvas, INK, (327, 47), (327, 85), 2)
        pygame.draw.line(self.canvas, INK, (308, 66), (346, 66), 2)
        draw_text(self.canvas, "酱油部作战", 15, TEAL_DARK, (360, 42), bold=True)
        draw_text(self.canvas, self.message, 20, INK, (360, 64), bold=True)
        if self.feedback:
            draw_text(self.canvas, self.feedback, 14, self.feedback_color, (929, 88), bold=True, anchor="bottomright")

        button_color = CORAL if self.end_turn_rect.collidepoint(self.current_mouse()) else CORAL_DARK
        draw_cloth_panel(self.canvas, self.end_turn_rect, button_color, (92, 34, 31), stitch=(255, 201, 178))
        pygame.draw.circle(self.canvas, PAPER, (1080, 68), 21, 3)
        pygame.draw.line(self.canvas, PAPER, (1068, 68), (1077, 77), 4)
        pygame.draw.line(self.canvas, PAPER, (1077, 77), (1092, 57), 4)
        draw_text(self.canvas, "结束回合", 19, PAPER, (1156, 67), bold=True, anchor="center")

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
        selected = self.selected_card is not None
        if selected:
            glow = pygame.Surface((target.width + 24, target.height + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow, (238, 184, 76, 90), glow.get_rect(), border_radius=6)
            self.canvas.blit(glow, (target.x - 12, target.y - 12))

        draw_cloth_panel(self.canvas, target, TEAL_DARK, (13, 46, 50), stitch=(224, 186, 88))
        draw_text(self.canvas, self.enemy.name, 22, PAPER, (target.centerx, 168), bold=True, anchor="center")

        # 原创的纸箱废料怪，只保留课程 Demo 所需的敌人占位表现。
        pygame.draw.ellipse(self.canvas, (10, 16, 20, 115), (984, 338, 216, 32))
        pygame.draw.rect(self.canvas, (99, 75, 65), (1000, 250, 188, 105), border_radius=5)
        pygame.draw.rect(self.canvas, (172, 119, 75), (1016, 212, 156, 73), border_radius=4)
        pygame.draw.line(self.canvas, YELLOW, (1034, 213), (1053, 282), 8)
        pygame.draw.line(self.canvas, YELLOW, (1154, 213), (1134, 282), 8)
        pygame.draw.circle(self.canvas, PAPER, (1052, 247), 13)
        pygame.draw.circle(self.canvas, PAPER, (1135, 247), 13)
        pygame.draw.circle(self.canvas, INK, (1052, 247), 5)
        pygame.draw.circle(self.canvas, INK, (1135, 247), 5)
        pygame.draw.line(self.canvas, INK, (1065, 315), (1123, 315), 5)

        hp_rect = pygame.Rect(986, 377, 214, 22)
        draw_bar(self.canvas, hp_rect, self.enemy.hp, self.enemy.max_hp, CORAL)
        draw_text(self.canvas, f"{self.enemy.hp}/{self.enemy.max_hp}", 14, WHITE, hp_rect.center, bold=True, anchor="center")

        self.draw_statuses(self.enemy, 987, 405, max_width=210, line_height=20)

        intent_rect = pygame.Rect(792, 178, 145, 83)
        draw_paper_panel(self.canvas, intent_rect, (223, 211, 183), (132, 113, 82))
        draw_text(self.canvas, "敌方意图", 13, TEAL_DARK, (intent_rect.centerx, 190), bold=True, anchor="midtop")
        draw_text(self.canvas, self.enemy.intent.text, 19, CORAL_DARK, (intent_rect.centerx, 231), bold=True, anchor="center")
        pygame.draw.line(self.canvas, PAPER, (937, 220), (958, 220), 4)

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
        """渲染一个生物当前持有的状态（力量/易伤/虚弱等）为一行小胶囊。

        align="left" 从左往右排，align="center" 居中排。返回绘制到的 y。
        """
        powers = getattr(creature, "powers", {})
        # 负力量等也需要显示，避免实际伤害与界面状态不符。
        active = [(k, v.amount) for k, v in powers.items() if getattr(v, "amount", 0) != 0]
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
            title = getattr(card, "title", "牌")
            comp_texts = []
            for comp in bundle.components:
                text = getattr(comp, "effect_text", "") or getattr(comp, "text", "")
                cat = getattr(comp, "category_text", "")
                comp_texts.append((comp.title if hasattr(comp, "title") else "素材", cat, text))
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
        color = CARD_COLORS[card.card_type]
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
        art = self.card_art.get(card.card_id)
        if art is not None:
            self.canvas.blit(art, art_rect)
        else:
            pygame.draw.rect(self.canvas, TEAL_DARK, art_rect)
            pygame.draw.line(self.canvas, THREAD, art_rect.topleft, art_rect.bottomright, 3)
            pygame.draw.line(self.canvas, THREAD, art_rect.topright, art_rect.bottomleft, 3)
        pygame.draw.rect(self.canvas, INK, art_rect, 2)

        type_label = {CardType.ATTACK: "攻击", CardType.SKILL: "技能", CardType.POWER: "能力"}[card.card_type]
        type_chip = pygame.Rect(rect.centerx - 27, rect.y + 120, 54, 22)
        pygame.draw.rect(self.canvas, (246, 238, 220), type_chip, border_radius=4)
        pygame.draw.rect(self.canvas, color, type_chip, 1, border_radius=4)
        draw_text(self.canvas, type_label, 12, color, type_chip.center, bold=True, anchor="center")
        text_lines = wrap_text(card.text, rect.width - 30, 13, 3)
        for line_no, line in enumerate(text_lines):
            draw_text(self.canvas, line, 13, INK, (rect.x + 15, rect.y + 148 + line_no * 18))

        # 素材 Token 可以在手牌中展示，但不能再承载素材。
        if not can_carry_materials(card):
            return
        loadout = get_loadout(card)
        for slot in range(3):
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
        if loadout.material_count > 0:
            effects = []
            for b in loadout.slots:
                if b is None:
                    continue
                for comp in b.components:
                    text = getattr(comp, "effect_text", "") or getattr(comp, "text", "")
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

        if hovered or card is self.selected_card:
            pygame.draw.rect(self.canvas, YELLOW, rect.inflate(4, 4), 3, border_radius=6)

    def draw_hand(self) -> None:
        mouse = self.current_mouse()
        self.card_rects = self.hand_layout(mouse)
        self._material_slots.clear()
        for card, rect in self.card_rects:
            self.draw_card(card, rect, rect.collidepoint(mouse))
        # 鼠标悬停在素材槽上时，绘制素材效果 tooltip
        self.draw_material_tooltip(mouse)

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
                        running = False
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.end_turn()
                    elif event.key == pygame.K_r and self.combat.phase in ("victory", "defeat"):
                        self.reset_combat()
                    elif pygame.K_1 <= event.key <= pygame.K_9:
                        index = event.key - pygame.K_1
                        hand = self.combat.player.piles.pile(PileType.HAND).cards
                        if index < len(hand):
                            self.select_or_play(hand[index])
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mapped = self.window_to_canvas(event.pos)
                    if mapped is not None:
                        self.handle_click(mapped)
            self.update(dt)
            self.draw()
            self.present()
        pygame.quit()


def run() -> None:
    parser = argparse.ArgumentParser(description="所依 pygame 可视化战斗 Demo")
    parser.add_argument("--screenshot", type=Path, help="渲染一帧并保存 PNG 后退出")
    args = parser.parse_args()
    demo = PygameCombatDemo()
    demo.draw()
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(demo.canvas, str(args.screenshot))
        pygame.quit()
        return
    demo.run()


if __name__ == "__main__":
    run()
