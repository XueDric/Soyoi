#端到端复刻审计：造出来的卡进战斗后，数值和效果是否真的对得上。
from __future__ import annotations

import random
import shutil
import sys
import uuid
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):   # Windows 控制台默认 GBK，打印中文会乱码
    sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from soyoi_game import card_creator as cc
from soyoi_game.content.character import ASK_AROUND_SPEC
from soyoi_game.core.cards import CardKeyword, PileType, TargetType
from soyoi_game.core.enemy import Enemy, Intent, IntentAction
from soyoi_game.soyoi.card import get_loadout
from soyoi_game.soyoi.material_runtime import equip_from_hand

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, actual, expected) -> None:
    global CHECKS
    CHECKS += 1
    if actual != expected:
        FAILURES.append(f"{label}: 实际 {actual!r} != 期望 {expected!r}")


def _clean_starting_hand(combat) -> None:
    #把起始遗物白送的素材牌清掉，好让"这张牌生成了几张素材"算得准
    combat.on_player_turn_start = [cb for cb in combat.on_player_turn_start
                                   if cb.__name__ != "badge_turn_start"]
    for token in [c for c in combat.player.piles.pile(PileType.HAND).cards
                  if getattr(c, "is_material", False)]:
        combat.player.piles.exhaust(token)


def add_dummy_enemy(combat, name="木桩二号") -> None:
    """再放一个木桩，验证"全体伤害"是不是真的打到所有敌人。"""
    combat.enemies.append(Enemy(name=name, max_hp=999, intent=Intent(IntentAction.ATTACK, 0)))


def save_and_load(record: dict, cards_dir: Path):
    #一条卡牌记录 -> 落盘 -> 读回来 -> CardSpec（模拟"造完牌存下来再进对局"）
    path = cc.save_card(record, cards_dir)
    back = cc.read_card(path)
    return cc.make_card_spec(back)


def build_with(cards_dir: Path, decks_dir: Path, *card_ids: str, title="审计卡组"):
    #把这些编号放进一副卡组、选中它、开一局，返回战斗。
    deck = cc.new_deck(title)
    for card_id in card_ids:
        cc.add_card_to_deck(deck, card_id, 1)
    cc.save_deck(deck, decks_dir)
    cc.set_selected_deck(decks_dir, deck["deck_id"])
    combat = cc.build_combat(cards_dir, decks_dir)
    combat.start_combat()
    _clean_starting_hand(combat)
    return combat


def play_created(cards_dir: Path, decks_dir: Path, *, title: str, effects: list[dict], **fields):
    #造一张牌、放进卡组、开一局、把它抽到手牌并打出，返回 (战斗, 卡, 记录)
    defaults = dict(cost="1", card_type="attack", target="enemy", rarity="common", keywords=[], text="")
    defaults.update(fields)
    record, errors = cc.make_card_record(title=title, effects=effects, **defaults)
    assert record is not None, f"{title} 造不出来：{errors}"
    spec = save_and_load(record, cards_dir)
    combat = build_with(cards_dir, decks_dir, spec.card_id)
    card = next(c for c in combat.player.deck if c.card_id == spec.card_id)
    combat.player.piles.put_in_hand(card, combat.player.hand_limit)
    combat.player.energy = 3
    return combat, card, record


