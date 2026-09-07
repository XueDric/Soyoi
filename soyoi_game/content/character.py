"""内容层：数据驱动的角色、卡牌、素材、敌人定义。

队友移植 C# 卡牌时，在这里通过 CardSpec / MaterialCardData 注册即可。
本文件给出示例（基础卡、代表性重做卡、一张素材卡），用于跑通框架并演示接口。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core.cards import (
    Card,
    CardSpec,
    CardType,
    CardRarity,
    CardKeyword,
    TargetType,
    RewardEffectOperation,
    RewardEffectSpec,
)
from ..soyoi.materials import (
    MaterialCategory,
    MaterialEffectOperation,
    MaterialEffectSpec,
    MaterialEffectTiming,
    MaterialEffectTarget,
)
from ..soyoi.card import MaterialCardBase


# ------------------------------------------------------------------
# 素材数据（队友可直接以 MaterialCardBase 实例 / 或工厂函数生成）
# ------------------------------------------------------------------

def make_perler_color_pack() -> MaterialCardBase:
    """拼豆色包：普通素材。示例素材，带一个伤害效果。"""
    return MaterialCardBase(
        card_id="perler_color_pack",
        title="拼豆色包",
        base_cost=0,
        upgraded_cost=0,
        card_type=CardType.SKILL,
        rarity=CardRarity.TOKEN,
        target=TargetType.SELF,
        base_text="普通素材：造成3点伤害。",
        upgraded_text="",
        base_keywords=[CardKeyword.RETAIN],
        material_category=MaterialCategory.NORMAL,
        material_effects=[
            MaterialEffectSpec(
                operation=MaterialEffectOperation.MATERIAL_DAMAGE,
                amount=3,
                timing=MaterialEffectTiming.AFTER_CARRIER_PLAYED,
                target=MaterialEffectTarget.INHERITED,
            ),
        ],
    )


def make_badge_blank() -> MaterialCardBase:
    """吧唧底坯：普通素材，示例给易伤。"""
    return MaterialCardBase(
        card_id="badge_blank",
        title="吧唧底坯",
        base_cost=0,
        upgraded_cost=0,
        card_type=CardType.SKILL,
        rarity=CardRarity.TOKEN,
        target=TargetType.SELF,
        base_text="普通素材：给予1层易伤。",
        upgraded_text="",
        base_keywords=[CardKeyword.RETAIN],
        material_category=MaterialCategory.NORMAL,
        material_effects=[
            MaterialEffectSpec(
                operation=MaterialEffectOperation.APPLY_VULNERABLE,
                amount=1,
                timing=MaterialEffectTiming.AFTER_CARRIER_PLAYED,
                target=MaterialEffectTarget.INHERITED,
            ),
        ],
    )


# 素材工厂注册表（队友移植时往这里加）
MATERIAL_FACTORIES: dict[str, type] = {}


# ------------------------------------------------------------------
# 基础卡（对应 mod StrikeSoyoi / DefendSoyoi）
# ------------------------------------------------------------------

STRIKE_SPEC = CardSpec(
    card_id="strike_soyoi",
    title="打击",
    base_cost=1,
    upgraded_cost=1,
    card_type=CardType.ATTACK,
    rarity=CardRarity.BASIC,
    target=TargetType.ANY_ENEMY,
    base_text="造成6点伤害。",
    upgraded_text="造成9点伤害。",
    base_effects=[RewardEffectSpec(RewardEffectOperation.DAMAGE, 6)],
    upgraded_effects=[RewardEffectSpec(RewardEffectOperation.DAMAGE, 9)],
)

DEFEND_SPEC = CardSpec(
    card_id="defend_soyoi",
    title="防御",
    base_cost=1,
    upgraded_cost=1,
    card_type=CardType.SKILL,
    rarity=CardRarity.BASIC,
    target=TargetType.SELF,
    base_text="获得5点格挡。",
    upgraded_text="获得8点格挡。",
    base_effects=[RewardEffectSpec(RewardEffectOperation.GAIN_BLOCK, 5)],
    upgraded_effects=[RewardEffectSpec(RewardEffectOperation.GAIN_BLOCK, 8)],
)


# ------------------------------------------------------------------
# 代表性重做卡（对应 mod 的 CurrentCard 04/05，演示素材生成与加工）
# ------------------------------------------------------------------
# 这两张卡有"自定义逻辑"（生成素材/加工），无法纯用 RewardEffectSpec 表达，
# 因此框架允许为卡牌提供自定义 play 回调。这里用数据 + 特殊 hook 标记。

# 素材生成器的简易注册（队友可覆写逻辑）
def _gen_and_attach_material(combat, card, target, material_factory):
    """生成一张素材并加工到某张可承载的手牌（简化实现）。

    实际逻辑会比这复杂（要选牌、满槽合料等），这里是挂载点示例。
    """
    from ..soyoi.material_runtime import store, attach_next_available
    from ..soyoi.card import can_carry_materials
    from ..soyoi.materials import MaterialBundle
    player = combat.player
    material = material_factory()
    # 生成素材盒素材并放到手牌
    store(player, material)
    bundle = MaterialBundle.from_material(material)
    # 简化：加工到第一张可承载的手牌
    hand = player.piles.pile(1)
    for c in hand.cards:
        if can_carry_materials(c):
            attach_next_available(player, c, bundle)
            break


# 卡牌自定义行为钩子注册表：card_id -> callable(combat, card, target)
# 队友移植的复杂卡牌在这里挂自定义逻辑。
CARD_BEHAVIORS: dict[str, callable] = {}


def register_card_behavior(card_id: str, fn: callable) -> None:
    CARD_BEHAVIORS[card_id] = fn


# ------------------------------------------------------------------
# 角色定义：所依（酱油部）
# ------------------------------------------------------------------

@dataclass
class CharacterDef:
    """角色定义。对应 C# PlaceholderCharacterModel。"""
    name: str
    starting_hp: int
    starting_deck: list[CardSpec]
    starting_relics: list[str]
    card_pool: list[CardSpec]
    material_pool: list[callable]   # 可生成的普通素材工厂


def build_character() -> CharacterDef:
    """构建"所依"角色定义（对应 Soyoi.cs：起始HP 72，10张起始牌，1个遗物）。"""
    return CharacterDef(
        name="所依",
        starting_hp=72,
        starting_deck=[
            STRIKE_SPEC,
            STRIKE_SPEC,
            STRIKE_SPEC,
            STRIKE_SPEC,
            DEFEND_SPEC,
            DEFEND_SPEC,
            DEFEND_SPEC,
            # RushJob/TouchUp/AskAround 用占位基础牌替代（队友移植后可换成真实卡）
            STRIKE_SPEC,
            DEFEND_SPEC,
            STRIKE_SPEC,
        ],
        starting_relics=["soy_sauce_department_badge"],
        card_pool=[STRIKE_SPEC, DEFEND_SPEC],
        material_pool=[make_perler_color_pack, make_badge_blank],
    )


def instantiate_deck(character: CharacterDef) -> list[Card]:
    """把角色起始牌组数据实例化成真正的 Card 对象。"""
    return [spec.create() for spec in character.starting_deck]
