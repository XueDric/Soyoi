"""所依卡牌战斗的 pygame 可视化 Demo。"""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path

if "--screenshot" in sys.argv:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from ..content.character import build_character, setup_soyoi_combat
from ..content.soyoi_cards import PLAYABLE_REWARD_CARDS
from ..core.cards import Card, CardRarity, CardType, PileType, TargetType
from ..core.combat import CombatState
from ..core.enemy import Enemy, Intent, IntentAction
from ..core.player import Player
from ..soyoi.card import get_loadout


WIDTH = 1280
HEIGHT = 720
FPS = 60
ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_PATH = ROOT / "assets" / "backgrounds" / "craft_club_room.png"

INK = (30, 36, 43)
PAPER = (246, 244, 238)
WHITE = (255, 255, 255)
TEAL = (37, 132, 140)
TEAL_DARK = (24, 86, 94)
CORAL = (218, 96, 83)
CORAL_DARK = (142, 54, 49)
YELLOW = (232, 184, 76)
BLUE = (74, 121, 176)
GREEN = (73, 153, 106)
MUTED = (173, 184, 190)
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


@dataclass
class FloatText:
    text: str
    position: pygame.Vector2
    color: tuple[int, int, int]
    lifetime: float = 1.0

    def update(self, dt: float) -> None:
        self.lifetime -= dt
        self.position.y -= 36 * dt


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
        self.card_rects: list[tuple[Card, pygame.Rect]] = []
        self.enemy_rect = pygame.Rect(785, 155, 255, 245)
        self.end_turn_rect = pygame.Rect(1090, 72, 152, 50)
        self.restart_rect = pygame.Rect(540, 405, 200, 54)
        self.selected_card: Card | None = None
        self.hovered_card: Card | None = None
        self.message = "选择一张牌"
        self.float_texts: list[FloatText] = []
        self.flash = 0.0
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
        self.float_texts.clear()
        self.flash = 0.0

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
        card_w, card_h = 144, 214
        step = min(158, (1130 - card_w) / max(1, len(cards) - 1))
        total_w = card_w + step * (len(cards) - 1)
        start_x = (WIDTH - total_w) / 2
        result = []
        for index, card in enumerate(cards):
            rect = pygame.Rect(round(start_x + index * step), 493, card_w, card_h)
            if card is self.selected_card:
                rect.y -= 28
            elif mouse_pos is not None and rect.collidepoint(mouse_pos):
                rect.y -= 14
            result.append((card, rect))
        return result

    def card_at(self, position: tuple[int, int]) -> Card | None:
        for card, rect in reversed(self.hand_layout(position)):
            if rect.collidepoint(position):
                return card
        return None

    def select_or_play(self, card: Card) -> None:
        if card.cost > self.combat.player.energy:
            self.message = f"能量不足：需要 {card.cost} 点"
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
            self.float_texts.append(FloatText(f"-{damage}", pygame.Vector2(908, 195), CORAL))
            self.flash = 0.16
        if block > 0:
            self.float_texts.append(FloatText(f"+{block} 格挡", pygame.Vector2(257, 343), BLUE))
        if healing > 0:
            self.float_texts.append(FloatText(f"+{healing}", pygame.Vector2(230, 298), GREEN))
        self.selected_card = None
        self.message = f"已打出：{card.title}"
        if self.enemy.is_dead():
            self.combat.phase = "victory"
            self.message = "制作完成"

    def end_turn(self) -> None:
        if self.combat.phase != "player":
            return
        old_hp = self.combat.player.hp
        self.selected_card = None
        self.combat.end_player_turn()
        damage = old_hp - self.combat.player.hp
        if damage > 0:
            self.float_texts.append(FloatText(f"-{damage}", pygame.Vector2(232, 292), CORAL))
            self.flash = 0.14
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
        self.flash = max(0.0, self.flash - dt)
        for item in self.float_texts:
            item.update(dt)
        self.float_texts = [item for item in self.float_texts if item.lifetime > 0]

    def draw_background(self) -> None:
        self.canvas.blit(self.background, (0, 0))
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((12, 20, 28, 42))
        pygame.draw.rect(shade, (9, 14, 20, 170), (0, 455, WIDTH, 265))
        self.canvas.blit(shade, (0, 0))

    def draw_header(self) -> None:
        draw_panel(self.canvas, pygame.Rect(32, 24, 1216, 112), (22, 30, 36, 226), (104, 136, 142))
        draw_text(self.canvas, "SOYOI", 30, WHITE, (58, 44), bold=True)
        draw_text(self.canvas, "酱油部作战", 16, (171, 216, 216), (59, 84))
        draw_text(self.canvas, f"回合 {self.combat.round_number}", 18, PAPER, (265, 49), bold=True)
        draw_text(self.canvas, self.message, 17, YELLOW, (265, 82))

        button_color = CORAL if self.end_turn_rect.collidepoint(self.current_mouse()) else CORAL_DARK
        pygame.draw.rect(self.canvas, button_color, self.end_turn_rect, border_radius=6)
        pygame.draw.rect(self.canvas, (255, 187, 174), self.end_turn_rect, 1, border_radius=6)
        draw_text(self.canvas, "结束回合", 19, WHITE, self.end_turn_rect.center, bold=True, anchor="center")

    def draw_player(self) -> None:
        panel = pygame.Rect(48, 164, 310, 238)
        draw_panel(self.canvas, panel, (21, 31, 38, 225), (86, 157, 162))
        pygame.draw.circle(self.canvas, (217, 237, 234), (116, 232), 46)
        pygame.draw.circle(self.canvas, TEAL_DARK, (116, 232), 45, 3)
        pygame.draw.circle(self.canvas, (57, 74, 82), (116, 220), 25)
        pygame.draw.arc(self.canvas, (57, 74, 82), (80, 210, 72, 76), 0, 3.14, 26)
        draw_text(self.canvas, "所依", 25, WHITE, (184, 185), bold=True)
        draw_text(self.canvas, "酱油部", 15, (174, 207, 207), (185, 220))

        player = self.combat.player
        hp_rect = pygame.Rect(78, 300, 245, 20)
        draw_bar(self.canvas, hp_rect, player.hp, player.max_hp, CORAL)
        draw_text(self.canvas, f"生命 {player.hp}/{player.max_hp}", 15, WHITE, hp_rect.center, bold=True, anchor="center")
        pygame.draw.rect(self.canvas, BLUE, (78, 335, 116, 42), border_radius=6)
        draw_text(self.canvas, f"格挡 {player.block}", 17, WHITE, (136, 356), bold=True, anchor="center")
        pygame.draw.circle(self.canvas, YELLOW, (269, 356), 25)
        draw_text(self.canvas, str(player.energy), 22, INK, (269, 355), bold=True, anchor="center")
        draw_text(self.canvas, "能量", 13, PAPER, (304, 349), anchor="midleft")

    def draw_enemy(self) -> None:
        target = self.enemy_rect
        selected = self.selected_card is not None
        if selected:
            glow = pygame.Surface((target.width + 24, target.height + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow, (238, 184, 76, 60), glow.get_rect(), border_radius=8)
            self.canvas.blit(glow, (target.x - 12, target.y - 12))

        # 由简单几何图形组成的废料怪，保持课程项目可自行修改。
        pygame.draw.ellipse(self.canvas, (10, 16, 20, 110), (792, 347, 240, 42))
        pygame.draw.rect(self.canvas, (106, 77, 62), (825, 222, 168, 132), border_radius=6)
        pygame.draw.rect(self.canvas, (173, 125, 78), (842, 190, 132, 70), border_radius=5)
        pygame.draw.line(self.canvas, (237, 190, 82), (858, 190), (885, 260), 8)
        pygame.draw.line(self.canvas, (237, 190, 82), (960, 190), (932, 260), 8)
        pygame.draw.circle(self.canvas, (246, 239, 214), (878, 228), 13)
        pygame.draw.circle(self.canvas, (246, 239, 214), (938, 228), 13)
        pygame.draw.circle(self.canvas, INK, (878, 228), 5)
        pygame.draw.circle(self.canvas, INK, (938, 228), 5)
        pygame.draw.line(self.canvas, INK, (883, 292), (936, 292), 5)
        pygame.draw.line(self.canvas, (128, 161, 164), (825, 285), (992, 285), 3)

        if self.flash > 0:
            overlay = pygame.Surface(target.size, pygame.SRCALPHA)
            overlay.fill((255, 236, 210, int(150 * self.flash / 0.16)))
            self.canvas.blit(overlay, target)

        draw_text(self.canvas, self.enemy.name, 23, WHITE, (target.centerx, 145), bold=True, anchor="midbottom")
        hp_rect = pygame.Rect(805, 374, 210, 20)
        draw_bar(self.canvas, hp_rect, self.enemy.hp, self.enemy.max_hp, CORAL)
        draw_text(self.canvas, f"{self.enemy.hp}/{self.enemy.max_hp}", 14, WHITE, hp_rect.center, bold=True, anchor="center")
        intent_rect = pygame.Rect(1048, 172, 170, 72)
        draw_panel(self.canvas, intent_rect, (26, 36, 42, 225), (173, 190, 191))
        draw_text(self.canvas, "下一步", 13, MUTED, (intent_rect.centerx, 183), anchor="midtop")
        draw_text(self.canvas, self.enemy.intent.text, 18, YELLOW, (intent_rect.centerx, 216), bold=True, anchor="center")

    def draw_piles(self) -> None:
        piles = self.combat.player.piles
        items = [
            ("抽牌", len(piles.pile(PileType.DRAW).cards), 35),
            ("弃牌", len(piles.pile(PileType.DISCARD).cards), 1127),
            ("消耗", len(piles.pile(PileType.EXHAUST).cards), 1192),
        ]
        for label, count, x in items:
            rect = pygame.Rect(x, 637, 56, 62)
            pygame.draw.rect(self.canvas, (31, 42, 49), rect, border_radius=5)
            pygame.draw.rect(self.canvas, (142, 159, 164), rect, 1, border_radius=5)
            draw_text(self.canvas, str(count), 20, WHITE, (rect.centerx, rect.y + 20), bold=True, anchor="center")
            draw_text(self.canvas, label, 12, MUTED, (rect.centerx, rect.bottom - 12), anchor="center")

    def draw_card(self, card: Card, rect: pygame.Rect, hovered: bool) -> None:
        color = CARD_COLORS[card.card_type]
        shadow = rect.move(5, 7)
        pygame.draw.rect(self.canvas, (8, 12, 16), shadow, border_radius=7)
        pygame.draw.rect(self.canvas, PAPER, rect, border_radius=7)
        pygame.draw.rect(self.canvas, color, (rect.x, rect.y, rect.width, 47), border_top_left_radius=7, border_top_right_radius=7)
        pygame.draw.rect(self.canvas, YELLOW if card is self.selected_card else color, rect, 3 if hovered or card is self.selected_card else 2, border_radius=7)

        pygame.draw.circle(self.canvas, (251, 211, 93), (rect.x + 22, rect.y + 22), 17)
        draw_text(self.canvas, str(card.cost), 18, INK, (rect.x + 22, rect.y + 21), bold=True, anchor="center")
        draw_text(self.canvas, card.title, 17, WHITE, (rect.centerx + 8, rect.y + 23), bold=True, anchor="center")

        type_label = {CardType.ATTACK: "攻击", CardType.SKILL: "技能", CardType.POWER: "能力"}[card.card_type]
        draw_text(self.canvas, type_label, 12, color, (rect.centerx, rect.y + 61), bold=True, anchor="center")
        for line_no, line in enumerate(wrap_text(card.text, rect.width - 20, 14, 4)):
            draw_text(self.canvas, line, 14, INK, (rect.x + 10, rect.y + 82 + line_no * 21))

        loadout = get_loadout(card)
        for slot in range(3):
            center = (rect.x + 48 + slot * 25, rect.bottom - 20)
            bundle = loadout.slots[slot]
            if bundle is None:
                pygame.draw.circle(self.canvas, (178, 184, 183), center, 8, 2)
            else:
                material_id = bundle.components[0].card_id
                pygame.draw.circle(self.canvas, MATERIAL_COLORS.get(material_id, TEAL), center, 9)
                pygame.draw.circle(self.canvas, INK, center, 9, 1)

        rarity_marks = {CardRarity.BASIC: 0, CardRarity.COMMON: 1, CardRarity.UNCOMMON: 2, CardRarity.RARE: 3}.get(card.rarity, 0)
        for index in range(rarity_marks):
            pygame.draw.circle(self.canvas, YELLOW, (rect.right - 12 - index * 10, rect.bottom - 12), 3)

    def draw_hand(self) -> None:
        mouse = self.current_mouse()
        self.card_rects = self.hand_layout(mouse)
        for card, rect in self.card_rects:
            self.draw_card(card, rect, rect.collidepoint(mouse))

    def draw_float_texts(self) -> None:
        for item in self.float_texts:
            alpha = max(0, min(255, round(255 * item.lifetime)))
            image = font(24, True).render(item.text, True, item.color)
            image.set_alpha(alpha)
            self.canvas.blit(image, image.get_rect(center=(round(item.position.x), round(item.position.y))))

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
        self.draw_float_texts()
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
