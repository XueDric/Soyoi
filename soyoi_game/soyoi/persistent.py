"""从当前槽位重新计算常驻效果；不会覆盖本回合临时保留/费用。"""

from ..core.cards import Card
from .materials import MaterialEffectOperation as Op, MaterialEffectTiming as Timing


def sync_persistent_materials(card: Card) -> None:
    card.material_retain = False
    card.material_cost_modifier = 0
    loadout = getattr(card, "_material_loadout", None)
    if loadout is None:
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