def audit_effects(cards_dir: Path, decks_dir: Path) -> None:
    print("== 普通牌效果 ==")

    # ① 伤害
    combat, card, _ = play_created(cards_dir, decks_dir, title="伤1", effects=[{"op": "damage", "value": "7", "hits": "1"}])
    foe = combat.enemies[0]
    before = foe.hp
    combat.play_card(card, foe)
    check("伤害 7", before - foe.hp, 7)

    # ② 多段伤害
    combat, card, _ = play_created(cards_dir, decks_dir, title="伤2", effects=[{"op": "damage", "value": "4", "hits": "3"}])
    foe = combat.enemies[0]
    before = foe.hp
    combat.play_card(card, foe)
    check("多段伤害 4×3", before - foe.hp, 12)

    # ③ 全体伤害（场上放两个敌人）
    combat, card, _ = play_created(cards_dir, decks_dir, title="伤3", target="all",
                                   effects=[{"op": "damage", "value": "5", "hits": "1"}])
    add_dummy_enemy(combat)
    check("目标=所有敌人 带过来了", card.target, TargetType.ALL_ENEMIES)
    before = [f.hp for f in combat.enemies]
    combat.play_card(card, combat.enemies[0])
    check("全体伤害 5（每个敌人）", [b - f.hp for b, f in zip(before, combat.enemies)], [5, 5])

    # ④ 格挡
    combat, card, _ = play_created(cards_dir, decks_dir, title="挡", card_type="skill", target="self",
                                   effects=[{"op": "block", "value": "9", "hits": "1"}])
    combat.play_card(card, combat.player)
    check("格挡 9", combat.player.block, 9)

    # ⑤ 抽牌
    combat, card, _ = play_created(cards_dir, decks_dir, title="抽", card_type="skill", target="self",
                                   effects=[{"op": "draw", "value": "2", "hits": "1"}])
    combat.player.piles.pile(PileType.DRAW).cards.extend([ASK_AROUND_SPEC.create() for _ in range(5)])
    hand_before = len(combat.player.piles.pile(PileType.HAND).cards)
    combat.play_card(card, combat.player)
    check("抽 2 张", len(combat.player.piles.pile(PileType.HAND).cards) - hand_before + 1, 2)

    # ⑥ 能量
    combat, card, _ = play_created(cards_dir, decks_dir, title="能", card_type="skill", target="self",
                                   effects=[{"op": "energy", "value": "2", "hits": "1"}])
    energy_before = combat.player.energy
    cost = card.cost
    combat.play_card(card, combat.player)
    check("获得 2 能量（扣 1 费后净 +1）", combat.player.energy, energy_before - cost + 2)

    # ⑦⑧ 易伤 / 虚弱
    combat, card, _ = play_created(cards_dir, decks_dir, title="易", effects=[{"op": "vulnerable", "value": "2", "hits": "1"}])
    foe = combat.enemies[0]
    combat.play_card(card, foe)
    check("易伤 2 层", foe.get_power_amount("Vulnerable"), 2)

    combat, card, _ = play_created(cards_dir, decks_dir, title="弱", effects=[{"op": "weak", "value": "2", "hits": "1"}])
    foe = combat.enemies[0]
    combat.play_card(card, foe)
    check("虚弱 2 层", foe.get_power_amount("Weak"), 2)

    # ⑨ 力量
    combat, card, _ = play_created(cards_dir, decks_dir, title="力", card_type="power", target="self",
                                   effects=[{"op": "strength", "value": "3", "hits": "1"}])
    combat.play_card(card, combat.player)
    check("力量 +3", combat.player.get_power_amount("Strength"), 3)

    # ⑩ 治疗
    combat, card, _ = play_created(cards_dir, decks_dir, title="疗", card_type="skill", target="self",
                                   effects=[{"op": "heal", "value": "5", "hits": "1"}])
    combat.player.hp = 50
    combat.play_card(card, combat.player)
    check("回复 5 点生命", combat.player.hp, 55)

    # ⑪ 失去生命
    combat, card, _ = play_created(cards_dir, decks_dir, title="失", card_type="skill", target="self",
                                   effects=[{"op": "lose_hp", "value": "3", "hits": "1"}])
    hp_before = combat.player.hp
    combat.play_card(card, combat.player)
    check("失去 3 点生命", hp_before - combat.player.hp, 3)

    # ⑫ 生成素材
    combat, card, _ = play_created(cards_dir, decks_dir, title="材", card_type="skill", target="self",
                                   effects=[{"op": "attach_material", "value": "0", "hits": "1"}])
    combat.play_card(card, combat.player)
    tokens = [c for c in combat.player.piles.pile(PileType.HAND).cards if getattr(c, "is_material", False)]
    check("生成 1 张素材牌", len(tokens), 1)
    check("素材牌不能打出", CardKeyword.UNPLAYABLE in tokens[0].keywords if tokens else None, True)
    check("素材牌不会掉（保留）", CardKeyword.RETAIN in tokens[0].keywords if tokens else None, True)

    # ⑬ 关键字：消耗 / 保留
    combat, card, _ = play_created(cards_dir, decks_dir, title="耗", keywords=["exhaust"],
                                   effects=[{"op": "damage", "value": "1", "hits": "1"}])
    check("消耗：关键字带进对局", CardKeyword.EXHAUST in card.keywords, True)
    combat.play_card(card, combat.enemies[0])
    check("消耗：进消耗堆", combat.player.piles.pile(PileType.EXHAUST).contains(card), True)

    combat, card, _ = play_created(cards_dir, decks_dir, title="留", keywords=["retain"],
                                   effects=[{"op": "block", "value": "1", "hits": "1"}], target="self", card_type="skill")
    check("保留：关键字带进对局", CardKeyword.RETAIN in card.keywords, True)
    # 保留说的是"回合结束时留在手里"，所以这张牌要留在手上不打出，再配一张没勾保留的牌做对照
    control = ASK_AROUND_SPEC.create()
    combat.player.piles.put_in_hand(control, combat.player.hand_limit)
    combat.discard_hand()      # 直接跑"回合结束扔手牌"这一步，免得下一回合洗牌把弃牌堆又抽走
    check("保留：回合结束仍留在手牌", combat.player.piles.pile(PileType.HAND).contains(card), True)
    check("对照：没勾保留的牌回合结束进弃牌堆",
          combat.player.piles.pile(PileType.DISCARD).contains(control), True)

    # ⑭ 一张牌多条效果按顺序结算
    combat, card, _ = play_created(cards_dir, decks_dir, title="组", effects=[
        {"op": "damage", "value": "6", "hits": "1"},
        {"op": "vulnerable", "value": "2", "hits": "1"},
        {"op": "draw", "value": "1", "hits": "1"},
    ])
    foe = combat.enemies[0]
    before = foe.hp
    combat.play_card(card, foe)
    check("三条效果：伤害", before - foe.hp, 6)
    check("三条效果：易伤", foe.get_power_amount("Vulnerable"), 2)


