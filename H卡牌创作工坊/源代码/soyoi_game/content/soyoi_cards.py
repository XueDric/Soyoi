"""所依课程 Demo 的 40 张可玩奖励牌。"""

from __future__ import annotations

from ..core.cards import (
    CardKeyword,
    CardRarity,
    CardSpec,
    CardType,
    RewardEffectOperation as Op,
    RewardEffectSpec,
    TargetType,
)


def effect(op: Op, amount: int = 0, hits: int = 1, material_id: str | None = None) -> RewardEffectSpec:
    return RewardEffectSpec(op, amount, hits, material_id)


def attack(
    number: int,
    title: str,
    cost: int,
    rarity: CardRarity,
    text: str,
    upgraded_text: str,
    base: list[RewardEffectSpec],
    upgraded: list[RewardEffectSpec],
    *,
    all_enemies: bool = False,
    exhaust: bool = False,
) -> CardSpec:
    keywords = [CardKeyword.EXHAUST] if exhaust else []
    return CardSpec(
        card_id=f"soyoi_reward_{number:03d}", title=title,
        base_cost=cost, upgraded_cost=cost,
        card_type=CardType.ATTACK, rarity=rarity,
        target=TargetType.ALL_ENEMIES if all_enemies else TargetType.ANY_ENEMY,
        base_text=text, upgraded_text=upgraded_text,
        base_keywords=keywords, upgraded_keywords=list(keywords),
        base_effects=base, upgraded_effects=upgraded,
    )


def skill(
    number: int,
    title: str,
    cost: int,
    rarity: CardRarity,
    text: str,
    upgraded_text: str,
    base: list[RewardEffectSpec],
    upgraded: list[RewardEffectSpec],
    *,
    exhaust: bool = False,
    retain: bool = False,
) -> CardSpec:
    keywords = []
    if exhaust:
        keywords.append(CardKeyword.EXHAUST)
    if retain:
        keywords.append(CardKeyword.RETAIN)
    return CardSpec(
        card_id=f"soyoi_reward_{number:03d}", title=title,
        base_cost=cost, upgraded_cost=cost,
        card_type=CardType.SKILL, rarity=rarity, target=TargetType.SELF,
        base_text=text, upgraded_text=upgraded_text,
        base_keywords=keywords, upgraded_keywords=list(keywords),
        base_effects=base, upgraded_effects=upgraded,
    )


def power(
    number: int,
    title: str,
    cost: int,
    rarity: CardRarity,
    text: str,
    upgraded_text: str,
    base: list[RewardEffectSpec],
    upgraded: list[RewardEffectSpec],
) -> CardSpec:
    # 当前课程框架没有能力牌区域，能力牌打出后进入消耗堆，效果仍永久生效。
    return CardSpec(
        card_id=f"soyoi_reward_{number:03d}", title=title,
        base_cost=cost, upgraded_cost=cost,
        card_type=CardType.POWER, rarity=rarity, target=TargetType.SELF,
        base_text=text, upgraded_text=upgraded_text,
        base_keywords=[CardKeyword.EXHAUST], upgraded_keywords=[CardKeyword.EXHAUST],
        base_effects=base, upgraded_effects=upgraded,
    )


C = CardRarity.COMMON
U = CardRarity.UNCOMMON
R = CardRarity.RARE


