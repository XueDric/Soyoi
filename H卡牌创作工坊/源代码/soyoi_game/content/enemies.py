"""敌人设计：五只怪，意图只有攻击 / 防御 / 强化三种。"""

from __future__ import annotations

import random

from ..core.cards import (
    CardKeyword,
    CardRarity,
    CardSpec,
    CardType,
    RewardEffectOperation,
    TargetType,
)
from ..core.enemy import Enemy, Intent, IntentAction


# ===== 一、废牌「铁屑」：Boss 攻击时塞进你的弃牌堆 =====
WOUND_SPEC = CardSpec(
    card_id="wound_scrap", title="铁屑",
    base_cost=0, upgraded_cost=0,
    card_type=CardType.SKILL, rarity=CardRarity.TOKEN,
    target=TargetType.NONE,
    base_text="无法打出。", upgraded_text="无法打出。",
    base_keywords=[CardKeyword.UNPLAYABLE],
    upgraded_keywords=[CardKeyword.UNPLAYABLE],
    base_effects=[],
    upgraded_effects=[],
)


def make_wound():
    """造一张铁屑（会被塞进玩家弃牌堆）。"""
    return WOUND_SPEC.create()


# ===== 二、敌人基类：只管数回合，子类只挑意图 =====
class SoyoiEnemy(Enemy):
    """所有敌人的父类。"""

    appearance = {
        "shape": "beast",       # beast / robe / thief / robot / colossus
        "color": (120, 110, 96),
        "accent": (235, 177, 47),
    }

    def __init__(self, name: str, max_hp: int, *, flavor: str = "") -> None:
        super().__init__(name=name, max_hp=max_hp, brain=self._choose)
        self.turn = 0            # 已经行动过几回合（第 1 回合是 1）
        self.flavor = flavor     # 出场台词，让敌人有性格
        self.phase = 1           # 阶段（Boss 换阶段用）

    def _choose(self, _enemy, combat) -> Intent:
        self.turn += 1
        return self.choose_intent(combat)

    def choose_intent(self, combat) -> Intent:
        """决定这回合做什么。子类必须实现。"""
        raise NotImplementedError

    # --- 三个小工具，对应三种意图，省得每只怪手写 Intent ---
    @staticmethod
    def attack(amount: int, hits: int = 1, label: str = "",
               effect: RewardEffectOperation | None = None, effect_amount: int = 0,
               card_spec=None) -> Intent:
        """攻击：造成伤害（hits 段），可选附带状态或塞废牌。"""
        return Intent(IntentAction.ATTACK, amount, hits, label,
                      effect_operation=effect, effect_amount=effect_amount, card_spec=card_spec)

    @staticmethod
    def defend(amount: int, label: str = "") -> Intent:
        """防御：给自己加格挡。"""
        return Intent(IntentAction.DEFEND, amount, 1, label)

    @staticmethod
    def buff(amount: int, label: str = "") -> Intent:
        """强化：给自己加力量。"""
        return Intent(IntentAction.BUFF, amount, 1, label)


# ===== 三、五只敌人 =====
class JawWorm(SoyoiEnemy):
    """颚虫：最基础的敌人，三段循环 —— 用来教学"看意图做决策"。"""

    appearance = {"shape": "beast", "color": (131, 108, 84), "accent": (235, 177, 47)}

    def __init__(self) -> None:
        super().__init__("颚虫", 44, flavor="它张开嘴，像是在数你的血条。")

    def choose_intent(self, combat) -> Intent:
        step = (self.turn - 1) % 3 + 1
        if step == 1:
            return self.attack(11, label="啃咬 11")
        if step == 2:
            return self.defend(6, label="硬化 格挡6")
        return self.attack(7, label="甩尾 7")


