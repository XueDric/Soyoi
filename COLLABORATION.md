# 两人协作方案

## 代码边界

队友负责 pygame 外壳：`main.py`、窗口循环、场景切换、鼠标事件、卡牌绘制和动画。

你负责角色内容：`characters/soyoi/`、卡牌数据、素材规则、角色数值和相关测试。

双方共同维护一个很小的战斗接口，不要同时修改彼此目录。推荐接口如下：

```python
class CombatAPI:
    def queue_effect(self, effect, source_card, target): ...
    def move_card(self, card, destination): ...
    def choose_from_hand(self, predicate): ...
    def choose_enemy(self): ...
```

pygame 层只负责把点击翻译成命令；角色模块只返回效果和状态变化，不直接绘图。

## Git 分支

- `main`：始终保持能启动、能测试。
- `feature/pygame-shell`：队友开发窗口和战斗界面。
- `feature/soyoi-character`：你开发所依角色。
- 每次提交只完成一个小目标，例如“显示手牌”或“实现素材附着”。
- 每天至少合并一次，先运行测试，再由另一人试玩一回合。

## 对接顺序

1. 队友先能在窗口中显示一张 `CardDefinition`。
2. 接入打击、防御，跑通能量与弃牌。
3. 接入 `attach_material()`，确认素材不计作正常出牌。
4. 接入 `resolve_materials()`，让拼豆色包追加两段伤害。
5. 接入赶制、细修和活动证。
6. 核心稳定后，再从 80 张奖励牌目录中一次挑 3 至 5 张实现。

## 合并门禁

- `python -m unittest discover -s tests -v` 全部通过。
- 一张卡不能同时处于两个牌堆。
- UI 不直接修改生命、格挡、能量或牌堆列表。
- 角色模块不导入 pygame。
- 标记 `requires_custom_logic=True` 的卡不能直接加入奖励池。

