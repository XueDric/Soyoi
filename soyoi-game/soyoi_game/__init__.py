"""酱油部 类杀戮尖塔 游戏框架。

本包是把《杀戮尖塔2》"所依/酱油部"人物 mod 的"素材加工"机制
移植到 Python 的游戏引擎框架。

设计原则（见 README.md）：
- 逻辑与显示分离：core/soyoi/content 是纯逻辑，不依赖 pygame。
- 数据驱动：卡牌、素材、敌人、角色都用数据描述，用一个解释器去读。
- 契约先行：teammate 移植 C# 卡牌时，只需实现约定的接口/子类。
- 可测试：核心是纯逻辑，可以写无 UI 的断言测试。
"""

from .core.combat import CombatState
from .core.cards import PileType, Card

__all__ = ["CombatState", "PileType", "Card"]

__version__ = "0.1.0"
