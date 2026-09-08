"""框架冒烟测试：无 UI 验证核心逻辑与素材结算。

运行：python scripts/smoke_test.py
断言核心数值，任一失败即 raise。
"""

import sys
import os

# 保证能 import soyoi_game
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soyoi_game.core.cards import PileType, CardType
from soyoi_game.core.combat import CombatState
from soyoi_game.soyoi.card import can_carry_materials, get_loadout
from soyoi_game.soyoi.material_effect_resolver import MaterialEffectResolver
from soyoi_game.soyoi.material_runtime import begin_combat, store, attach_next_available
from soyoi_game.soyoi.materials import MaterialBundle
from soyoi_game.content.materials import make_perler_color_pack
from soyoi_game.ui.__main__ import make_player, make_enemy


def test_basic_combat():
    p = make_player()
    p.piles.rng.seed(2026)
    e = make_enemy()
    combat = CombatState(player=p, enemies=[e])
    combat.next_enemy_intents()
    combat.start_combat()
    hand = p.piles.pile(PileType.HAND)
    card = next((c for c in hand.cards if c.card_type == CardType.ATTACK and c.cost <= p.energy), None)
    assert card is not None, "找不到可打出的攻击牌"
    hp_before = e.hp
    combat.play_card(card, e)
    assert e.hp < hp_before, "攻击牌没有造成伤害"
    assert p.energy < 3, "出牌没有消耗能量"
    assert p.piles.pile(PileType.DISCARD).cards, "出牌后没有进弃牌堆"
    print("[OK] 基础战斗")


def test_material_attach_and_resolve():
    p = make_player()
    e = make_enemy()
    combat = CombatState(player=p, enemies=[e])
    combat.next_enemy_intents()
    begin_combat(p)
    resolver = MaterialEffectResolver(combat)

    def after(sc, card):
        if can_carry_materials(card):
            resolver.resolve_after_carrier_played(card, sc.get_target())
    combat.after_card_played.append(after)

    mat = make_perler_color_pack()
    store(p, mat)
    bundle = MaterialBundle.from_material(mat)
    carrier = next(c for c in p.deck if c.title == "打击")
    attach_next_available(p, carrier, bundle)
    assert get_loadout(carrier).material_count == 1, "素材未附着"

    combat.start_combat()
    # 测试指定实例时显式移入手牌，不再依赖绕过合法性检查。
    p.piles.put_in_hand(carrier, p.hand_limit)
    hp_before = e.hp
    combat.play_card(carrier, e)
    # 打击6 + 素材3 = 9
    assert e.hp == hp_before - 9, f"素材效果未结算: 期望-9 实际{e.hp-hp_before}"
    print("[OK] 素材附着与结算")


def test_turn_cycle():
    p = make_player()
    e = make_enemy()
    combat = CombatState(player=p, enemies=[e])
    combat.next_enemy_intents()
    combat.start_combat()
    r1 = combat.round_number
    combat.end_player_turn()
    assert combat.round_number == r1 + 1, "回合未推进"
    assert len(p.piles.pile(PileType.HAND).cards) > 0, "新回合没有抽牌"
    print("[OK] 回合循环")


if __name__ == "__main__":
    test_basic_combat()
    test_material_attach_and_resolve()
    test_turn_cycle()
    print("\n全部冒烟测试通过！")