COMMON_CARDS = [
    attack(1, "拼豆弹射", 1, C, "造成7点伤害，生成1张拼豆色包。", "造成10点伤害，生成1张拼豆色包。",
           [effect(Op.DAMAGE, 7), effect(Op.ATTACH_MATERIAL, material_id="perler_color_pack")],
           [effect(Op.DAMAGE, 10), effect(Op.ATTACH_MATERIAL, material_id="perler_color_pack")]),
    attack(2, "罐体敲击", 1, C, "造成8点伤害。", "造成11点伤害。",
           [effect(Op.DAMAGE, 8)], [effect(Op.DAMAGE, 11)]),
    attack(3, "电池点火", 1, C, "造成6点伤害，获得1点能量。", "造成9点伤害，获得1点能量。",
           [effect(Op.DAMAGE, 6), effect(Op.GAIN_ENERGY, 1)],
           [effect(Op.DAMAGE, 9), effect(Op.GAIN_ENERGY, 1)]),
    attack(4, "空白胸牌", 1, C, "造成6点伤害，生成1张吧唧底坯。", "造成9点伤害，生成1张吧唧底坯。",
           [effect(Op.DAMAGE, 6), effect(Op.ATTACH_MATERIAL, material_id="badge_blank")],
           [effect(Op.DAMAGE, 9), effect(Op.ATTACH_MATERIAL, material_id="badge_blank")]),
    attack(5, "整面招贴", 1, C, "对所有敌人造成4点伤害。", "对所有敌人造成7点伤害。",
           [effect(Op.DAMAGE, 4)], [effect(Op.DAMAGE, 7)], all_enemies=True),
    attack(6, "压合吊牌", 2, C, "造成14点伤害。消耗。", "造成19点伤害。消耗。",
           [effect(Op.DAMAGE, 14)], [effect(Op.DAMAGE, 19)], exhaust=True),
    skill(7, "裁片包扎", 1, C, "获得7点格挡，生成1张不织布裁片。", "获得10点格挡，生成1张不织布裁片。",
          [effect(Op.GAIN_BLOCK, 7), effect(Op.ATTACH_MATERIAL, material_id="felt_scrap")],
          [effect(Op.GAIN_BLOCK, 10), effect(Op.ATTACH_MATERIAL, material_id="felt_scrap")]),
    skill(8, "活页装订", 1, C, "获得5点格挡，抽1张牌。", "获得8点格挡，抽1张牌。",
          [effect(Op.GAIN_BLOCK, 5), effect(Op.DRAW_CARDS, 1)],
          [effect(Op.GAIN_BLOCK, 8), effect(Op.DRAW_CARDS, 1)]),
    skill(9, "桌面清点", 1, C, "抽2张牌。", "抽3张牌。",
          [effect(Op.DRAW_CARDS, 2)], [effect(Op.DRAW_CARDS, 3)]),
    skill(10, "轮阅册页", 0, C, "抽1张牌。消耗。", "抽2张牌。消耗。",
          [effect(Op.DRAW_CARDS, 1)], [effect(Op.DRAW_CARDS, 2)], exhaust=True),
    attack(11, "吧唧试压", 1, C, "造成8点伤害，给予1层易伤。", "造成11点伤害，给予2层易伤。",
           [effect(Op.DAMAGE, 8), effect(Op.APPLY_VULNERABLE, 1)],
           [effect(Op.DAMAGE, 11), effect(Op.APPLY_VULNERABLE, 2)]),
    attack(12, "拆件", 1, C, "造成7点伤害，生成1张流麻胶液。", "造成10点伤害，生成1张流麻胶液。",
           [effect(Op.DAMAGE, 7), effect(Op.ATTACH_MATERIAL, material_id="liquid_glue")],
           [effect(Op.DAMAGE, 10), effect(Op.ATTACH_MATERIAL, material_id="liquid_glue")]),
    attack(13, "连续打磨", 1, C, "造成2次4点伤害。", "造成2次6点伤害。",
           [effect(Op.DAMAGE, 4, 2)], [effect(Op.DAMAGE, 6, 2)]),
    attack(14, "熨烫拼豆", 2, C, "造成3次5点伤害。", "造成3次7点伤害。",
           [effect(Op.DAMAGE, 5, 3)], [effect(Op.DAMAGE, 7, 3)]),
    attack(15, "流麻封口", 1, C, "造成5点伤害，给予2层虚弱。", "造成8点伤害，给予2层虚弱。",
           [effect(Op.DAMAGE, 5), effect(Op.APPLY_WEAK, 2)],
           [effect(Op.DAMAGE, 8), effect(Op.APPLY_WEAK, 2)]),
    skill(16, "叠贴加固", 1, C, "获得8点格挡和1层覆甲。", "获得11点格挡和2层覆甲。",
          [effect(Op.GAIN_BLOCK, 8), effect(Op.GAIN_PLATING, 1)],
          [effect(Op.GAIN_BLOCK, 11), effect(Op.GAIN_PLATING, 2)]),
    skill(17, "预留工位", 1, C, "获得6点格挡。保留。", "获得9点格挡。保留。",
          [effect(Op.GAIN_BLOCK, 6)], [effect(Op.GAIN_BLOCK, 9)], retain=True),
    skill(18, "清理桌面", 0, C, "获得1点能量。消耗。", "获得1点能量并抽1张牌。消耗。",
          [effect(Op.GAIN_ENERGY, 1)],
          [effect(Op.GAIN_ENERGY, 1), effect(Op.DRAW_CARDS, 1)], exhaust=True),
    skill(19, "不织布挂件", 1, C, "获得7点格挡，生成1张不织布裁片。", "获得11点格挡，生成1张不织布裁片。",
          [effect(Op.GAIN_BLOCK, 7), effect(Op.ATTACH_MATERIAL, material_id="felt_scrap")],
          [effect(Op.GAIN_BLOCK, 11), effect(Op.ATTACH_MATERIAL, material_id="felt_scrap")]),
    skill(20, "摊位展示", 1, C, "获得3层活力和1层荆棘。", "获得5层活力和2层荆棘。",
          [effect(Op.GAIN_VIGOR, 3), effect(Op.GAIN_THORNS, 1)],
          [effect(Op.GAIN_VIGOR, 5), effect(Op.GAIN_THORNS, 2)]),
]


