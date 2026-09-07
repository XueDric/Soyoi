from __future__ import annotations

from .character import STARTER_CARDS
from .generated_catalog import MATERIAL_DATA, REWARD_CARD_DATA, SOURCE_INFO
from .model import CardDefinition, MaterialDefinition


REWARD_CARDS: dict[str, CardDefinition] = {
    item["id"]: CardDefinition.from_dict(item) for item in REWARD_CARD_DATA
}

MATERIALS: dict[str, MaterialDefinition] = {
    item["id"]: MaterialDefinition.from_dict(item) for item in MATERIAL_DATA
}

ALL_CARDS: dict[str, CardDefinition] = {**STARTER_CARDS, **REWARD_CARDS}


def get_card(card_id: str) -> CardDefinition:
    return ALL_CARDS[card_id]


def get_material(material_id: str) -> MaterialDefinition:
    return MATERIALS[material_id]

