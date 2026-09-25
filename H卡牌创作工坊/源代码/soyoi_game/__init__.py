"""游戏框架：卡牌、战斗流程与素材系统。"""

from pathlib import Path
import sys

from .core.combat import CombatState
from .core.cards import PileType, Card

__all__ = ["CombatState", "PileType", "Card", "app_root", "resource_root"]
__version__ = "0.1.0"


def app_root() -> Path:
    """程序根目录 —— 需要**写文件**的东西都放这儿（user_cards/、user_decks/）。"""
    if getattr(sys, "frozen", False):        # PyInstaller 打包后会设这个标记
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    """只读资源（assets/：背景图、卡面、立绘）的根目录。"""
    bundled = getattr(sys, "_MEIPASS", "")
    return Path(bundled) if bundled else app_root()