def audit_materials(cards_dir: Path, decks_dir: Path) -> None:
    print("== 素材牌效果（装在承载牌上）==")
    material_cases = [
        ("material_damage", "3", "1", "伤害素材"),
        ("material_block", "4", "1", "格挡素材"),
        ("material_vulnerable", "2", "1", "易伤素材"),
        ("material_weak", "1", "1", "虚弱素材"),
        ("material_energy", "1", "1", "能量素材"),
        ("material_draw", "1", "1", "抽牌素材"),
        ("material_plating", "2", "1", "覆甲素材"),
    ]
    for index, (op, value, hits, note) in enumerate(material_cases):
        material_record, errors = cc.make_card_record(
            title=f"材{index}", cost="0", card_type="material", target="self", rarity="normal",
            keywords=[], text="", effects=[{"op": op, "value": value, "hits": hits}])
        assert material_record is not None, f"素材牌造不出来：{errors}"
        material_spec = save_and_load(material_record, cards_dir)

        carrier_record, _ = cc.make_card_record(
            title=f"载{index}", cost="1", card_type="attack", target="enemy", rarity="common",
            keywords=[], text="", effects=[{"op": "damage", "value": "6", "hits": "1"}])
        carrier_spec = save_and_load(carrier_record, cards_dir)

        combat = build_with(cards_dir, decks_dir, carrier_spec.card_id, material_spec.card_id, title="素材审计")
        piles = combat.player.piles
        carrier = next(c for c in combat.player.deck if c.card_id == carrier_spec.card_id)
        material = next(c for c in combat.player.deck if c.card_id == material_spec.card_id)
        check(f"{note}：素材类别带过来了", material.category_text, "普通")
        piles.put_in_hand(carrier, combat.player.hand_limit)
        piles.put_in_hand(material, combat.player.hand_limit)
        combat.player.energy = 3
        foe = combat.enemies[0]

        equipped, _tip = equip_from_hand(combat.player, material, carrier, combat=combat)
        check(f"{note}（装得上）", equipped, True)
        check(f"{note}：装完槽位 1", get_loadout(carrier).material_count, 1)

        hp_before, energy_before, block_before = foe.hp, combat.player.energy, combat.player.block
        hand_before = len(piles.pile(PileType.HAND).cards)
        plating_before = combat.player.get_power_amount("Plating")
        vuln_before = foe.get_power_amount("Vulnerable")
        weak_before = foe.get_power_amount("Weak")
        combat.play_card(carrier, foe)

        if op == "material_damage":
            check(f"{note}：敌人共掉 6+{value}", hp_before - foe.hp, 6 + int(value))
        elif op == "material_block":
            check(f"{note}：格挡 +{value}", combat.player.block - block_before, int(value))
        elif op == "material_vulnerable":
            check(f"{note}：易伤 +{value}", foe.get_power_amount("Vulnerable") - vuln_before, int(value))
        elif op == "material_weak":
            check(f"{note}：虚弱 +{value}", foe.get_power_amount("Weak") - weak_before, int(value))
        elif op == "material_energy":
            check(f"{note}：能量 +{value}（扣 1 费）", combat.player.energy - energy_before,
                  int(value) - carrier_record["cost"])
        elif op == "material_draw":
            check(f"{note}：手牌 +{value}（打出又少 1 张）",
                  len(piles.pile(PileType.HAND).cards) - hand_before + 1, int(value))
        elif op == "material_plating":
            check(f"{note}：覆甲 +{value}", combat.player.get_power_amount("Plating") - plating_before, int(value))
        check(f"{note}：素材牌进消耗堆", piles.pile(PileType.EXHAUST).contains(material), True)

    # 常驻类素材：承载牌可保留 / 承载牌耗能+1
    for index, (op, value, note, want) in enumerate((
            ("material_retain", "0", "承载牌可跨回合保留", "retain"),
            ("material_cost", "1", "承载牌耗能+1", "cost"))):
        material_record, _ = cc.make_card_record(
            title=f"常材{index}", cost="0", card_type="material", target="self", rarity="permanent",
            keywords=[], text="", effects=[{"op": op, "value": value, "hits": "1"}])
        material_spec = save_and_load(material_record, cards_dir)
        carrier_record, _ = cc.make_card_record(
            title=f"常载{index}", cost="1", card_type="skill", target="self", rarity="common",
            keywords=[], text="", effects=[{"op": "block", "value": "5", "hits": "1"}])
        carrier_spec = save_and_load(carrier_record, cards_dir)
        combat = build_with(cards_dir, decks_dir, carrier_spec.card_id, material_spec.card_id, title="常驻审计")
        piles = combat.player.piles
        carrier = next(c for c in combat.player.deck if c.card_id == carrier_spec.card_id)
        material = next(c for c in combat.player.deck if c.card_id == material_spec.card_id)
        check(f"{note}：永久素材类别带过来了", material.category_text, "永久")
        piles.put_in_hand(carrier, combat.player.hand_limit)
        piles.put_in_hand(material, combat.player.hand_limit)
        equip_from_hand(combat.player, material, carrier, combat=combat)

        if want == "retain":
            check(f"{note}：material_retain 标记", carrier.material_retain, True)
            combat.end_player_turn()
            check(f"{note}：回合结束仍在手牌", piles.pile(PileType.HAND).contains(carrier), True)
        else:
            check(f"{note}：费用 1 -> 2", carrier.cost, 2)


