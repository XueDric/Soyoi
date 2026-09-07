"""文本界面的战斗循环 (可玩 demo)。

对应 C# 的 UI 层（图片/卡牌/点击）。这里用纯文本实现，方便：
- 验证核心逻辑
- 队友开发时用文本快速试牌
- 之后换成 pygame/Godot 只替换本层

运行：python -m soyoi_game
"""

from __future__ import annotations

import sys

from ..core.cards import Card, PileType, CardType, CardKeyword
from ..core.player import Player
from ..core.enemy import Enemy, Intent, IntentAction
from ..core.combat import CombatState
from ..content.character import build_character, instantiate_deck, setup_soyoi_combat


def make_player() -> Player:
    char_def = build_character()
    deck = instantiate_deck(char_def)
    return Player(
        name=char_def.name,
        max_hp=char_def.starting_hp,
        deck=deck,
    )


def make_enemy(name: str = "垃圾怪", hp: int = 20, pattern=None) -> Enemy:
    if pattern is None:
        pattern = [
            Intent(IntentAction.ATTACK, 6, 1, "攻击 6"),
            Intent(IntentAction.DEFEND, 5, 1, "防御 5"),
            Intent(IntentAction.ATTACK, 8, 1, "攻击 8"),
        ]
    e = Enemy(name=name, max_hp=hp, act_pattern=pattern)
    e.intent = pattern[0]
    return e


def describe_loadout(card: Card) -> str:
    """渲染卡牌的素材位信息。"""
    from ..soyoi.card import can_carry_materials, get_loadout
    if not can_carry_materials(card):
        return ""
    loadout = get_loadout(card)
    if loadout.material_count == 0:
        return ""
    parts = []
    for i, b in enumerate(loadout.slots):
        if b is None:
            continue
        effects = " ".join(describe_material_effect(e) for comp in b.components for e in comp.material_effects)
        parts.append(f"[{i+1}]{effects}")
    return f"[素材 {loadout.material_count}/3: " + "; ".join(parts) + "]"


def describe_material_effect(effect) -> str:
    from ..soyoi.materials_render import describe_material_effect as d
    return d(effect)


def show_state(combat: CombatState) -> None:
    p = combat.player
    print("=" * 50)
    print(f"回合 {combat.round_number} | 阶段 {combat.phase}")
    print(f"你: 生命 {p.hp}/{p.max_hp} 格挡 {p.block} 能量 {p.energy}/{p.max_energy}")
    print(f"  状态: " + ", ".join(f"{k}={v}" for k, v in p.powers.items() if v) or "无")
    for e in combat.enemies:
        if e.is_dead():
            print(f"敌人[{e.name}]: 已击败")
        else:
            print(f"敌人[{e.name}]: 生命 {e.hp}/{e.max_hp} 格挡 {e.block} 意图 {e.intent.text}")
            print(f"  状态: " + ", ".join(f"{k}={v}" for k, v in e.powers.items() if v) or "无")
    hand = p.piles.pile(PileType.HAND)
    print(f"手牌 ({len(hand.cards)}):")
    for i, c in enumerate(hand.cards):
        extra = describe_loadout(c)
        print(f"  [{i}] {c.title} 费{c.cost} {c.text} {'(升级)' if c.upgraded else ''} {extra}")
    print(f"抽牌堆 {len(p.piles.pile(PileType.DRAW).cards)} | 弃牌堆 {len(p.piles.pile(PileType.DISCARD).cards)} | 消耗 {len(p.piles.pile(PileType.EXHAUST).cards)}")
    print("=" * 50)


def parse_choice(combat: CombatState) -> bool:
    """解析玩家输入。返回是否继续。"""
    hand = combat.player.piles.pile(PileType.HAND)
    text = input("> 输入 [牌号] 出牌 (多个目标可加 -t 目标号)；[e]结束回合；[q]退出: ").strip()
    if text in ("q", "quit"):
        return False
    if text in ("e", "end"):
        combat.end_player_turn()
        return True
    parts = text.split()
    try:
        idx = int(parts[0])
        target_idx = None
        if "-t" in parts:
            target_idx = int(parts[parts.index("-t") + 1])
        card = hand.cards[idx]
        target = None
        living = combat.living_enemies
        if card.target in (2, 3):  # ANY_ENEMY / ALL_ENEMIES
            if living:
                target = living[min(target_idx or 0, len(living) - 1)]
        combat.play_card(card, target)
    except (ValueError, IndexError) as e:
        print(f"无效输入: {e}")
    return True


def run() -> None:
    print("进入《所依》文本战斗 demo。")
    player = make_player()
    enemy = make_enemy()
    combat = CombatState(player=player, enemies=[enemy])
    combat.next_enemy_intents()
    setup_soyoi_combat(combat)

    combat.start_combat()
    show_state(combat)

    while True:
        if not combat.has_living_enemy:
            print(">>> 胜利！")
            break
        if combat.player.is_dead():
            print(">>> 失败！")
            break
        if not parse_choice(combat):
            break
        show_state(combat)


if __name__ == "__main__":
    run()
