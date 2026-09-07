from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class CardType(str, Enum):
    ATTACK = "attack"
    SKILL = "skill"
    POWER = "power"
    MATERIAL = "material"


class CardRarity(str, Enum):
    BASIC = "basic"
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    TOKEN = "token"


class TargetType(str, Enum):
    SELF = "self"
    ANY_ENEMY = "any_enemy"
    ALL_ENEMIES = "all_enemies"
    NONE = "none"


class MaterialCategory(str, Enum):
    NORMAL = "normal"
    ONE_SHOT = "one_shot"
    PERMANENT = "permanent"
    CURSE = "curse"


class MaterialTiming(str, Enum):
    PERSISTENT = "persistent"
    AFTER_CARRIER_PLAYED = "after_carrier_played"
    AFTER_RETAINED_ACROSS_TURN = "after_retained_across_turn"
    AFTER_CARRIER_NEXT_PLAYED = "after_carrier_next_played"
    FIRST_CARRIER_PLAY_EACH_COMBAT = "first_carrier_play_each_combat"


@dataclass(frozen=True)
class EffectSpec:
    operation: str
    amount: float = 0
    hits: int = 1
    timing: str = "on_play"
    target: str = "inherited"
    once_per_turn: bool = False
    consumes_component: bool = False
    payload: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EffectSpec":
        return cls(
            operation=str(data["operation"]),
            amount=float(data.get("amount", 0)),
            hits=int(data.get("hits", 1)),
            timing=str(data.get("timing", "on_play")),
            target=str(data.get("target", "inherited")),
            once_per_turn=bool(data.get("once_per_turn", False)),
            consumes_component=bool(data.get("consumes_component", False)),
            payload=dict(data.get("payload", {})),
        )


@dataclass(frozen=True)
class CardDefinition:
    id: str
    name: str
    cost: int
    upgraded_cost: int
    card_type: CardType
    rarity: CardRarity
    target: TargetType
    base_text: str
    upgraded_text: str
    portrait: str = ""
    effects: tuple[EffectSpec, ...] = ()
    upgraded_effects: tuple[EffectSpec, ...] = ()
    keywords: tuple[str, ...] = ()
    upgraded_keywords: tuple[str, ...] = ()
    runtime_id: int | None = None
    is_fusion: bool = False
    requires_custom_logic: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CardDefinition":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            cost=int(data["cost"]),
            upgraded_cost=int(data["upgraded_cost"]),
            card_type=CardType(str(data["card_type"])),
            rarity=CardRarity(str(data["rarity"])),
            target=TargetType(str(data["target"])),
            base_text=str(data["base_text"]),
            upgraded_text=str(data["upgraded_text"]),
            portrait=str(data.get("portrait", "")),
            effects=tuple(EffectSpec.from_dict(item) for item in data.get("effects", [])),
            upgraded_effects=tuple(
                EffectSpec.from_dict(item) for item in data.get("upgraded_effects", [])
            ),
            keywords=tuple(data.get("keywords", [])),
            upgraded_keywords=tuple(data.get("upgraded_keywords", [])),
            runtime_id=data.get("runtime_id"),
            is_fusion=bool(data.get("is_fusion", False)),
            requires_custom_logic=bool(data.get("requires_custom_logic", False)),
        )


@dataclass(frozen=True)
class MaterialDefinition:
    id: str
    name: str
    text: str
    category: MaterialCategory
    effects: tuple[EffectSpec, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MaterialDefinition":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            text=str(data["text"]),
            category=MaterialCategory(str(data["category"])),
            effects=tuple(EffectSpec.from_dict(item) for item in data.get("effects", [])),
        )


@dataclass
class MaterialInstance:
    definition: MaterialDefinition
    instance_id: str = field(default_factory=lambda: uuid4().hex)
    fired_once_keys: set[str] = field(default_factory=set)


@dataclass
class CardInstance:
    definition: CardDefinition
    upgraded: bool = False
    instance_id: str = field(default_factory=lambda: uuid4().hex)
    materials: list[MaterialInstance] = field(default_factory=list)
    next_replace_index: int = 0
    times_processed: int = 0

    @property
    def cost(self) -> int:
        return self.definition.upgraded_cost if self.upgraded else self.definition.cost

    @property
    def printed_effects(self) -> tuple[EffectSpec, ...]:
        return self.definition.upgraded_effects if self.upgraded else self.definition.effects


@dataclass(frozen=True)
class RelicDefinition:
    id: str
    name: str
    text: str
    turn_start_effects: tuple[EffectSpec, ...] = ()


@dataclass(frozen=True)
class CharacterDefinition:
    id: str
    name: str
    english_name: str
    description: str
    starting_hp: int
    color_rgb: tuple[int, int, int]
    energy_per_turn: int
    draw_per_turn: int
    starting_deck: tuple[str, ...]
    starting_relic: RelicDefinition

