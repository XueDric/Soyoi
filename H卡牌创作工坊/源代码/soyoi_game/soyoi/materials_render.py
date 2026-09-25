"""素材效果的文本渲染与提示。"""

from __future__ import annotations

from .materials import MaterialEffectOperation, MaterialEffectSpec, MaterialEffectTiming, MaterialEffectTarget


def describe_material_effect(effect: MaterialEffectSpec) -> str:
    #把一条素材效果转成可读文字
    amount = effect.amount
    op = effect.operation
    if op == MaterialEffectOperation.MATERIAL_DAMAGE:
        s = f"造成{amount:g}点伤害"
        if effect.hits > 1:
            s += f"×{effect.hits}"
    elif op == MaterialEffectOperation.APPLY_VULNERABLE:
        s = f"给予{amount:g}层易伤"
    elif op == MaterialEffectOperation.APPLY_WEAK:
        s = f"给予{amount:g}层虚弱"
    elif op == MaterialEffectOperation.GAIN_BLOCK:
        s = f"获得{amount:g}点格挡"
    elif op == MaterialEffectOperation.LOSE_STRENGTH_THIS_TURN:
        s = f"敌人本回合力量-{amount:g}"
    elif op == MaterialEffectOperation.GAIN_PLATING:
        s = f"获得{amount:g}层覆甲"
    elif op == MaterialEffectOperation.GRANT_RETAIN:
        s = "获得保留"
    elif op == MaterialEffectOperation.REDUCE_NEXT_COST:
        s = "下次打出耗能降低"
    elif op == MaterialEffectOperation.DRAW_CARDS:
        s = f"抽{amount:g}张牌"
    elif op == MaterialEffectOperation.PUT_OTHER_NON_MATERIAL_FROM_DISCARD_ON_DRAW_PILE:
        s = "从弃牌堆置顶一张非素材牌"
    elif op == MaterialEffectOperation.GAIN_ENERGY:
        s = f"获得{amount:g}点能量"
    elif op == MaterialEffectOperation.RETURN_CARRIER_TO_HAND:
        s = "返回手牌"
    elif op == MaterialEffectOperation.ADD_WOUND_TO_DISCARD:
        s = f"向弃牌堆添加{amount:g}张伤口"
    elif op == MaterialEffectOperation.INCREASE_CARRIER_COST:
        s = f"耗能+{amount:g}"
    else:
        s = op.name

    # 时机后缀
    timing_note = {
        MaterialEffectTiming.PERSISTENT: "（常驻）",
        MaterialEffectTiming.AFTER_CARRIER_NEXT_PLAYED: "（下次打出）",
        MaterialEffectTiming.FIRST_CARRIER_PLAY_EACH_COMBAT: "（首打）",
        MaterialEffectTiming.AFTER_RETAINED_ACROSS_TURN: "（保留后）",
    }.get(effect.timing, "")
    return s + timing_note
