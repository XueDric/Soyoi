"""素材加工：生成素材、装到承载牌上、槽满了合料。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..core.cards import Card, PileType, RewardEffectOperation
from ..soyoi.card import can_carry_materials, get_loadout
from .materials import MaterialBundle, MaterialCategory, MaterialEffectSpec, SLOTS_PER_CARD
from .material_lifecycle import mark_material_played, mark_processed
from .persistent import sync_persistent_materials

if TYPE_CHECKING:
    from ..core.combat import CombatState
    from ..core.player import Player


def _box(player: "Player") -> list[MaterialBundle]:
    #取玩家的素材盒：第一次访问时才挂到玩家实例上
    box = player.__dict__.get("_material_box")
    if box is None:
        box = []
        player.__dict__["_material_box"] = box
    return box


def get_materials(player: "Player") -> list[MaterialBundle]:
    #玩家当前素材盒里的所有素材
    return _box(player)


def positive_count(player: "Player") -> int:
    #正向素材数量（非诅咒）
    return sum(1 for m in get_materials(player) if m.positive)


def begin_combat(player: "Player") -> None:
    #战斗开始清空素材盒（组件仍可能留在牌堆/牌上，此处清运行时列表）
    _box(player).clear()


def store(player: "Player", material: "Card") -> MaterialBundle:
    #加入素材盒并把手牌里对应的素材卡放进手牌
    # 重复存入同一组件是幂等操作，两张同名素材则各占一份。
    for existing in _box(player):
        if any(component is material for component in existing.components):
            return existing
    bundle = MaterialBundle.from_material(material)
    _box(player).append(bundle)
    put_in_hand(player, material)
    return bundle


def put_in_hand(player: "Player", material: "Card") -> None:
    player.piles.put_in_hand(material, player.hand_limit)


def remove(player: "Player", bundle: MaterialBundle) -> bool:
    box = _box(player)
    if bundle not in box:
        return False
    box.remove(bundle)
    return True


def attach(player: "Player", carrier: "Card", slot: int, bundle: MaterialBundle) -> Optional[MaterialBundle]:
    #把一捆素材附着到承载牌的某个槽位，返回被替换的旧素材
    if not can_carry_materials(carrier):
        raise ValueError(f"{carrier.title} 是素材牌，不能再装备素材。")
    loadout = get_loadout(carrier)
    replaced = loadout.replace(slot, bundle)
    mark_processed(carrier)
    carrier.dynamic_vars["MaterialCount"] = loadout.material_count
    sync_persistent_materials(carrier)
    return replaced


def attach_next_available(player: "Player", carrier: "Card", bundle: MaterialBundle) -> Optional[MaterialBundle]:
    #附着到下一个可用槽位；满槽则替换轮询到的槽位
    loadout = get_loadout(carrier)
    slot = loadout.get_next_slot()
    return attach(player, carrier, slot, bundle)


def try_attach_from_box(player: "Player", bundle: MaterialBundle, carrier: "Card", slot: int) -> Optional[MaterialBundle]:
    #从素材盒取材并附着。若素材不在盒中或无法承载则失败
    from .card import can_carry_materials as ccm
    box = _box(player)
    if bundle not in box or not ccm(carrier):
        return None
    # 先验证槽位并完成加工，再消费盒中素材；无效槽位不丢素材。
    replaced = attach(player, carrier, slot, bundle)
    box.remove(bundle)
    for component in bundle.components:
        player.piles.exhaust(component)
    return replaced


def try_merge_from_box(player: "Player", left: MaterialBundle, right: MaterialBundle) -> Optional[MaterialBundle]:
    #把素材盒里两捆素材合料成一捆（诅咒不能合料）
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


#简化：判断"目标牌能否被选中用于融合/承载"
def can_choose_for_fusion(card: "Card") -> bool:
    return not card.is_material


#素材以牌的形式放手牌里，装到哪张牌由玩家决定
def gives_material(card: "Card") -> bool:
    #这张牌打出时会不会生成素材牌（也就是带「生成素材」效果）
    return any(
        effect.operation == RewardEffectOperation.ATTACH_MATERIAL
        for effect in card.current_effects()
    )


def material_targets(player: "Player", exclude: Optional["Card"] = None) -> list["Card"]:
    #手牌里所有能承载素材的牌 —— 也就是"可以加工到哪张牌上"的候选
    hand = player.piles.pile(PileType.HAND).cards
    return [card for card in hand if card is not exclude and can_carry_materials(card)]


def _bundle_of(player: "Player", material: "Card") -> MaterialBundle:
    for bundle in _box(player):
        if any(component is material for component in bundle.components):
            return bundle
    return MaterialBundle.from_material(material)


def equip_from_hand(
    player: "Player",
    material: "Card",
    carrier: "Card",
    *,
    combat: Optional["CombatState"] = None,
) -> tuple[bool, str]:
    if not material.is_material:
        return False, f"{material.title} 不是素材牌。"
    if material is carrier:
        return False, "不能把素材装到它自己身上。"
    if not can_carry_materials(carrier):
        return False, f"{carrier.title} 是素材牌，不能再装素材。"
    hand = player.piles.pile(PileType.HAND)
    if not hand.contains(material):
        return False, f"{material.title} 不在手牌里。"
    if not hand.contains(carrier):
        return False, f"{carrier.title} 不在手牌里。"

    bundle = _bundle_of(player, material)
    loadout = get_loadout(carrier)
    slot = loadout.get_next_slot()
    existing = loadout.slots[slot]
    if existing is None:
        attach(player, carrier, slot, bundle)
        note = f"已把「{material.title}」加工到「{carrier.title}」"
    else:
        if MaterialCategory.CURSE in (existing.category, bundle.category):
            return False, f"「{carrier.title}」的素材槽满了，诅咒素材不能合料。"
        attach(player, carrier, slot, existing.merge(bundle))
        note = f"「{carrier.title}」素材槽已满，改为合料"

    box = _box(player)
    if bundle in box:
        box.remove(bundle)
    for component in bundle.components:
        player.piles.exhaust(component)
    if combat is not None:
        mark_material_played(combat)
    return True, note
