from __future__ import annotations

import argparse
import ast
import hashlib
import pprint
import re
from pathlib import Path
from typing import Any


CARD_TYPE_MAP = {"Attack": "attack", "Skill": "skill", "Power": "power"}
RARITY_MAP = {
    "Basic": "basic",
    "Common": "common",
    "Uncommon": "uncommon",
    "Rare": "rare",
    "Token": "token",
}
TARGET_MAP = {"Self": "self", "AnyEnemy": "any_enemy", "AllEnemies": "all_enemies"}
CATEGORY_MAP = {
    "Normal": "normal",
    "OneShot": "one_shot",
    "Permanent": "permanent",
    "Curse": "curse",
}


def snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def parse_string(value: str) -> str:
    return ast.literal_eval(value.strip())


def extract_parenthesized(text: str, open_index: int) -> str:
    depth = 0
    in_string = False
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_index + 1 : index]
    raise ValueError("unclosed parenthesized expression")


def split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in depths:
            depths[char] += 1
        elif char in closing:
            depths[closing[char]] -= 1
        elif char == "," and all(value == 0 for value in depths.values()):
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return parts


def parse_number(value: str) -> float:
    return float(value.rstrip("mM"))


def parse_reward_effects(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"(?:RewardEffectOperation\.|Fx\(RewardEffectOperation\.)([A-Za-z0-9_]+)"
        r"\s*,\s*(-?\d+(?:\.\d+)?)[mM]?(?:\s*,\s*(\d+))?"
    )
    effects = []
    for operation, amount, hits in pattern.findall(text):
        effects.append(
            {
                "operation": snake_case(operation),
                "amount": parse_number(amount),
                "hits": int(hits or 1),
            }
        )
    return effects


