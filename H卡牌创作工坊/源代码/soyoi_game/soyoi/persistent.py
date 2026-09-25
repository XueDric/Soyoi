"""按槽位重算常驻效果（保留、加费），不动本回合的临时状态。"""

from ..core.cards import Card
from .card import find_loadout
from .materials import MaterialEffectOperation as Op, MaterialEffectTiming as Timing


def sync_persistent_materials(card: Card) -> None:
    card.material_retain = False
    card.material_cost_modifier = 0
    loadout = find_loadout(card)
    if loadout is None:          # 没装过素材的牌：没有常驻效果要同步
        return
    card.dynamic_vars["MaterialCount"] = loadout.material_count
    for bundle in loadout.slots:
        if bundle is None:
            continue
        for component in bundle.components:
            for effect in component.material_effects:
                if effect.timing != Timing.PERSISTENT:
                    continue
                if effect.operation == Op.GRANT_RETAIN:
                    card.material_retain = True
                elif effect.operation == Op.INCREASE_CARRIER_COST:
                    card.material_cost_modifier += int(effect.amount)