def audit_material_category(cards_dir: Path, decks_dir: Path) -> None:
    #素材类别（一次性 / 普通 / 永久 / 诅咒）在卡面上要能如实显示
    print("== 素材类别 ==")
    want = {"one_shot": "一次性", "normal": "普通", "permanent": "永久", "curse": "诅咒"}
    for key, label in want.items():
        record, errors = cc.make_card_record(
            title=f"类别{key}", cost="0", card_type="material", target="self", rarity=key,
            keywords=[], text="", effects=[{"op": "material_damage", "value": "2", "hits": "1"}])
        assert record is not None, f"{key} 造不出来：{errors}"
        spec = cc.make_card_spec(record)
        check(f"{label}：类别 -> 卡面文字", spec.create().category_text, label)
        check(f"{label}：素材牌不能打出", CardKeyword.UNPLAYABLE in spec.create().keywords, True)


def audit_deck_pipeline(cards_dir: Path, decks_dir: Path) -> None:
    print("== 卡组 -> 战斗 的复刻 ==")
    record, _ = cc.make_card_record(title="复刻牌", cost="2", card_type="attack", target="enemy",
                                    rarity="rare", keywords=["exhaust"], text="",
                                    effects=[{"op": "damage", "value": "11", "hits": "1"}])
    spec = save_and_load(record, cards_dir)
    deck = cc.new_deck("复刻卡组")
    cc.add_card_to_deck(deck, spec.card_id, 2)
    cc.save_deck(deck, decks_dir)
    cc.set_selected_deck(decks_dir, deck["deck_id"])
    combat = cc.build_combat(cards_dir, decks_dir)
    combat.start_combat()
    _clean_starting_hand(combat)
    mine = [c for c in combat.player.deck if c.card_id == spec.card_id]
    check("卡组里 2 份 -> 牌组里 2 张", len(mine), 2)
    check("两份是不同实例", mine[0] is not mine[1], True)
    check("费用带过来了", mine[0].cost, 2)
    check("稀有度带过来了", mine[0].rarity.name, "RARE")
    check("类型带过来了", mine[0].card_type.name, "ATTACK")
    check("关键字带过来了", CardKeyword.EXHAUST in mine[0].keywords, True)
    check("卡面文字带过来了", mine[0].text, "造成11点伤害。消耗。")
    foe = combat.enemies[0]
    foe.hp = 100
    combat.player.piles.put_in_hand(mine[0], combat.player.hand_limit)
    combat.player.energy = 3
    combat.play_card(mine[0], foe)
    check("打出后确实造成 11 点", 100 - foe.hp, 11)
    check("消耗关键字生效（进消耗堆）", combat.player.piles.pile(PileType.EXHAUST).contains(mine[0]), True)

    # 目标类型：所有敌人
    record, _ = cc.make_card_record(title="全体复刻", cost="1", card_type="attack", target="all",
                                    rarity="common", keywords=[], text="",
                                    effects=[{"op": "damage", "value": "3", "hits": "1"}])
    spec2 = save_and_load(record, cards_dir)
    combat = build_with(cards_dir, decks_dir, spec2.card_id, title="全体卡组")
    card2 = next(c for c in combat.player.deck if c.card_id == spec2.card_id)
    add_dummy_enemy(combat)
    check("目标=所有敌人 带过来了", card2.target, TargetType.ALL_ENEMIES)
    combat.player.piles.put_in_hand(card2, combat.player.hand_limit)
    combat.player.energy = 3
    before = [f.hp for f in combat.enemies]
    combat.play_card(card2, combat.enemies[0])
    check("全体牌：两个敌人都掉 3 点", [b - f.hp for b, f in zip(before, combat.enemies)], [3, 3])