UNCOMMON_CARDS = [
    skill(21, "轮换工位", 1, U, "抽1张牌，生成1张随机素材。", "抽2张牌，生成1张随机素材。",
          [effect(Op.DRAW_CARDS, 1), effect(Op.ATTACH_MATERIAL)],
          [effect(Op.DRAW_CARDS, 2), effect(Op.ATTACH_MATERIAL)]),
    power(22, "批量制作", 1, U, "获得2层覆甲。", "获得3层覆甲。",
          [effect(Op.GAIN_PLATING, 2)], [effect(Op.GAIN_PLATING, 3)]),
    attack(24, "精密连刻", 1, U, "造成2次4点伤害，生成1张拼豆色包。", "造成2次6点伤害，生成1张拼豆色包。",
           [effect(Op.DAMAGE, 4, 2), effect(Op.ATTACH_MATERIAL, material_id="perler_color_pack")],
           [effect(Op.DAMAGE, 6, 2), effect(Op.ATTACH_MATERIAL, material_id="perler_color_pack")]),
    attack(25, "堆料重击", 2, U, "造成18点伤害。", "造成24点伤害。",
           [effect(Op.DAMAGE, 18)], [effect(Op.DAMAGE, 24)]),
    attack(26, "交付展示", 1, U, "造成12点伤害。", "造成16点伤害。",
           [effect(Op.DAMAGE, 12)], [effect(Op.DAMAGE, 16)]),
    skill(27, "周边选材", 1, U, "抽2张牌，生成1张随机素材。", "抽3张牌，生成1张随机素材。",
          [effect(Op.DRAW_CARDS, 2), effect(Op.ATTACH_MATERIAL)],
          [effect(Op.DRAW_CARDS, 3), effect(Op.ATTACH_MATERIAL)]),
    skill(28, "图案复刻", 1, U, "获得7点格挡，抽1张牌。", "获得10点格挡，抽2张牌。",
          [effect(Op.GAIN_BLOCK, 7), effect(Op.DRAW_CARDS, 1)],
          [effect(Op.GAIN_BLOCK, 10), effect(Op.DRAW_CARDS, 2)]),
    skill(29, "整理工位", 1, U, "抽3张牌。消耗。", "抽4张牌。消耗。",
          [effect(Op.DRAW_CARDS, 3)], [effect(Op.DRAW_CARDS, 4)], exhaust=True),
    skill(30, "应急修补", 1, U, "获得12点格挡。消耗。", "获得17点格挡。消耗。",
          [effect(Op.GAIN_BLOCK, 12)], [effect(Op.GAIN_BLOCK, 17)], exhaust=True),
    attack(34, "刻刀连舞", 1, U, "造成3次3点伤害。", "造成3次5点伤害。",
           [effect(Op.DAMAGE, 3, 3)], [effect(Op.DAMAGE, 5, 3)]),
    attack(35, "周边投递", 1, U, "造成11点伤害，给予1层易伤。", "造成15点伤害，给予2层易伤。",
           [effect(Op.DAMAGE, 11), effect(Op.APPLY_VULNERABLE, 1)],
           [effect(Op.DAMAGE, 15), effect(Op.APPLY_VULNERABLE, 2)]),
    attack(36, "返工风暴", 2, U, "对所有敌人造成14点伤害。", "对所有敌人造成19点伤害。",
           [effect(Op.DAMAGE, 14)], [effect(Op.DAMAGE, 19)], all_enemies=True),
    attack(37, "压线完成", 2, U, "造成18点伤害，给予1层虚弱。", "造成24点伤害，给予2层虚弱。",
           [effect(Op.DAMAGE, 18), effect(Op.APPLY_WEAK, 1)],
           [effect(Op.DAMAGE, 24), effect(Op.APPLY_WEAK, 2)]),
    skill(38, "深夜清单", 0, U, "失去2点生命，抽2张牌。", "失去1点生命，抽3张牌。",
          [effect(Op.LOSE_HP, 2), effect(Op.DRAW_CARDS, 2)],
          [effect(Op.LOSE_HP, 1), effect(Op.DRAW_CARDS, 3)]),
    skill(39, "自封袋收纳", 1, U, "获得9点格挡，生成1张自封袋。", "获得13点格挡，生成1张自封袋。",
          [effect(Op.GAIN_BLOCK, 9), effect(Op.ATTACH_MATERIAL, material_id="self_sealing_bag")],
          [effect(Op.GAIN_BLOCK, 13), effect(Op.ATTACH_MATERIAL, material_id="self_sealing_bag")]),
]


