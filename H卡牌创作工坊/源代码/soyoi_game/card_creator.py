"""卡牌的数据层：表单 -> 记录 -> JSON，再把卡组拼成一副能打的牌。"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

from .content.character import build_character, setup_soyoi_combat
from . import app_root, resource_root
from .core.cards import (
    CardKeyword,
    CardRarity,
    CardSpec,
    CardType,
    RewardEffectOperation,
    RewardEffectSpec,
    TargetType,
)
from .core.combat import CombatState
from .core.enemy import Enemy, Intent, IntentAction
from .core.player import Player
from .soyoi.card import MaterialCardSpec
from .soyoi.materials import (
    MaterialCategory,
    MaterialEffectOperation,
    MaterialEffectSpec,
    MaterialEffectTarget,
    MaterialEffectTiming,
)

# ===== 一、常量表：能填什么、有什么限制 =====
PROJECT_DIR = app_root()                           # 程序根目录（打包后是 exe 所在目录）
CARDS_DIR = PROJECT_DIR / "user_cards"             # 玩家作品存放目录
DECKS_DIR = PROJECT_DIR / "user_decks"             # 玩家卡组存放目录（一个卡组一个文件）
ASSETS_DIR = resource_root() / "assets"            # 只读资源（打包后被解包到临时目录）
DECK_FILE_NAME = "test_deck.json"                  # 老版本的牌组清单（会被自动搬成卡组）
SELECTED_DECK_FILE = "selected.json"               # 记着"对局用哪副卡组"
SCHEMA_VERSION = 1                                 # JSON 格式版本

# 新建卡组的底子：4 张打击 + 4 张防御
BASE_DECK_CARDS = {"strike_soyoi": 4, "defend_soyoi": 4}
SAMPLE_DECK_ID = "sample"                          # 内置示例卡组（只读）
SAMPLE_DECK_NAME = "示例卡组"
MAX_DECK_COPIES = 10                               # 同一种牌在卡组里最多放几张

MAX_NAME_LENGTH = 20       # 卡名最多 20 字
MAX_DESCRIPTION_LENGTH = 60
MIN_COST, MAX_COST = 0, 3  # 费用 0~3
MIN_HITS, MAX_HITS = 1, 4  # 多段攻击最多 4 段
MAX_EFFECTS = 3            # 一张牌最多 3 条效果
CARDS_PER_TEST_DECK = 3    # 命令行示例卡（main.py --demo）默认放几份；界面里由「份数」框决定

# 卡面图复制进 user_cards/art/，记录里只存相对路径。
ART_DIR_NAME = "art"
ART_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
MAX_ART_BYTES = 4 * 1024 * 1024            # 单张卡面图最大 4 MB

# 能选的效果：代码里用英文键，中文名放 *_LABELS 给界面。
EFFECTS = {
    "damage": RewardEffectOperation.DAMAGE,
    "block": RewardEffectOperation.GAIN_BLOCK,
    "draw": RewardEffectOperation.DRAW_CARDS,
    "energy": RewardEffectOperation.GAIN_ENERGY,
    "vulnerable": RewardEffectOperation.APPLY_VULNERABLE,
    "weak": RewardEffectOperation.APPLY_WEAK,
    "strength": RewardEffectOperation.GAIN_STRENGTH,
    "heal": RewardEffectOperation.HEAL,
    "lose_hp": RewardEffectOperation.LOSE_HP,
    "attach_material": RewardEffectOperation.ATTACH_MATERIAL,
}
# 英文键 -> 界面上的中文名
EFFECT_LABELS = {
    "damage": "造成伤害",
    "block": "获得格挡",
    "draw": "抽牌",
    "energy": "获得能量",
    "vulnerable": "施加易伤",
    "weak": "施加减弱",
    "strength": "获得力量",
    "heal": "回复生命",
    "lose_hp": "失去生命",
    "attach_material": "生成素材",
}
# 只有伤害类效果分多段（普通伤害和素材伤害都算）
DAMAGE_EFFECTS = ("damage", "material_damage")
# 每种效果的数值范围
VALUE_LIMITS = {
    "damage": (1, 999),
    "block": (1, 999),
    "draw": (1, 5),
    "energy": (1, 3),
    "vulnerable": (1, 9),
    "weak": (1, 9),
    "strength": (1, 9),
    "heal": (1, 999),
    "lose_hp": (1, 999),
    "attach_material": (0, 0),  # 这种效果不用填数值
}
# 卡面文字模板：{value} 会被替换成实际数值
EFFECT_TEXTS = {
    "damage": "造成{value}点伤害。",
    "block": "获得{value}点格挡。",
    "draw": "抽{value}张牌。",
    "energy": "获得{value}点能量。",
    "vulnerable": "给予{value}层易伤。",
    "weak": "给予{value}层虚弱。",
    "strength": "获得{value}点力量。",
    "heal": "回复{value}点生命。",
    "lose_hp": "失去{value}点生命。",
    "attach_material": "生成1张随机素材。",
}

# ===== 素材牌：不能打出，装到别的牌上才生效 =====
MATERIAL_CATEGORIES = {
    "one_shot": MaterialCategory.ONE_SHOT,
    "normal": MaterialCategory.NORMAL,
    "permanent": MaterialCategory.PERMANENT,
    "curse": MaterialCategory.CURSE,
}
MATERIAL_CATEGORY_NAMES = {
    "one_shot": "一次性",
    "normal": "普通",
    "permanent": "永久",
    "curse": "诅咒",
}

# 素材能做哪些事
MATERIAL_EFFECTS = {
    "material_damage": MaterialEffectOperation.MATERIAL_DAMAGE,
    "material_block": MaterialEffectOperation.GAIN_BLOCK,
    "material_vulnerable": MaterialEffectOperation.APPLY_VULNERABLE,
    "material_weak": MaterialEffectOperation.APPLY_WEAK,
    "material_energy": MaterialEffectOperation.GAIN_ENERGY,
    "material_draw": MaterialEffectOperation.DRAW_CARDS,
    "material_plating": MaterialEffectOperation.GAIN_PLATING,
    "material_retain": MaterialEffectOperation.GRANT_RETAIN,
    "material_cost": MaterialEffectOperation.INCREASE_CARRIER_COST,
}
# 英文键 -> 界面上的中文名
MATERIAL_EFFECT_LABELS = {
    "material_damage": "造成伤害",
    "material_block": "获得格挡",
    "material_vulnerable": "给予易伤",
    "material_weak": "给予虚弱",
    "material_energy": "获得能量",
    "material_draw": "抽牌",
    "material_plating": "获得覆甲",
    "material_retain": "承载牌可保留",
    "material_cost": "承载牌耗能+1",
}
MATERIAL_VALUE_LIMITS = {
    "material_damage": (1, 999),
    "material_block": (1, 999),
    "material_vulnerable": (1, 9),
    "material_weak": (1, 9),
    "material_energy": (1, 3),
    "material_draw": (1, 5),
    "material_plating": (1, 9),
    "material_retain": (0, 0),   # 这条不用填数值
    "material_cost": (1, 3),
}
MATERIAL_EFFECT_TEXTS = {
    "material_damage": "承载牌打出后额外造成{value}点伤害。",
    "material_block": "承载牌打出后获得{value}点格挡。",
    "material_vulnerable": "承载牌打出后给予{value}层易伤。",
    "material_weak": "承载牌打出后给予{value}层虚弱。",
    "material_energy": "承载牌打出后获得{value}点能量。",
    "material_draw": "承载牌打出后抽{value}张牌。",
    "material_plating": "承载牌打出后获得{value}层覆甲。",
    "material_retain": "承载牌可跨回合保留。",
    "material_cost": "承载牌耗能+{value}。",
}
# 素材效果作用于谁、何时触发（口径同 content/materials.py）
MATERIAL_EFFECT_TARGETS = {
    "material_damage": MaterialEffectTarget.INHERITED,
    "material_block": MaterialEffectTarget.OWNER,
    "material_vulnerable": MaterialEffectTarget.INHERITED,
    "material_weak": MaterialEffectTarget.INHERITED,
    "material_energy": MaterialEffectTarget.OWNER,
    "material_draw": MaterialEffectTarget.OWNER,
    "material_plating": MaterialEffectTarget.OWNER,
    "material_retain": MaterialEffectTarget.CARRIER,
    "material_cost": MaterialEffectTarget.CARRIER,
}
MATERIAL_EFFECT_TIMINGS = {
    "material_retain": MaterialEffectTiming.PERSISTENT,
    "material_cost": MaterialEffectTiming.PERSISTENT,
}

# 卡牌类型 / 目标 / 稀有度：英文键 -> 战斗系统枚举
CARD_TYPES = {
    "attack": CardType.ATTACK,
    "skill": CardType.SKILL,
    "power": CardType.POWER,
    "material": CardType.SKILL,
}
CARD_TYPE_NAMES = {"attack": "攻击", "skill": "技能", "power": "能力", "material": "素材"}
TARGETS = {"self": TargetType.SELF, "enemy": TargetType.ANY_ENEMY, "all": TargetType.ALL_ENEMIES}
TARGET_NAMES = {"self": "自己", "enemy": "单个敌人", "all": "所有敌人"}
RARITIES = {
    "basic": CardRarity.BASIC,
    "common": CardRarity.COMMON,
    "uncommon": CardRarity.UNCOMMON,
    "rare": CardRarity.RARE,
}
RARITY_NAMES = {"basic": "基础", "common": "普通", "uncommon": "罕见", "rare": "稀有"}
KEYWORDS = {"exhaust": "消耗", "retain": "保留"}
# 关键字 -> 引擎的关键字枚举（要进对局靠这张表）
CARD_KEYWORDS = {"exhaust": CardKeyword.EXHAUST, "retain": CardKeyword.RETAIN}


class Choice(str):
    """下拉框选项：既是英文键（存 JSON），也能取中文名和枚举。"""

    def __new__(cls, key, label, enum_value=None):
        obj = super().__new__(cls, key)
        obj.key = key
        obj._label = label
        obj._enum = enum_value
        return obj

    @property
    def label(self):
        return self._label

    @property
    def value(self):
        return self.key

    @property
    def enum(self):
        return self._enum


# 界面按下拉框中文名找选项时用这几张表
CARD_TYPE_CHOICES = {
    "attack": Choice("attack", CARD_TYPE_NAMES["attack"], CARD_TYPES["attack"]),
    "skill": Choice("skill", CARD_TYPE_NAMES["skill"], CARD_TYPES["skill"]),
    "power": Choice("power", CARD_TYPE_NAMES["power"], CARD_TYPES["power"]),
    "material": Choice("material", CARD_TYPE_NAMES["material"], CARD_TYPES["material"]),
}
MATERIAL_CATEGORY_CHOICES = {
    key: Choice(key, MATERIAL_CATEGORY_NAMES[key], MATERIAL_CATEGORIES[key])
    for key in MATERIAL_CATEGORIES
}
RARITY_CHOICES = {
    "basic": Choice("basic", RARITY_NAMES["basic"], RARITIES["basic"]),
    "common": Choice("common", RARITY_NAMES["common"], RARITIES["common"]),
    "uncommon": Choice("uncommon", RARITY_NAMES["uncommon"], RARITIES["uncommon"]),
    "rare": Choice("rare", RARITY_NAMES["rare"], RARITIES["rare"]),
}
TARGET_CHOICES = {
    "self": Choice("self", TARGET_NAMES["self"], TARGETS["self"]),
    "enemy": Choice("enemy", TARGET_NAMES["enemy"], TARGETS["enemy"]),
    "all": Choice("all", TARGET_NAMES["all"], TARGETS["all"]),
}
KEYWORD_DEFS = {
    "exhaust": ("消耗", KEYWORDS["exhaust"]),
    "retain": ("保留", KEYWORDS["retain"]),
}


def cards_folder(directory=None):
    """卡牌目录：传了就用传进来的，没传就用默认的 user_cards/。"""
    return Path(directory) if directory else CARDS_DIR


# ===== 一之二、卡面插画 =====
def art_folder(directory=None):
    """卡面插画目录：user_cards/art/（跟卡牌放在一起，方便整个目录备份/搬家）。"""
    return cards_folder(directory) / ART_DIR_NAME


def check_art(name):
    """检查卡面插画字段，返回错误提示（不填也算正常）。"""
    text = str(name or "").strip().replace("\\", "/")
    if not text:
        return ""                                   # 不设插画是正常情况
    prefix = f"{ART_DIR_NAME}/"
    if not text.startswith(prefix):
        return f"卡面插画要写成 {prefix}<文件名>"
    filename = text[len(prefix):]
    if filename != Path(filename).name or ".." in filename:
        return "卡面插画只能用文件名，不能带路径"
    if Path(filename).suffix.lower() not in ART_EXTENSIONS:
        return f"卡面插画只能是 {'/'.join(ART_EXTENSIONS)} 这几种格式"
    return ""


def find_card_art(art_name, directory=None):
    """按记录里的相对路径找到插画文件（绝对路径）。没设过或文件不在就返回 None。"""
    text = str(art_name or "").strip()
    if not text or check_art(text):
        return None
    path = cards_folder(directory) / text
    return path if path.is_file() else None


def is_image_file(path):
    """看文件头判断是不是真图片（后缀不作数）。"""
    head = Path(path).read_bytes()[:12]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if head.startswith(b"\xff\xd8\xff"):                    # jpg / jpeg
        return True
    if head.startswith((b"GIF87a", b"GIF89a")):
        return True
    if head.startswith(b"BM"):                              # bmp
        return True
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"    # webp


def save_card_art(source, card_id, directory=None):
    """把选的图复制进 art/ 目录，返回记录里要写的相对路径。"""
    source = Path(source)
    suffix = source.suffix.lower()
    if suffix not in ART_EXTENSIONS:
        raise ValueError(f"卡面插画只能是 {'/'.join(ART_EXTENSIONS)} 这几种格式，现在选的是 {suffix or '没有后缀'}")
    if not source.is_file():
        raise ValueError(f"找不到这张图：{source}")
    if not is_image_file(source):
        raise ValueError(f"「{source.name}」不是图片文件（只看后缀是不够的）")
    size = source.stat().st_size
    if size > MAX_ART_BYTES:
        raise ValueError(f"卡面插画最大 {MAX_ART_BYTES // 1024 // 1024} MB，这张有 {size / 1024 / 1024:.1f} MB")
    folder = art_folder(directory)
    folder.mkdir(parents=True, exist_ok=True)
    remove_card_art(card_id, directory)             # 换图时先删掉旧后缀的那张，别留垃圾
    target = folder / f"{card_id}{suffix}"
    shutil.copyfile(source, target)
    return f"{ART_DIR_NAME}/{target.name}"


def remove_card_art(card_id, directory=None):
    """删掉这张牌已有的卡面插画（换图、清空、删卡时用）。返回删了几个文件。"""
    folder = art_folder(directory)
    if not folder.is_dir():
        return 0
    removed = 0
    for path in folder.glob(f"{card_id}.*"):
        path.unlink()
        removed += 1
    return removed


# ===== 二、输入检查 =====
def check_text(value, name, max_length):
    """检查一段文字。返回错误提示，没问题就返回空字符串。"""
    text = str(value or "").strip()
    if not text:
        return f"{name}不能为空"
    if len(text) > max_length:
        return f"{name}最多 {max_length} 个字，现在是 {len(text)} 个"
    return ""


def check_number(value, name, low, high):
    """检查整数，返回 (数字, 提示)；输入框里拿到的都是字符串。"""
    if value is None or str(value).strip() == "":
        return None, f"{name}不能为空"
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None, f"{name}要填整数，不能填「{value}」"
    if not low <= number <= high:
        return None, f"{name}要在 {low} 到 {high} 之间，现在是 {number}"
    return number, ""


def check_effects(raw_effects, card_type="attack"):
    """检查效果列表，返回 (效果, 错误字典)；数值范围按类型查表。"""
    errors = {}
    effects = []
    if not raw_effects:
        return [], {"effects": "至少要有一条效果"}
    if len(raw_effects) > MAX_EFFECTS:
        return [], {"effects": f"最多只能有 {MAX_EFFECTS} 条效果"}

    is_material = card_type == "material"
    table = MATERIAL_EFFECTS if is_material else EFFECTS
    labels = MATERIAL_EFFECT_LABELS if is_material else EFFECT_LABELS
    limits = MATERIAL_VALUE_LIMITS if is_material else VALUE_LIMITS

    for position, raw in enumerate(raw_effects):
        operation = raw.get("op")
        if operation not in table:
            errors[f"effect_{position}"] = "不认识这种效果"
            continue

        hits = 1
        # 按英文键判断，中文名只用来拼错误提示
        if operation in DAMAGE_EFFECTS:
            hits, problem = check_number(raw.get("hits", 1), "段数", MIN_HITS, MAX_HITS)
            if problem:
                errors[f"effect_{position}"] = problem
                continue

        low, high = limits[operation]
        if low == high == 0:  # 不需要数值的效果（生成素材、承载牌可保留）
            value = 0
        else:
            value, problem = check_number(
                raw.get("value"), f"{labels[operation]}的数值", low, high)
            if problem:
                errors[f"effect_{position}"] = problem
                continue

        effects.append({"op": operation, "value": value, "hits": hits})

    # 同一效果同一个数值填两遍，基本是手滑
    seen = set()
    for position, effect in enumerate(effects):
        key = (effect["op"], effect["value"])
        if key in seen:
            errors[f"effect_{position}"] = "这条效果和上一条重复了"
        seen.add(key)

    if errors:
        return [], errors
    return effects, {}


def check_keywords(keywords):
    """检查关键字。返回错误提示，没问题就返回空字符串。"""
    for keyword in keywords:
        if keyword not in KEYWORDS:
            return "关键字只支持「消耗」和「保留」"
    return ""


def describe_effects(effects, card_type="attack"):
    """把效果写成卡面文字，例如「造成12点伤害。获得5点格挡。」"""
    texts = {}
    texts.update(EFFECT_TEXTS)
    texts.update(MATERIAL_EFFECT_TEXTS)
    pieces = []
    for effect in effects:
        text = texts[effect["op"]].format(value=effect["value"])
        if effect["hits"] > 1:  # 多段攻击要标出来，不然看不出和单段的区别
            text = text.replace("。", f"（{effect['hits']}段）。")
        pieces.append(text)
    return "".join(pieces)


# ===== 三、表单 -> 卡牌记录 =====
def make_card_record(title, cost, card_type, target, rarity, keywords, effects, text="", art=""):
    """表单 -> 卡牌记录。有问题就返回 (None, 错误字典)，界面按字段名显示提示。"""
    errors = {}
    is_material = card_type == "material"

    problem = check_text(title, "卡牌名称", MAX_NAME_LENGTH)
    if problem:
        errors["title"] = problem

    if card_type not in CARD_TYPES:
        errors["card_type"] = "类型不认识，请用下拉框选"

    if is_material:
        cost, target, keywords = 0, "self", []
        if rarity not in MATERIAL_CATEGORIES:
            errors["rarity"] = "素材类别要选 一次性 / 普通 / 永久 / 诅咒"
    else:
        cost, problem = check_number(cost, "费用", MIN_COST, MAX_COST)
        if problem:
            errors["cost"] = problem
        if target not in TARGETS:
            errors["target"] = "目标不认识，请用下拉框选"
        if rarity not in RARITIES:
            errors["rarity"] = "稀有度不认识，请用下拉框选"
        problem = check_keywords(keywords)
        if problem:
            errors["keywords"] = problem

    effects, effect_errors = check_effects(effects, card_type)
    errors.update(effect_errors)

    art = str(art or "").strip().replace("\\", "/")
    problem = check_art(art)
    if problem:
        errors["art"] = problem

    custom_text = str(text or "").strip()
    if len(custom_text) > MAX_DESCRIPTION_LENGTH:
        errors["text"] = f"卡面描述最多 {MAX_DESCRIPTION_LENGTH} 个字"

    if errors:
        return None, errors

    text = custom_text or describe_effects(effects, card_type)
    # 关键字也写进卡面文字，描述里已经有就不重复
    for keyword in keywords:
        name = KEYWORDS[keyword]
        if name in text:
            continue
        text = f"{text.rstrip('。')}。{name}。" if text else f"{name}。"

    return {
        "schema_version": SCHEMA_VERSION,
        "card_id": make_card_id(title),
        "title": str(title).strip(),
        "cost": cost,
        "card_type": card_type,
        "rarity": rarity,
        "target": target,
        "keywords": list(keywords),
        "text": text,
        "effects": effects,
        "art": art,
    }, {}


def make_card_id(title):
    """用标题生成编号（同时也是文件名）；中文名就用时间戳。"""
    letters = []
    for char in str(title).strip().lower():
        if char.isascii() and char.isalnum():
            letters.append(char)
        elif char.isspace():
            letters.append("_")
    name = "".join(letters).strip("_")
    if name:
        return name[:32]
    return "user_" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:28]


def card_id_of(record):
    """已经存过的牌用记录里的编号；还没存过的现算一个。"""
    return record.get("card_id") or make_card_id(record["title"])


# ===== 四、存成 JSON / 读回来 =====
def save_card(record, directory=None, overwrite=False, art_source=None):
    """保存一张卡牌，同名不覆盖（自动加 -2 后缀）。

    art_source 是新挑的插画原图，会被复制进 art/ 并把 art 字段改成新文件名。
    撞名时编号会变，所以保存完要用 saved_card_id(path) 取真正的编号。
    """
    folder = cards_folder(directory)
    folder.mkdir(parents=True, exist_ok=True)

    record = dict(record)
    record["card_id"] = card_id_of(record)
    path = folder / f"{record['card_id']}.json"

    if path.exists() and not overwrite:
        for suffix in range(2, 100):
            candidate = f"{record['card_id']}-{suffix}"[:32]
            if not (folder / f"{candidate}.json").exists():
                record["card_id"] = candidate
                path = folder / f"{candidate}.json"
                break
        else:
            raise FileExistsError("同名卡牌太多了，换个名字吧")

    if art_source:
        record["art"] = save_card_art(art_source, record["card_id"], directory)

    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def saved_card_id(path):
    """一张已保存卡牌的真正编号：文件名就是编号（撞名时已经带上 -2 后缀）。"""
    return Path(path).stem


def read_card(path):
    """读一个卡牌文件，并用跟表单一样的规则再检查一遍。"""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if "title" not in data or "effects" not in data:
        raise ValueError(f"{path.name} 里没有 title 或 effects")
    data["card_id"] = str(data.get("card_id") or make_card_id(data["title"]))

    _record, errors = make_card_record(
        title=data.get("title", ""),
        cost=data.get("cost", 0),
        card_type=data.get("card_type", ""),
        target=data.get("target", ""),
        rarity=data.get("rarity", ""),
        keywords=data.get("keywords") or [],
        effects=data.get("effects") or [],
        art=data.get("art", ""),
    )
    if errors:
        detail = "；".join(f"{key}: {tip}" for key, tip in errors.items())
        raise ValueError(f"{path.name} 字段不合法（{detail}）")
    return data


def load_cards(directory=None):
    """读出目录里所有能读的卡牌。

    坏文件包一层 try：报出文件名就跳过，不让整局游戏起不来。
    返回 (卡牌记录列表, 错误提示列表)。
    """
    folder = cards_folder(directory)
    cards, errors = [], []
    if not folder.exists():
        return cards, errors
    for path in sorted(folder.glob("*.json")):
        if path.name == DECK_FILE_NAME:
            continue  # 老版本的牌组清单不是卡牌
        try:
            cards.append(read_card(path))
        except Exception as error:
            errors.append(f"{path.name}：{error}")
    return cards, errors


# ===== 四之二、卡组：一个 JSON 一副牌，选中的就是实战用的 =====
def decks_folder(directory=None):
    """卡组目录：传了就用传进来的，没传就用默认的 user_decks/。"""
    return Path(directory) if directory else DECKS_DIR


def make_deck_id(name):
    """卡组编号（也是文件名）：用时间戳，保证不重名，下拉框里按创建顺序排。

    玩家看到的是卡组名字，编号只用来落文件，所以不做"按名字生成"那一套。
    """
    return "deck_" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:22]


def new_deck(name="我的卡组"):
    """新建一个卡组：底子是 4 张打击 + 4 张防御。"""
    deck_name = str(name or "").strip() or "我的卡组"
    return {"deck_id": make_deck_id(deck_name), "name": deck_name, "cards": dict(BASE_DECK_CARDS)}


def sample_deck():
    """内置示例卡组（只读）：就是战斗端原本默认跑的那副。

    放在列表最前面，玩家想先打一局、或者想照着配一套时有个参照。
    """
    from .content.character import sample_deck_cards

    return {"deck_id": SAMPLE_DECK_ID, "name": SAMPLE_DECK_NAME,
            "cards": sample_deck_cards(), "builtin": True}


def read_deck(path):
    """读一个卡组文件，顺手检查格式。格式不对就抛错，让上层跳过它。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cards"), dict):
        raise ValueError("卡组文件里要有 cards（编号 -> 份数）")
    cards = {}
    for card_id, copies in data["cards"].items():
        try:
            count = int(copies)
        except (TypeError, ValueError):
            continue
        if count > 0:
            cards[str(card_id)] = min(count, MAX_DECK_COPIES)
    return {
        "deck_id": str(data.get("deck_id") or make_deck_id(data.get("name", "卡组"))),
        "name": str(data.get("name") or "未命名卡组"),
        "cards": cards,
    }


