"""素材盒 (MaterialBoxRuntime) 与附着 (MaterialAttachmentRuntime) 的高层 API。

对应 C#：
- MaterialBoxRuntime       ：素材集合的增删/生成/放到手牌/取材
- MaterialAttachmentRuntime：对承载牌槽位的附着/卸下/左移/合料

这是队友移植卡牌时最常调用的"操作入口"，比如"生成一张拼豆色包并加工到某牌"、
"选择一张手牌加工"、"把两份素材合料"等。

注意：素材操作不创建正常 CardPlay，素材作为 Token Skill 卡放在手牌，
拖出后进入消耗牌堆并让效果留在承载牌上（框架内用 MaterialCardBase 表示）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..core.cards import Card
from ..soyoi.card import can_carry_materials, get_loadout
from .materials import MaterialBundle, MaterialCategory, MaterialEffectSpec, SLOTS_PER_CARD
from .material_lifecycle import mark_processed

if TYPE_CHECKING:
    from ..core.combat import CombatState
    from ..core.player import Player


def _box(player: "Player") -> list[MaterialBundle]:
    box = player.__dict__.get("_material_box")
    if box is None:
        box = []
        player.__dict__["_material_box"] = box
    return box


def get_materials(player: "Player") -> list[MaterialBundle]:
    """玩家当前素材盒里的所有素材（对应 C# GetMaterials）。"""
    return _box(player)


def positive_count(player: "Player") -> int:
    """正向素材数量（非诅咒）。"""
    return sum(1 for m in get_materials(player) if m.positive)


def begin_combat(player: "Player") -> None:
    """战斗开始清空素材盒（组件仍可能留在牌堆/牌上，此处清运行时列表）。"""
    _box(player).clear()


def store(player: "Player", material: "Card") -> MaterialBundle:
    """加入素材盒并把手牌里对应的素材卡放进手牌。"""
    bundle = MaterialBundle.from_material(material)
    if bundle not in _box(player):
        _box(player).append(bundle)
    put_in_hand(player, material)
    return bundle


def put_in_hand(player: "Player", material: "Card") -> None:
    """把素材卡放进玩家手牌（如果还没有）。"""
    hand = player.piles.pile(1)  # PileType.HAND
    if material not in hand.cards:
        hand.add(material)


def remove(player: "Player", bundle: MaterialBundle) -> bool:
    """从素材盒移除一捆素材。"""
    box = _box(player)
    if bundle not in box:
        return False
    box.remove(bundle)
    return True


def attach(player: "Player", carrier: "Card", slot: int, bundle: MaterialBundle) -> Optional[MaterialBundle]:
    """把一捆素材附着到承载牌的某个槽位，返回被替换的旧素材。"""
    if not can_carry_materials(carrier):
        raise ValueError(f"{carrier.title} 是素材牌，不能再装备素材。")
    loadout = get_loadout(carrier)
    replaced = loadout.replace(slot, bundle)
    mark_processed(carrier)
    carrier.dynamic_vars["MaterialCount"] = loadout.material_count
    return replaced


def attach_next_available(player: "Player", carrier: "Card", bundle: MaterialBundle) -> Optional[MaterialBundle]:
    """附着到下一个可用槽位；满槽则替换轮询到的槽位（对应 C# Attach 的逻辑）。"""
    loadout = get_loadout(carrier)
    slot = loadout.get_next_slot()
    return attach(player, carrier, slot, bundle)


def try_attach_from_box(player: "Player", bundle: MaterialBundle, carrier: "Card", slot: int) -> Optional[MaterialBundle]:
    """从素材盒取材并附着。若素材不在盒中或无法承载则失败。"""
    from .card import can_carry_materials as ccm
    box = _box(player)
    if bundle not in box or not ccm(carrier):
        return None
    box.remove(bundle)
    return attach(player, carrier, slot, bundle)


def try_merge_from_box(player: "Player", left: MaterialBundle, right: MaterialBundle) -> Optional[MaterialBundle]:
    """把素材盒里两捆素材合料成一捆（诅咒不能合料）。"""
    box = _box(player)
    if left is right or left.category == MaterialCategory.CURSE or right.category == MaterialCategory.CURSE:
        return None
    if left not in box or right not in box:
        return None
    merged = left.merge(right)
    box.remove(left)
    box.remove(right)
    box.append(merged)
    return merged


# ---- 简化：判断"目标牌能否被选中用于融合/承载" ----
def can_choose_for_fusion(card: "Card") -> bool:
    return not getattr(card, "is_material", False)
