from soyoi_port import (
    SOYOI,
    CardInstance,
    MaterialInstance,
    attach_material,
    get_card,
    get_material,
)


def main() -> None:
    card = CardInstance(get_card("strike_soyoi"))
    material = MaterialInstance(get_material("perler_color_pack"))
    result = attach_material(card, material)

    print(f"角色：{SOYOI.name}，初始生命：{SOYOI.starting_hp}")
    print(f"{material.definition.name} 已加工到 {card.definition.name}")
    print(f"素材牌应移至：{result.destination_zone}")
    print(f"是否计作正常出牌：{result.counts_as_card_play}")


if __name__ == "__main__":
    main()