RARE_CARDS = [
    attack(57, "最后通牒", 3, R, "造成30点伤害，给予2层易伤和虚弱。", "造成40点伤害，给予3层易伤和虚弱。",
           [effect(Op.DAMAGE, 30), effect(Op.APPLY_VULNERABLE, 2), effect(Op.APPLY_WEAK, 2)],
           [effect(Op.DAMAGE, 40), effect(Op.APPLY_VULNERABLE, 3), effect(Op.APPLY_WEAK, 3)]),
    attack(60, "一刀定型", 0, R, "造成18点伤害。消耗。", "造成24点伤害。消耗。",
           [effect(Op.DAMAGE, 18)], [effect(Op.DAMAGE, 24)], exhaust=True),
    power(66, "高压专注", 2, R, "获得2点力量。", "获得3点力量。",
          [effect(Op.GAIN_STRENGTH, 2)], [effect(Op.GAIN_STRENGTH, 3)]),
    skill(72, "大休息", 3, R, "获得24点格挡，回复5点生命。", "获得32点格挡，回复8点生命。",
          [effect(Op.GAIN_BLOCK, 24), effect(Op.HEAL, 5)],
          [effect(Op.GAIN_BLOCK, 32), effect(Op.HEAL, 8)]),
    attack(77, "双刻", 1, R, "造成2次6点伤害，生成1张随机素材。", "造成2次9点伤害，生成1张随机素材。",
           [effect(Op.DAMAGE, 6, 2), effect(Op.ATTACH_MATERIAL)],
           [effect(Op.DAMAGE, 9, 2), effect(Op.ATTACH_MATERIAL)]),
]


PLAYABLE_REWARD_CARDS = COMMON_CARDS + UNCOMMON_CARDS + RARE_CARDS
PLAYABLE_REWARD_CARDS_BY_ID = {card.card_id: card for card in PLAYABLE_REWARD_CARDS}

assert len(PLAYABLE_REWARD_CARDS) == 40
assert len(PLAYABLE_REWARD_CARDS_BY_ID) == 40