class Cultist(SoyoiEnemy):
    """邪教徒：第一回合必定先强化，之后连续攻击 —— 拖越久越痛。"""

    appearance = {"shape": "robe", "color": (78, 66, 102), "accent": (218, 91, 75)}

    def __init__(self) -> None:
        super().__init__("邪教徒", 52, flavor="仪式开始了。")

    def choose_intent(self, combat) -> Intent:
        if self.turn == 1:
            return self.buff(3, label="仪式 力量+3")
        return self.attack(6, label="鞭击 6")


class Looter(SoyoiEnemy):
    """摸金校尉：偷完就跑，用格挡拖时间。"""

    appearance = {"shape": "thief", "color": (92, 104, 78), "accent": (238, 190, 62)}

    def __init__(self) -> None:
        super().__init__("摸金校尉", 46, flavor="值钱的我都拿走了。")

    def choose_intent(self, combat) -> Intent:
        step = (self.turn - 1) % 4 + 1
        if step == 1:
            return self.attack(10, label="偷窃 10")
        if step == 2:
            return self.attack(5, 2, label="扒手 5×2")
        if step == 3:
            return self.defend(18, label="逃跑 格挡18")
        return self.attack(4, effect=RewardEffectOperation.APPLY_WEAK, effect_amount=2,
                           label="烟雾弹 4+虚弱2")


class Sentry(SoyoiEnemy):
    """铁皮哨卫：血多时蓄力+重击，血量过半改成四连击。"""

    appearance = {"shape": "robot", "color": (96, 112, 122), "accent": (218, 91, 75)}

    def __init__(self) -> None:
        super().__init__("铁皮哨卫", 60, flavor="齿轮转动，红光扫过你。")

    def choose_intent(self, combat) -> Intent:
        if self.hp <= self.max_hp // 2:
            return self.attack(8, 4, label="过载连击 8×4")   # 狂怒：四连击
        step = (self.turn - 1) % 3 + 1
        if step == 1:
            return self.buff(2, label="蓄力 力量+2")
        if step == 2:
            return self.attack(16, label="重击 16")
        return self.defend(8, label="装甲 格挡8")


class ScrapColossus(SoyoiEnemy):
    """废料巨像：Boss。血量过半进入第二阶段，攻击更凶还会往你牌堆塞铁屑。"""

    appearance = {"shape": "colossus", "color": (74, 68, 64), "accent": (218, 91, 75)}

    def __init__(self) -> None:
        super().__init__("废料巨像", 140, flavor="它由无数被丢弃的零件拧成。")

    def choose_intent(self, combat) -> Intent:
        self.phase = 2 if self.hp <= self.max_hp // 2 else 1

        if self.phase == 2:
            step = (self.turn - 1) % 3 + 1
            if step == 1:
                return self.attack(6, 3, label="碾压 6×3")
            if step == 2:
                return self.attack(4, 2, label="灌铁屑 4×2", card_spec=WOUND_SPEC)
            return self.attack(18, label="重锤 18")

        step = (self.turn - 1) % 4 + 1
        if step == 1:
            return self.buff(2, label="上紧发条 力量+2")
        if step == 3:
            return self.defend(12, label="铁壳 格挡12")
        return self.attack(12, label="挥砸 12")


# ===== 四、敌人总表：命令行、随机出场、外置脚本都注册在这里 =====
BUILTIN_ENEMIES = {
    "jaw_worm": ("颚虫", JawWorm),
    "cultist": ("邪教徒", Cultist),
    "looter": ("摸金校尉", Looter),
    "sentry": ("铁皮哨卫", Sentry),
    "scrap_colossus": ("废料巨像", ScrapColossus),
}

# 运行时可以再往里加（比如脚本加载的敌人）
ENEMY_TYPES: dict[str, tuple[str, object]] = dict(BUILTIN_ENEMIES)

# 随机出场时只抽普通怪，Boss 要显式指定（和这类游戏一样）
NORMAL_ENEMY_IDS = ["jaw_worm", "cultist", "looter", "sentry"]
BOSS_ENEMY_IDS = ["scrap_colossus"]

DEFAULT_ENEMY_ID = "jaw_worm"