def audit_id_collision(cards_dir: Path, decks_dir: Path) -> None:
    #自制卡编号和系统卡撞了会怎样（比如起名 strike_soyoi）
    print("== 编号撞车（自制卡 id == 系统卡 id）==")
    from soyoi_game.content.character import build_character
    from soyoi_game.content.soyoi_cards import PLAYABLE_REWARD_CARDS

    system_ids = {spec.card_id for spec in build_character().starting_deck}
    system_ids |= {spec.card_id for spec in PLAYABLE_REWARD_CARDS}
    collision = {cid for cid in system_ids if cc.make_card_id(cid) == cid}
    check("系统卡编号不会被自制卡顶掉（自制编号会去掉下划线）", sorted(collision), [])

    record, errors = cc.make_card_record(title="strike_soyoi", cost="3", card_type="attack", target="enemy",
                                         rarity="common", keywords=[], text="",
                                         effects=[{"op": "damage", "value": "99", "hits": "1"}])
    if record is None:
        print("  造不出来：", errors)
        return
    print("  自制卡编号：", record["card_id"])
    save_and_load(record, cards_dir)
    combat = build_with(cards_dir, decks_dir, "strike_soyoi", title="撞车卡组")
    strike = next(c for c in combat.player.deck if c.card_id == "strike_soyoi")
    print(f"  对局里的「打击」：{strike.title} {strike.cost} 费，{strike.text}")
    check("编号撞车：系统「打击」还是原来的打击", strike.title, "打击")
    check("编号撞车：伤害还是 6 点", strike.current_effects()[0].amount, 6)


def audit_edit_existing(cards_dir: Path, decks_dir: Path) -> None:
    #改数值：载入已保存的卡 -> 改伤害 -> 覆盖保存，对局里要变成新数值
    print("== 改已有卡牌的数值 ==")
    record, _ = cc.make_card_record(title="改数值", cost="1", card_type="attack", target="enemy",
                                    rarity="common", keywords=[], text="",
                                    effects=[{"op": "damage", "value": "4", "hits": "1"}])
    spec = save_and_load(record, cards_dir)
    combat = build_with(cards_dir, decks_dir, spec.card_id, title="改数值卡组")
    card = next(c for c in combat.player.deck if c.card_id == spec.card_id)
    check("改数值前：对局里是 4 点", card.current_effects()[0].amount, 4)

    # 创作端的"载入老卡再保存"：编号不变、覆盖同一个文件
    edited, _ = cc.make_card_record(title=record["title"], cost="1", card_type="attack", target="enemy",
                                    rarity="common", keywords=[], text="",
                                    effects=[{"op": "damage", "value": "9", "hits": "1"}])
    edited["card_id"] = spec.card_id
    cc.save_card(edited, cards_dir, overwrite=True)
    combat2 = build_with(cards_dir, decks_dir, spec.card_id, title="改数值卡组2")
    card2 = next(c for c in combat2.player.deck if c.card_id == spec.card_id)
    check("改数值后：对局里变成 9 点", card2.current_effects()[0].amount, 9)
    check("改数值后：卡面文字跟着变", card2.text, "造成9点伤害。")
    foe = combat2.enemies[0]
    before = foe.hp
    combat2.player.piles.put_in_hand(card2, combat2.player.hand_limit)
    combat2.player.energy = 3
    combat2.play_card(card2, foe)
    check("改数值后：打出来真的掉 9 点", before - foe.hp, 9)
    check("改数值只留一个文件（没多出 -2）",
          sorted(p.name for p in cards_dir.glob(f"{spec.card_id}*.json")), [f"{spec.card_id}.json"])