def load_decks(directory=None):
    """读出目录里所有能读的卡组。坏文件跳过并报原因，返回 (卡组列表, 错误列表)。"""
    folder = decks_folder(directory)
    decks, errors = [], []
    if not folder.exists():
        return decks, errors
    for path in sorted(folder.glob("*.json")):
        if path.name == SELECTED_DECK_FILE:
            continue  # 这是"当前选中哪个卡组"的指针，不是卡组
        try:
            decks.append(read_deck(path))
        except Exception as error:
            errors.append(f"{path.name}：{error}")
    return decks, errors


def save_deck(deck, directory=None):
    """把一个卡组写回 user_decks/<编号>.json。"""
    folder = decks_folder(directory)
    folder.mkdir(parents=True, exist_ok=True)
    deck = dict(deck)
    deck["deck_id"] = deck.get("deck_id") or make_deck_id(deck.get("name", "卡组"))
    path = folder / f"{deck['deck_id']}.json"
    path.write_text(json.dumps(deck, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def delete_deck(deck_id, directory=None):
    """删掉一个卡组。内置示例卡组删不了。"""
    if deck_id == SAMPLE_DECK_ID:
        return False
    path = decks_folder(directory) / f"{deck_id}.json"
    if not path.exists():
        return False
    path.unlink()
    if selected_deck_id(directory) == deck_id:
        set_selected_deck(directory, SAMPLE_DECK_ID)
    return True


def all_decks(directory=None):
    """界面下拉框用的清单：示例卡组排在最前面，后面是玩家自己存的。"""
    decks, _errors = load_decks(directory)
    return [sample_deck()] + decks


def find_deck(decks, key):
    """按编号或名字找一个卡组；找不到返回 None。"""
    text = str(key or "").strip()
    for deck in decks:
        if text in (deck["deck_id"], deck["name"]):
            return deck
    return None


def selected_deck_id(directory=None):
    """当前选中的卡组编号（没选过就是示例卡组）。"""
    path = decks_folder(directory) / SELECTED_DECK_FILE
    if not path.exists():
        return SAMPLE_DECK_ID
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return SAMPLE_DECK_ID
    return str(data.get("deck_id") or SAMPLE_DECK_ID)


def set_selected_deck(directory=None, deck_id=SAMPLE_DECK_ID):
    """记下"对局用哪副牌组"。创作端选了哪副，战斗端就跟着用哪副。"""
    folder = decks_folder(directory)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / SELECTED_DECK_FILE
    path.write_text(json.dumps({"deck_id": str(deck_id)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(deck_id)


def add_card_to_deck(deck, card_id, copies=CARDS_PER_TEST_DECK):
    """往卡组里加牌（同编号直接改份数）。返回加完之后的份数。"""
    count = max(1, min(int(copies), MAX_DECK_COPIES))
    deck.setdefault("cards", {})[str(card_id)] = count
    return count


def remove_card_from_deck(deck, card_id):
    """把一张牌从卡组里移出。移掉了返回 True。"""
    return deck.setdefault("cards", {}).pop(str(card_id), None) is not None


def remove_card_from_all_decks(card_id, directory=None):
    """删掉一张自制卡时，顺手把它从所有自制卡组里拿掉，免得卡组里留个死编号。"""
    changed = 0
    decks, _errors = load_decks(directory)
    for deck in decks:
        if remove_card_from_deck(deck, card_id):
            save_deck(deck, directory)
            changed += 1
    return changed


def deck_size(deck):
    """卡组一共几张牌。"""
    return sum(int(copies) for copies in deck.get("cards", {}).values())


def describe_deck(deck, titles=None):
    """把卡组写成一行字，给界面显示用。titles 是 {编号: 名字}，可以只传自己知道的。"""
    cards = deck.get("cards", {})
    if not cards:
        return "（这个卡组是空的，对局里会退回角色的起始牌组）"
    titles = titles or {}
    parts = [f"{titles.get(card_id, card_id)}×{copies}" for card_id, copies in cards.items()]
    return f"{deck.get('name', '卡组')}（{deck_size(deck)} 张）：" + "、".join(parts)


def spec_table(cards_dir=None):
    """编号 -> CardSpec：角色起始牌 + 40 张奖励牌 + 自制卡。

    卡组里存的是编号，真正开打时要靠这张表把编号换成引擎认识的卡牌。
    """
    from .content.character import build_character
    from .content.soyoi_cards import PLAYABLE_REWARD_CARDS

    table = {spec.card_id: spec for spec in build_character().starting_deck}
    table.update({spec.card_id: spec for spec in PLAYABLE_REWARD_CARDS})
    records, _errors = load_cards(cards_dir)
    table.update({spec.card_id: spec for spec in (make_card_spec(record) for record in records)})
    return table


def deck_specs(deck, cards_dir=None):
    """把一个卡组展开成引擎能用的 CardSpec 列表。

    找不到的编号（比如卡牌文件被删了）记进 missing，由界面提示玩家。
    份数在 read_deck() / add_card_to_deck() 那两关已经保证是 ≥1 的整数，这里直接照用。
    """
    table = spec_table(cards_dir)
    specs, missing = [], []
    for card_id, copies in deck.get("cards", {}).items():
        spec = table.get(str(card_id))
        if spec is None:
            missing.append(str(card_id))
            continue
        specs.extend([spec] * int(copies))
    return specs, missing


def resolve_deck(cards_dir=None, decks_dir=None, deck_id=None):
    """决定这一局用哪副卡组：指定编号 > 创作端选中的 > 示例卡组；找不到就退回。"""
    notes = []
    migrate_old_test_deck(cards_dir, decks_dir)
    decks = all_decks(decks_dir)
    deck = find_deck(decks, deck_id) if deck_id else None
    if deck_id and deck is None:
        notes.append(f"没有卡组「{deck_id}」，改用选中的那副")
    if deck is None:
        deck = find_deck(decks, selected_deck_id(decks_dir)) or sample_deck()
    return deck, notes


def migrate_old_test_deck(cards_dir=None, decks_dir=None):
    """把老版本的 user_cards/test_deck.json 升级成一个卡组（只做一次）。

    老版本只有"一份测试牌组"，现在改成可以建多个卡组了；
    玩家之前的配置不能丢，所以第一次加载时自动搬过来，编号叫"我的卡组"。
    """
    folder = decks_folder(decks_dir)
    if folder.exists() and [p for p in folder.glob("*.json") if p.name != SELECTED_DECK_FILE]:
        return None                                   # 已经有卡组了，不用搬
    old_path = cards_folder(cards_dir) / DECK_FILE_NAME
    if not old_path.exists():
        return None
    try:
        old = json.loads(old_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(old, dict) or not old:
        return None
    deck = new_deck("我的卡组")
    for card_id, copies in old.items():
        add_card_to_deck(deck, card_id, copies)
    save_deck(deck, decks_dir)
    set_selected_deck(decks_dir, deck["deck_id"])
    old_path.rename(old_path.with_suffix(".json.migrated"))   # 搬完就改名，不再重复搬
    return deck["deck_id"]


# ===== 五、把卡牌接进战斗框架 =====
def make_card_spec(record):
    """卡牌记录 -> 战斗框架认识的 CardSpec（素材牌 -> MaterialCardSpec）。

    这一步之后，自制卡和系统卡就没有区别了：都用同一套结算规则。
    """
    if record.get("card_type") == "material":
        return make_material_spec(record)

    text = record.get("text") or describe_effects(record["effects"])
    # 关键字要跟着进对局：消耗进消耗堆，保留留到回合结束
    keywords = [CARD_KEYWORDS[key] for key in record.get("keywords", []) if key in CARD_KEYWORDS]
    spec = CardSpec(
        card_id=card_id_of(record),
        title=record["title"],
        base_cost=int(record["cost"]),
        upgraded_cost=int(record["cost"]),
        card_type=CARD_TYPES[record["card_type"]],
        rarity=RARITIES[record["rarity"]],
        target=TARGETS[record["target"]],
        base_text=text,
        upgraded_text=text,
        base_keywords=list(keywords),
        upgraded_keywords=list(keywords),
        art=str(record.get("art", "") or ""),
    )
    for effect in record["effects"]:
        spec.base_effects.append(
            RewardEffectSpec(EFFECTS[effect["op"]], amount=effect["value"], hits=effect["hits"])
        )
    spec.upgraded_effects = list(spec.base_effects)
    return spec


def make_material_spec(record):
    """素材牌记录 -> MaterialCardSpec。

    素材牌不能打出（UNPLAYABLE），回合结束也不会掉（RETAIN）：它是装备，
    等着玩家点它、再点一张手牌，装到那张牌身上。

    类别决定素材会不会被用掉：**一次性素材结算完就从槽位消失**（类别是 one_shot 的
    那三种都带"消耗"标记），普通 / 永久 / 诅咒素材一直留着。
    """
    consumed_after_use = record["rarity"] == "one_shot"
    effects = []
    for effect in record["effects"]:
        key = effect["op"]
        effects.append(MaterialEffectSpec(
            operation=MATERIAL_EFFECTS[key],
            amount=effect["value"],
            hits=effect["hits"],
            timing=MATERIAL_EFFECT_TIMINGS.get(key, MaterialEffectTiming.AFTER_CARRIER_PLAYED),
            target=MATERIAL_EFFECT_TARGETS[key],
            consumes_component=consumed_after_use,
        ))
    text = record.get("text") or describe_effects(record["effects"], "material")
    return MaterialCardSpec(
        card_id=card_id_of(record),
        title=record["title"],
        base_text=text,
        upgraded_text=text,
        material_category=MATERIAL_CATEGORIES[record["rarity"]],
        material_effects=effects,
        art=str(record.get("art", "") or ""),
    )


def build_player(deck_specs, name="所依", max_hp=72):
    """按牌组创建玩家。每张牌都单独造实例，避免同名牌互相影响。"""
    return Player(name=name, max_hp=max_hp, deck=[spec.create() for spec in deck_specs])


def load_enemy_scripts(directories=None) -> list[str]:
    """加载敌人脚本（游戏脚本）。

    - 不传参数：只加载仓库自带的示例脚本（`content/enemy_scripts/`）；
    - 传目录列表：在自带脚本之外再加载这些目录。

    返回出错提示（脚本写错不会让游戏起不来，只会在这里告诉你原因）。
    """
    from .content.enemy_scripts import load_default_scripts, load_script_list

    if directories:
        report = load_script_list(list(directories))
    else:
        report = load_default_scripts()
    return report.errors


def build_combat(cards_dir=None, decks_dir=None, deck_id=None, seed=2026,
                 enemy="random", scripts_dir=None):
    """组一场对战，可以直接 start_combat()。

    **用哪副牌组由卡组决定**：不指定 deck_id 就用创作端选中的那副，
    一副都没有时用内置的示例卡组。卡组里找不到的牌会被跳过（界面会提示）。
    `enemy` 决定打谁：填敌人编号（jaw_worm / cultist / looter / sentry /
    scrap_colossus）、中文名、脚本里定义的敌人，或者 "random" 随机抽一只普通怪。
    `scripts_dir` 可以再加载额外的敌人脚本目录。
    """
    from .content.enemies import make_enemy_by_name

    load_enemy_scripts([scripts_dir] if scripts_dir else None)

    character = build_character()
    deck, _notes = resolve_deck(cards_dir, decks_dir, deck_id)
    specs, _missing = deck_specs(deck, cards_dir)
    if not specs:
        # 卡组是空的：退回角色起始牌组，别让对局开不起来
        specs = list(character.starting_deck)

    player = build_player(specs, name=character.name, max_hp=character.starting_hp)
    player.piles.rng.seed(seed)

    combat = CombatState(
        player=player,
        enemies=[make_enemy_by_name(enemy)],
        rng=random.Random(seed),
    )
    setup_soyoi_combat(combat)
    return combat


# ===== 六、命令行入口 =====
def list_cards(directory=None, decks_directory=None):
    """列出卡牌目录里的卡牌和卡组，返回 0 表示全部正常。"""
    records, errors = load_cards(directory)
    print(f"卡牌目录：{cards_folder(directory)}")
    if not records:
        print("（还没有保存任何卡牌）")
    for record in records:
        print(f"- {record['title']}　{record['cost']} 费　{record['text']}")
    decks, deck_errors = load_decks(decks_directory)
    selected = selected_deck_id(decks_directory)
    print(f"卡组目录：{decks_folder(decks_directory)}")
    for deck in all_decks(decks_directory):
        mark = "→" if deck["deck_id"] == selected else "　"
        row = "、".join(f"{card_id}×{copies}" for card_id, copies in deck["cards"].items()) or "空"
        print(f"{mark} {deck['name']}（{deck_size(deck)} 张）：{row}")
    for error in errors + deck_errors:
        print(f"[跳过] {error}")
    return 1 if errors or deck_errors else 0


def create_sample(directory=None, decks_directory=None):
    """生成一张示例卡「重击」，并加进当前卡组，用来快速试一下整条链路。"""
    record, errors = make_card_record(
        title="重击", cost=2, card_type="attack", target="enemy", rarity="common",
        keywords=[], effects=[{"op": "damage", "value": 12, "hits": 1}],
    )
    if record is None:
        print(f"示例卡都存不下来：{errors}")
        return 1
    path = save_card(record, directory)
    deck, _notes = resolve_deck(directory, decks_directory)
    if deck.get("builtin"):
        deck = new_deck("我的卡组")          # 示例卡组只读，要改就自动另存一份
    add_card_to_deck(deck, saved_card_id(path), CARDS_PER_TEST_DECK)
    save_deck(deck, decks_directory)
    set_selected_deck(decks_directory, deck["deck_id"])
    print(f"已生成：{path}")
    print(f"卡面：〔{record['cost']} 费〕{record['title']} — {record['text']}")
    print(f"已加入卡组「{deck['name']}」（{deck_size(deck)} 张），对局就用这一副")
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK，打印中文会乱码
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="卡牌数据处理（命令行方式）")
    parser.add_argument("--dir", type=Path, default=None, help="卡牌目录，默认 user_cards/")
    parser.add_argument("--decks-dir", type=Path, default=None, help="卡组目录，默认 user_decks/")
    parser.add_argument("--list", action="store_true", help="列出已经保存的卡牌和卡组")
    parser.add_argument("--demo", action="store_true", help="生成一张示例卡后退出")
    args = parser.parse_args(argv)

    if args.list:
        return list_cards(args.dir, args.decks_dir)
    if args.demo:
        return create_sample(args.dir, args.decks_dir)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
