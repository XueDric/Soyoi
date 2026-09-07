from __future__ import annotations

from dataclasses import dataclass

from .model import CardInstance, EffectSpec, MaterialInstance, MaterialTiming


FULL_REFERENCE_SLOT_COUNT = 3
COURSE_MVP_SLOT_COUNT = 1


@dataclass(frozen=True)
class AttachmentResult:
    attached: MaterialInstance
    replaced: MaterialInstance | None
    slot_index: int
    destination_zone: str = "exhaust"
    counts_as_card_play: bool = False


@dataclass(frozen=True)
class MaterialResolution:
    effects: tuple[EffectSpec, ...]
    consumed_material_ids: tuple[str, ...]


def attach_material(
    carrier: CardInstance,
    material: MaterialInstance,
    *,
    slot_count: int = COURSE_MVP_SLOT_COUNT,
    slot_index: int | None = None,
) -> AttachmentResult:
    """Attach a material and return what the engine must move to the exhaust pile.

    The default is the one-slot course MVP. Use slot_count=3 to mirror the full mod's
    left-to-right replacement cycle.
    """
    if slot_count < 1:
        raise ValueError("slot_count must be at least 1")
    if slot_index is not None and not 0 <= slot_index < slot_count:
        raise IndexError("slot_index is outside the carrier's material slots")

    replaced: MaterialInstance | None = None
    if len(carrier.materials) < slot_count:
        target_index = len(carrier.materials) if slot_index is None else slot_index
        if target_index < len(carrier.materials):
            replaced = carrier.materials[target_index]
            carrier.materials[target_index] = material
        else:
            carrier.materials.append(material)
    else:
        target_index = carrier.next_replace_index if slot_index is None else slot_index
        replaced = carrier.materials[target_index]
        carrier.materials[target_index] = material
        if slot_index is None:
            carrier.next_replace_index = (target_index + 1) % slot_count

    carrier.times_processed += 1
    return AttachmentResult(material, replaced, target_index)


def resolve_materials(
    carrier: CardInstance,
    timing: MaterialTiming,
    *,
    turn_number: int,
) -> MaterialResolution:
    """Collect material effects for the engine's effect queue.

    This function does not mutate HP, block, energy, or piles. The teammate's combat
    engine remains the single owner of those states.
    """
    queued: list[EffectSpec] = []
    consumed: list[str] = []

    for material in tuple(carrier.materials):
        consume_material = False
        for effect_index, effect in enumerate(material.definition.effects):
            if effect.timing != timing.value:
                continue
            once_key = f"{turn_number}:{effect_index}"
            if effect.once_per_turn and once_key in material.fired_once_keys:
                continue
            queued.append(effect)
            if effect.once_per_turn:
                material.fired_once_keys.add(once_key)
            consume_material = consume_material or effect.consumes_component

        if consume_material:
            carrier.materials.remove(material)
            consumed.append(material.instance_id)

    return MaterialResolution(tuple(queued), tuple(consumed))


def combine_material_effects(*materials: MaterialInstance) -> tuple[EffectSpec, ...]:
    """Flatten component effects for a lightweight composite-material implementation."""
    return tuple(effect for material in materials for effect in material.definition.effects)

