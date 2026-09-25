"""卡牌创作工坊 —— 程序入口（选一个模式运行）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def run_battle(args) -> int:
    """打开战斗界面。"""
    from soyoi_game.pygame_ui import run as run_battle_ui

    argv = []
    if args.cards_dir:
        argv += ["--cards-dir", str(args.cards_dir)]
    if args.decks_dir:
        argv += ["--decks-dir", str(args.decks_dir)]
    if args.deck:
        argv += ["--deck", args.deck]
    if args.enemy:
        argv += ["--enemy", args.enemy]
    if args.scripts:
        argv += ["--scripts", str(args.scripts)]
    if args.no_user_cards:
        argv.append("--no-user-cards")
    if args.screenshot:
        argv += ["--screenshot", str(args.screenshot)]
    run_battle_ui(argv)
    return 0


def run_creator(args) -> int:
    """打开造牌界面（--list / --demo 则走命令行分支）。"""
    from soyoi_game.tkinter_ui import create_sample, list_cards, run_window

    if args.list:
        return list_cards(args.cards_dir, args.decks_dir)
    if args.demo:
        return create_sample(args.cards_dir, args.decks_dir)
    print("正在打开卡牌创作工坊……（关掉窗口即退出）")
    run_window(args.cards_dir, args.decks_dir)
    return 0


def run_check(args) -> int:
    """不开窗口的自检：确认战斗框架、自制卡与卡组加载、出牌结算都能走通。"""
    from soyoi_game import card_creator as cc
    from soyoi_game.core.cards import PileType

    cards_dir = args.cards_dir
    records, errors = cc.load_cards(cards_dir)
    script_errors = cc.load_enemy_scripts([args.scripts] if args.scripts else None)
    deck, notes = cc.resolve_deck(cards_dir, args.decks_dir, args.deck)
    specs, missing = cc.deck_specs(deck, cards_dir)
    print(f"卡牌目录：{cc.cards_folder(cards_dir)}")
    print(f"读到的自制卡：{[record['title'] for record in records] or '（无）'}")
    print(f"卡组目录：{cc.decks_folder(args.decks_dir)}")
    print(f"这一局用：{cc.describe_deck(deck)}")
    for note in notes:
        print(f"  [提示] {note}")
    for card_id in missing:
        print(f"  [跳过] 卡组里的 {card_id} 找不到对应卡牌")
    for error in errors + script_errors:
        print(f"  [跳过] {error}")

    combat = cc.build_combat(cards_dir, args.decks_dir, args.deck,
                             enemy=args.enemy, scripts_dir=args.scripts)
    combat.start_combat()
    hand = combat.player.piles.pile(PileType.HAND).cards
    enemy = combat.enemies[0]
    print(f"战斗已开始：牌组 {len(combat.player.deck)} 张（卡组里 {len(specs)} 张），手牌 {len(hand)} 张")
    print(f"对手：{enemy.name}　生命 {enemy.hp}/{enemy.max_hp}　首回合意图：{enemy.intent.text}")
    print("自检通过：数据、创作端、卡组、战斗框架之间的连接是通的。")
    return 0


def run_enemies(args=None) -> int:
    """列出所有可选敌人（含脚本里加载的）。"""
    from soyoi_game import card_creator as cc
    from soyoi_game.content.enemies import enemy_list

    scripts = args.scripts if args else None       # args 可以不传：测试会直接调 run_enemies()
    cc.load_enemy_scripts([scripts] if scripts else None)  # 先把脚本里的敌人注册进来
    print(enemy_list())
    print("\n用法：python main.py --battle --enemy cultist")
    return 0


def run_scripts_list(args) -> int:
    """列出脚本里能加载出来的敌人，以及写错的脚本。"""
    from soyoi_game.content.enemy_scripts import load_default_scripts, load_script_list

    report = load_script_list([str(args.scripts)] if args.scripts else None)
    if not args.scripts:  # 没指定目录时看仓库自带的示例
        report = load_default_scripts()
    print(report.summary())
    print("\n用法：python main.py --battle --enemy <上面的名字>")
    return 0 if report.ok else 1


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="卡牌创作工坊：自己造卡牌，再进对局验证效果",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="不带参数运行 = 打开造牌界面。",
    )
    parser.add_argument("--battle", action="store_true", help="打开战斗界面（pygame）")
    parser.add_argument("--demo", action="store_true", help="生成一张示例卡「重击」后退出")
    parser.add_argument("--list", action="store_true", help="列出已经保存的卡牌与卡组")
    parser.add_argument("--check", action="store_true", help="自检：跑通数据 -> 卡组 -> 战斗的连接")
    parser.add_argument("--enemies", action="store_true", help="列出所有可选敌人")
    parser.add_argument("--scripts-list", action="store_true", help="列出敌人脚本里的敌人")
    parser.add_argument("--enemy", default="random", help="打哪个敌人（编号 / 中文名 / random，默认随机）")
    parser.add_argument("--scripts", type=Path, default=None, help="额外的敌人脚本目录（.txt）")
    parser.add_argument("--cards-dir", type=Path, default=None, help="卡牌目录，默认 user_cards/")
    parser.add_argument("--decks-dir", type=Path, default=None, help="卡组目录，默认 user_decks/")
    parser.add_argument("--deck", default="", help="用哪副卡组（编号或名字；默认用创作端选中的那副）")
    parser.add_argument("--no-user-cards", action="store_true", help="战斗时不加载自制卡")
    parser.add_argument("--screenshot", type=Path, default=None, help="战斗界面截图后退出")
    args = parser.parse_args(argv)

    if args.scripts_list:
        return run_scripts_list(args)
    if args.enemies:
        return run_enemies(args)
    if args.check:
        return run_check(args)
    if args.battle or args.screenshot:
        return run_battle(args)
    return run_creator(args)


if __name__ == "__main__":
    raise SystemExit(main())