def register_enemy(enemy_id: str, name: str, factory) -> None:
    """注册一只敌人（脚本加载器会调它，一般不用手写）。"""
    ENEMY_TYPES[str(enemy_id)] = (str(name), factory)


def make_enemy(enemy_id: str = DEFAULT_ENEMY_ID) -> SoyoiEnemy:
    """按编号或中文名造一个敌人。编号非法时给出可选清单。"""
    if enemy_id in ENEMY_TYPES:
        enemy = ENEMY_TYPES[enemy_id][1]()
        enemy.enemy_id = enemy_id          # 界面按编号找立绘
        return enemy
    for key, (title, cls) in ENEMY_TYPES.items():
        if title == enemy_id:
            enemy = cls()
            enemy.enemy_id = key
            return enemy
    raise ValueError(
        f"没有这个敌人：{enemy_id}（可选：{'、'.join(ENEMY_TYPES)}，或 random）"
    )


def random_enemy(rng: random.Random | None = None) -> SoyoiEnemy:
    """随机抽一只普通敌人（脚本加的怪也会一起参与抽）。"""
    rng = rng or random
    candidates = [enemy_id for enemy_id in NORMAL_ENEMY_IDS if enemy_id in ENEMY_TYPES]
    return make_enemy(rng.choice(candidates))


def make_enemy_by_name(name: str = "random") -> SoyoiEnemy:
    """按编号 / 中文名 / `random` 造敌人（战斗界面和 main.py 都走这个）。"""
    if name in ("random", ""):
        return random_enemy()
    return make_enemy(name)


def enemy_choices() -> list[str]:
    """所有可选的敌人编号（给命令行 choices 用）。"""
    return list(ENEMY_TYPES) + ["random"]


def enemy_kind(enemy_id: str) -> str:
    """这只怪的档位：普通 / BOSS / 脚本（脚本加载进来的都算这一类）。"""
    if enemy_id in NORMAL_ENEMY_IDS:
        return "普通"
    if enemy_id in BOSS_ENEMY_IDS:
        return "BOSS"
    return "脚本"


def enemy_catalog() -> list[dict]:
    """敌人清单（给界面挑对手用）：编号、名字、生命、档位。"""
    order = [e for e in NORMAL_ENEMY_IDS if e in ENEMY_TYPES]
    order += [e for e in ENEMY_TYPES if e not in NORMAL_ENEMY_IDS and e not in BOSS_ENEMY_IDS]
    order += [e for e in BOSS_ENEMY_IDS if e in ENEMY_TYPES]

    catalog = []
    for enemy_id in order:
        name, factory = ENEMY_TYPES[enemy_id]
        try:
            hp = int(factory().max_hp)
        except Exception:      # 脚本怪是玩家自己写的：某一只造不出来就跳过它，别让整个清单挂掉
            hp = 0
        catalog.append({"enemy_id": enemy_id, "name": name, "hp": hp, "kind": enemy_kind(enemy_id)})
    return catalog


def enemy_list() -> str:
    """敌人清单，给命令行和文档显示。"""
    lines = ["普通敌人（--enemy 后面可以填编号或中文名）："]
    for enemy_id in NORMAL_ENEMY_IDS:
        if enemy_id in ENEMY_TYPES:
            lines.append(f"  {enemy_id:<18} {ENEMY_TYPES[enemy_id][0]}")
    others = [key for key in ENEMY_TYPES if key not in NORMAL_ENEMY_IDS and key not in BOSS_ENEMY_IDS]
    if others:
        lines.append("脚本加载的敌人：")
        for enemy_id in others:
            lines.append(f"  {enemy_id:<18} {ENEMY_TYPES[enemy_id][0]}")
    lines.append("Boss：")
    for enemy_id in BOSS_ENEMY_IDS:
        if enemy_id in ENEMY_TYPES:
            lines.append(f"  {enemy_id:<18} {ENEMY_TYPES[enemy_id][0]}")
    lines.append(f"  {'random':<18} 随机一只普通敌人（默认）")
    return "\n".join(lines)