def audit_material_consumption(cards_dir: Path, decks_dir: Path) -> None:
    #素材类别要决定"用不用掉"：一次性素材结算完就没，普通素材一直留着
    print("== 一次性素材会不会被用掉 ==")
    carried = {}

    for index, category in enumerate(("one_shot", "normal")):
        material_record, errors = cc.make_card_record(
            title=f"用材{index}", cost="0", card_type="material", target="self", rarity=category,
            keywords=[], text="", effects=[{"op": "material_damage", "value": "3", "hits": "1"}])
        assert material_record is not None, f"{category} 素材造不出来：{errors}"
        material_spec = save_and_load(material_record, cards_dir)
        carrier_record, _ = cc.make_card_record(
            title=f"用载{index}", cost="0", card_type="attack", target="enemy", rarity="common",
            keywords=[], text="", effects=[{"op": "damage", "value": "6", "hits": "1"}])
        carrier_spec = save_and_load(carrier_record, cards_dir)

        combat = build_with(cards_dir, decks_dir, carrier_spec.card_id, material_spec.card_id,
                            title="消耗审计")
        piles = combat.player.piles
        carrier = next(c for c in combat.player.deck if c.card_id == carrier_spec.card_id)
        material = next(c for c in combat.player.deck if c.card_id == material_spec.card_id)
        piles.move(carrier, PileType.HAND)
        piles.move(material, PileType.HAND)
        equip_from_hand(combat.player, material, carrier, combat=combat)
        foe = combat.enemies[0]

        def play_carrier() -> int:
            combat.player.energy = 3
            piles.move(carrier, PileType.HAND)
            before = foe.hp
            combat.play_card(carrier, foe)
            return before - foe.hp

        first = play_carrier()
        left = get_loadout(carrier).material_count
        second = play_carrier()
        carried[category] = (first, left, second)
        if category == "one_shot":
            check("一次性素材：第一次打出 6+3", first, 9)
            check("一次性素材：结算完槽位空了", left, 0)
            check("一次性素材：第二次打出只剩本体的 6 点", second, 6)
        else:
            check("普通素材：第一次打出 6+3", first, 9)
            check("普通素材：素材还在槽里", left, 1)
            check("普通素材：第二次打出还有 6+3", second, 9)
    print(f"  一次性 {carried['one_shot']}　普通 {carried['normal']}　(首次伤害, 剩余素材, 二次伤害)")


def main() -> int:
    tmp_root = ROOT / "tests" / ".tmp" / f"audit-{uuid.uuid4().hex[:6]}"
    cards_dir = tmp_root / "cards"
    decks_dir = tmp_root / "decks"
    cards_dir.mkdir(parents=True, exist_ok=True)
    decks_dir.mkdir(parents=True, exist_ok=True)
    random.seed(2026)
    try:
        audit_effects(cards_dir, decks_dir)
        audit_materials(cards_dir, decks_dir)
        audit_material_category(cards_dir, decks_dir)
        audit_material_consumption(cards_dir, decks_dir)
        audit_deck_pipeline(cards_dir, decks_dir)
        audit_id_collision(cards_dir, decks_dir)
        audit_edit_existing(cards_dir, decks_dir)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print(f"\n共检查 {CHECKS} 项")
    if FAILURES:
        print(f"发现 {len(FAILURES)} 个问题：")
        for item in FAILURES:
            print(" -", item)
        return 1
    print("全部通过：创作端造出来的卡，进战斗后行为与描述一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
