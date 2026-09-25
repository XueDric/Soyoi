"""游戏脚本加载器：不改代码就能加敌人 / 定制行动套路。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core.cards import RewardEffectOperation
from ..core.enemy import Intent, IntentAction
from .enemies import WOUND_SPEC, SoyoiEnemy, register_enemy

# 内置脚本目录（仓库里自带示例）
DEFAULT_SCRIPT_DIR = Path(__file__).resolve().parent / "enemy_scripts"

# effect=xxx 支持的几种状态
EFFECT_KEYWORDS = {
    "weak": RewardEffectOperation.APPLY_WEAK,
    "vulnerable": RewardEffectOperation.APPLY_VULNERABLE,
    "lose_hp": RewardEffectOperation.LOSE_HP,
}

# appearance 里的形状，和界面的画法一一对应
SHAPES = ("beast", "robe", "thief", "robot", "colossus")

DEFAULT_APPEARANCE = {"shape": "beast", "color": (120, 110, 96), "accent": (235, 177, 47)}


class ScriptError(ValueError):
    """脚本写错了。消息里会带上文件名和行号，方便照着改。"""


# ===== 一、把脚本文字解析成"一只敌人的定义" =====
@dataclass
class EnemyScript:
    """一个脚本解析出来的结果。"""

    enemy_id: str
    name: str
    hp: int
    flavor: str
    appearance: dict
    actions: list[Intent]
    path: Path

    def summary(self) -> str:
        lines = [f"{self.name}（{self.enemy_id}）生命 {self.hp}"]
        if self.flavor:
            lines.append(f"  台词：{self.flavor}")
        for index, intent in enumerate(self.actions, start=1):
            lines.append(f"  回合{index}：{intent.text}")
        return "\n".join(lines)


def _parse_appearance(text: str, where: str) -> dict:
    """解析 `robot / 96,112,122 / 218,91,75` 这种外观写法。"""
    parts = [piece.strip() for piece in text.split("/")]
    shape = parts[0] if parts and parts[0] else "beast"
    if shape not in SHAPES:
        raise ScriptError(f"{where}：appearance 的形状只能是 {'/'.join(SHAPES)}，现在是「{shape}」")

    def color(piece: str, fallback):
        if not piece:
            return fallback
        numbers = [int(value) for value in piece.replace(" ", "").split(",")]
        if len(numbers) != 3 or not all(0 <= value <= 255 for value in numbers):
            raise ScriptError(f"{where}：颜色要写成 0~255 的三个数字，例如 218,91,75")
        return tuple(numbers)

    return {
        "shape": shape,
        "color": color(parts[1] if len(parts) > 1 else "", DEFAULT_APPEARANCE["color"]),
        "accent": color(parts[2] if len(parts) > 2 else "", DEFAULT_APPEARANCE["accent"]),
    }


def parse_action(line: str, where: str) -> Intent:
    """解析一行动作，例如 `attack 6 x3 effect=weak 2 stuff=1`。"""
    pieces = line.split()
    action = pieces[0].lower()
    options = [piece for piece in pieces[1:] if "=" in piece]
    numbers = [piece for piece in pieces[1:] if "=" not in piece]

    amount = 0
    hits = 1
    for piece in numbers:
        if piece.lower().startswith("x"):          # x3 表示三段
            hits = int(piece[1:])
        else:
            amount = int(piece)

    effect = None
    effect_amount = 0
    stuff = 0
    for option in options:
        key, _, value = option.partition("=")
        key = key.lower()
        if key == "effect":
            effect_parts = value.split(",")
            effect_name = effect_parts[0].lower()
            if effect_name not in EFFECT_KEYWORDS:
                raise ScriptError(
                    f"{where}：effect 只支持 {'/'.join(EFFECT_KEYWORDS)}，现在是「{effect_name}」"
                )
            effect = EFFECT_KEYWORDS[effect_name]
            effect_amount = int(effect_parts[1]) if len(effect_parts) > 1 else 1
        elif key == "stuff":
            stuff = int(value)
        else:
            raise ScriptError(f"{where}：不认识的选项「{key}」（可用：effect / stuff）")

    if action == "attack":
        if amount <= 0:
            raise ScriptError(f"{where}：attack 后面要写伤害，例如 attack 6")
        return Intent(IntentAction.ATTACK, amount, max(1, hits), "",
                      effect_operation=effect, effect_amount=effect_amount,
                      card_spec=WOUND_SPEC if stuff else None)
    if action == "defend":
        if amount <= 0:
            raise ScriptError(f"{where}：defend 后面要写格挡数，例如 defend 6")
        return Intent(IntentAction.DEFEND, amount, 1, "")
    if action == "buff":
        if amount <= 0:
            raise ScriptError(f"{where}：buff 后面要写力量层数，例如 buff 2")
        return Intent(IntentAction.BUFF, amount, 1, "")

    raise ScriptError(
        f"{where}：不认识的动作「{action}」（只有 attack / defend / buff 三种）"
    )


def parse_script(text: str, path: Path | None = None) -> EnemyScript:
    """把脚本内容解析成 EnemyScript。写错就抛 ScriptError（带行号）。"""
    where = path.name if path else "脚本"
    fields: dict[str, str] = {}
    actions: list[Intent] = []

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()   # 井号后面是注释
        if not line:
            continue
        if "=" in line and not line.lower().startswith(("attack", "defend", "buff")):
            key, _, value = line.partition("=")
            fields[key.strip().lower()] = value.strip()
            continue
        actions.append(parse_action(line, f"{where} 第 {number} 行"))

    name = fields.get("name", "").strip()
    if not name:
        raise ScriptError(f"{where}：缺少 name（敌人名字）")
    try:
        hp = int(fields.get("hp", "40"))
    except ValueError as error:
        raise ScriptError(f"{where}：hp 要填整数") from error
    if hp <= 0:
        raise ScriptError(f"{where}：hp 要大于 0")
    if not actions:
        raise ScriptError(f"{where}：至少要写一个动作（attack / defend / buff）")

    enemy_id = fields.get("id", "").strip() or name
    appearance = _parse_appearance(fields.get("appearance", ""), where)
    return EnemyScript(
        enemy_id=enemy_id,
        name=name,
        hp=hp,
        flavor=fields.get("flavor", "").strip(),
        appearance=appearance,
        actions=actions,
        path=path or Path(f"{name}.txt"),
    )


# ===== 二、把脚本变成游戏里能用的敌人 =====
class ScriptedEnemy(SoyoiEnemy):
    """脚本敌人：套路就是脚本里那串动作，按顺序循环。"""

    def __init__(self, script: EnemyScript) -> None:
        super().__init__(script.name, script.hp, flavor=script.flavor)
        self.script = script
        self.appearance = dict(script.appearance)
        self.enemy_id = script.enemy_id      # 界面按编号找立绘
        # 顺带带上界面要显示的信息（这怪来自哪个脚本）
        self.source = script.path.name

    def choose_intent(self, combat) -> Intent:
        actions = self.script.actions
        return actions[(self.turn - 1) % len(actions)]


def make_script_enemy(script: EnemyScript) -> ScriptedEnemy:
    """按脚本造一只敌人。"""
    return ScriptedEnemy(script)


def register_script(script: EnemyScript) -> str:
    """把脚本里的敌人注册进敌人表，返回编号（注册后命令行就能选它）。"""
    register_enemy(script.enemy_id, script.name, lambda: make_script_enemy(script))
    return script.enemy_id


# ===== 三、加载脚本目录 =====
@dataclass
class LoadReport:
    """加载结果：成功注册的敌人 + 每个坏脚本的原因。"""

    loaded: list[EnemyScript]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        lines = [f"脚本敌人：{len(self.loaded)} 只"]
        lines += [f"  {script.name}（{script.enemy_id}）{len(script.actions)} 个动作"
                  for script in self.loaded]
        for error in self.errors:
            lines.append(f"  [跳过] {error}")
        return "\n".join(lines)


def load_script_file(path: Path) -> EnemyScript:
    """加载一个脚本文件并注册。失败抛 ScriptError。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ScriptError(f"{Path(path).name}：读不了这个文件（{error}）") from error
    script = parse_script(text, Path(path))
    register_script(script)
    return script


def load_scripts(directory: Path | str | None = None) -> LoadReport:
    """加载一个目录里所有 .txt 脚本。"""
    folder = Path(directory) if directory else DEFAULT_SCRIPT_DIR
    loaded: list[EnemyScript] = []
    errors: list[str] = []
    if not folder.exists():
        return LoadReport(loaded, [f"脚本目录不存在：{folder}"])
    for path in sorted(folder.glob("*.txt")):
        try:
            loaded.append(load_script_file(path))
        except ScriptError as error:
            errors.append(str(error))
    return LoadReport(loaded, errors)


def load_default_scripts() -> LoadReport:
    """加载仓库里自带的示例脚本（`content/enemy_scripts/`）。"""
    return load_scripts(DEFAULT_SCRIPT_DIR)


def load_script_list(directories: list[str] | None) -> LoadReport:
    """加载多个目录（命令行可以传好几次 --scripts）。"""
    total = LoadReport([], [])
    for directory in directories or []:
        report = load_scripts(directory)
        total.loaded.extend(report.loaded)
        total.errors.extend(report.errors)
    return total