def parse_redesigns(path: Path) -> dict[int, dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    result: dict[int, dict[str, Any]] = {}
    for match in re.finditer(r"(?m)^\s*(\d+)\s*=>\s*new\(", text):
        runtime_id = int(match.group(1))
        open_index = text.find("(", match.start())
        args = split_top_level(extract_parenthesized(text, open_index))
        result[runtime_id] = {
            "base_text": parse_string(args[0]),
            "upgraded_text": parse_string(args[1]),
            "effects": parse_reward_effects(args[2]),
            "upgraded_effects": parse_reward_effects(args[3]),
        }
    return result


def find_base_args(text: str) -> list[str]:
    marker = ": base("
    marker_index = text.find(marker)
    if marker_index < 0:
        raise ValueError("constructor base call not found")
    open_index = marker_index + len(marker) - 1
    return split_top_level(extract_parenthesized(text, open_index))


def parse_card(path: Path, redesigns: dict[int, dict[str, Any]]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    args = find_base_args(text)
    runtime_id = int(args[0])
    card = {
        "id": f"soyoi_reward_{runtime_id:03d}",
        "runtime_id": runtime_id,
        "name": parse_string(args[1]),
        "base_text": parse_string(args[2]),
        "upgraded_text": parse_string(args[3]),
        "portrait": parse_string(args[4]),
        "cost": int(args[5]),
        "upgraded_cost": int(args[6]),
        "card_type": CARD_TYPE_MAP[args[7].split(".")[-1]],
        "rarity": RARITY_MAP[args[8].split(".")[-1]],
        "target": TARGET_MAP[args[9].split(".")[-1]],
        "is_fusion": args[10].split(":")[-1].strip().lower() == "true",
        "keywords": [snake_case(item) for item in re.findall(r"CardKeyword\.(\w+)", args[11])],
        "upgraded_keywords": [
            snake_case(item) for item in re.findall(r"CardKeyword\.(\w+)", args[12])
        ],
        "effects": parse_reward_effects(args[13]),
        "upgraded_effects": parse_reward_effects(args[14]),
    }
    if runtime_id in redesigns:
        card.update(redesigns[runtime_id])

    plain_effect_words = ("造成", "格挡", "抽", "能量", "易伤", "虚弱", "力量", "回复")
    has_nontrivial_text = any(word in card["base_text"] for word in (
        "选择", "素材", "返回", "保留", "消耗", "每回合", "若", "置于", "结束",
    ))
    card["requires_custom_logic"] = has_nontrivial_text or not (
        card["effects"] or any(word in card["base_text"] for word in plain_effect_words)
    )
    return card


def parse_material_effects(text: str) -> list[dict[str, Any]]:
    effects: list[dict[str, Any]] = []
    for match in re.finditer(r"new MaterialEffectSpec\(", text):
        open_index = text.find("(", match.start())
        args = split_top_level(extract_parenthesized(text, open_index))
        effect: dict[str, Any] = {
            "operation": snake_case(args[0].split(".")[-1]),
            "amount": parse_number(args[1]),
            "hits": 1,
            "timing": "after_carrier_played",
            "target": "inherited",
            "once_per_turn": False,
            "consumes_component": False,
        }
        positional_index = 0
        for raw in args[2:]:
            if ":" in raw:
                key, value = (part.strip() for part in raw.split(":", 1))
                mapped = {
                    "OncePerTurn": "once_per_turn",
                    "ConsumesComponent": "consumes_component",
                }.get(key)
                if mapped:
                    effect[mapped] = value.lower() == "true"
            elif "MaterialEffectTiming." in raw:
                effect["timing"] = snake_case(raw.split(".")[-1])
            elif "MaterialEffectTarget." in raw:
                effect["target"] = snake_case(raw.split(".")[-1])
            elif positional_index == 0:
                effect["hits"] = int(raw)
                positional_index += 1
        effects.append(effect)
    return effects


def parse_material(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    class_match = re.search(r"class\s+(\w+)\s*:\s*MaterialCard", text)
    if not class_match:
        raise ValueError(f"material class not found in {path}")
    args = find_base_args(text)
    category = args[2].split(".")[-1]
    return {
        "id": snake_case(class_match.group(1)),
        "name": parse_string(args[0]),
        "text": parse_string(args[1]),
        "category": CATEGORY_MAP[category],
        "effects": parse_material_effects(",".join(args[3:])),
    }


def source_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Soyoi card data from the C# rebuild")
    parser.add_argument("source", type=Path, help="Path to SoyoiMod-Rebuild")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "soyoi_port" / "generated_catalog.py",
    )
    args = parser.parse_args()

    cards_dir = args.source / "SoyoiMod" / "SoyoiModCode" / "Cards"
    redesign_path = cards_dir / "RedesignedCardRegistry.cs"
    redesigns = parse_redesigns(redesign_path)
    card_paths = sorted(cards_dir.glob("CurrentCard[0-9][0-9][0-9].cs"))
    cards = [parse_card(path, redesigns) for path in card_paths]

    material_paths = []
    for path in sorted(cards_dir.glob("*.cs")):
        if re.search(r"class\s+\w+\s*:\s*MaterialCard", path.read_text(encoding="utf-8-sig")):
            material_paths.append(path)
    materials = [parse_material(path) for path in material_paths]

    if len(cards) != 80:
        raise RuntimeError(f"expected 80 reward cards, found {len(cards)}")
    if len(materials) != 17:
        raise RuntimeError(f"expected 17 materials, found {len(materials)}")

    source_paths = card_paths + material_paths + [redesign_path]
    source_info = {
        "source_name": "SoyoiMod-Rebuild",
        "source_digest": source_digest(source_paths),
        "reward_card_count": len(cards),
        "material_count": len(materials),
        "note": "Card text is ported; cards marked requires_custom_logic need combat hooks.",
    }
    output = (
        '"""Generated from SoyoiMod-Rebuild. Do not edit by hand."""\n\n'
        f"SOURCE_INFO = {pprint.pformat(source_info, width=100, sort_dicts=False)}\n\n"
        f"REWARD_CARD_DATA = {pprint.pformat(cards, width=120, sort_dicts=False)}\n\n"
        f"MATERIAL_DATA = {pprint.pformat(materials, width=120, sort_dicts=False)}\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8", newline="\n")
    print(f"wrote {len(cards)} cards and {len(materials)} materials to {args.output}")


if __name__ == "__main__":
    main()

