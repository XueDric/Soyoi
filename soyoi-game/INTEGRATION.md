# 整合说明（Integration Notes）

> 本文档记录把队友「所依」人物移植代码整合进本项目的经过与现状，
> 供两人后续协作对齐。

> **项目主目录**：所有内容已归拢到本目录 `soyoi-game/`（本文件所在目录）。
> 这是一个自包含的游戏项目主目录——包含可运行代码、测试、参考目录、
> 规划文档，以及完整 git 历史（外层 `小学期游戏` 仅作为包裹这个主目录的壳）。
> 进入本目录后即可运行 `python -m soyoi_game`。

---

## 1. 整合结果

项目主目录现已成为**唯一正式运行入口**，采用队友分支 `feature/playable-40-card-core`
的完整实现作为权威基线。原独立版 `soyoi_game/`（仅引擎骨架，无内容卡牌）已被替换。

现状：在本目录内，`python -m soyoi_game` 即可运行文本战斗 demo，
`python -m unittest discover -s tests -v` 全部通过（共 12 项）。


---

## 2. 最终目录结构

```
项目根/
├── .gitignore                 # 忽略 __pycache__/pyc/venv 等
├── README.md                  # 项目说明（来自队友仓库）
├── COLLABORATION.md           # 两人协作方案与代码边界
├── INTEGRATION.md             # 本文档
├── pyproject.toml             # 项目元数据
├── soyoi_game/                # ★ 游戏引擎 + 内容（权威基线）
│   ├── __main__.py            # python -m soyoi_game 入口
│   ├── core/                  # 引擎核心（纯逻辑，无 UI）
│   │   ├── cards.py           # 卡牌数据类 + 枚举 + ATTACH_MATERIAL
│   │   ├── combat.py          # 战斗状态 + 回合循环
│   │   ├── powers.py          # 状态(Power) + 伤害/格挡计算
│   │   ├── pile.py            # 四堆牌
│   │   ├── player.py / enemy.py / creature.py
│   ├── combat/resolver.py     # 卡牌本体效果结算（含素材加工解析）
│   ├── soyoi/                 # 素材系统
│   │   ├── materials.py       # 素材枚举/Spec/Bundle/Loadout
│   │   ├── card.py            # MaterialCardBase + 承载判定
│   │   ├── material_runtime.py      # 素材盒 + 附着/合料
│   │   ├── material_effect_resolver.py  # 素材效果结算
│   │   ├── material_lifecycle.py    # 生命周期/成长计数
│   │   └── materials_render.py      # 素材渲染
│   ├── content/               # 内容层（数据驱动）
│   │   ├── character.py       # 「所依」角色 + 战斗接线
│   │   ├── soyoi_cards.py     # 40 张精简奖励牌
│   │   └── materials.py       # 6 种核心素材
│   └── ui/__main__.py         # 文本战斗 demo（可换 pygame）
├── soyoi_port/                # 原始移植参考目录（80 张牌 + 17 素材）
├── tests/                     # 12 个测试（角色/卡牌/素材/整合）
├── scripts/
│   ├── card_showcase.py       # 逐张结算 40 张牌并输出结果
│   └── smoke_test.py          # 精简冒烟测试
├── examples/integration_example.py
├── tools/extract_soyoi.py
└── SoyoiMod-Rebuild/          # 原 C# mod 源码（参考，不参与运行）
```

---

## 3. 关键接口变更（从旧引擎版 → 队友整合版）

队友在我搭的引擎基础上做了如下扩展，整合后这些是**权威 API**：

| 变更 | 说明 | 位置 |
| --- | --- | --- |
| `RewardEffectOperation.ATTACH_MATERIAL` | 新增「加工素材」操作 | `core/cards.py` |
| `RewardEffectSpec.material_id` | 效果可指定加工的素材 ID | `core/cards.py` |
| `CombatState.last_card_target` | 记录本次出牌目标，供素材效果继承 | `core/combat.py` |
| `MaterialCardBase.as_bundle()` | 素材卡转成 Bundle 的便捷方法 | `soyoi/card.py` |
| `ATTACH_MATERIAL` **已在 resolver 实现** | 打牌时生成/加工素材 | `combat/resolver.py` |
| 内容层 `content/materials.py` | 6 种核心素材工厂 | `content/materials.py` |
| 内容层 `content/soyoi_cards.py` | 40 张奖励牌 | `content/soyoi_cards.py` |
| 起始遗物自动加工 | 每回合给一张手牌加工素材 | `content/character.py` |

> ⚠️ 旧版接口 `content.character.make_perler_color_pack()` 已移除，
> 现应改用 `content.materials.make_perler_color_pack()`（或 `make_material(id)`）。

---

## 4. 两个人各自负责的目录（对齐 COLLABORATION.md）

| 成员 | 目录 | 职责 |
| --- | --- | --- |
| 你（角色/内容） | `soyoi_game/content/`、`soyoi_game/soyoi/`、`soyoi_port/` | 卡牌数据、素材规则、角色数值、测试 |
| 队友（UI/外壳） | `main.py`、`soyoi_game/ui/`（pygame 层待建） | 窗口循环、场景切换、鼠标事件、卡牌绘制 |

**边界**：UI 层只把点击翻译成命令，不直接改生命/格挡/能量/牌堆；
角色模块只返回效果与状态变化，不直接绘图、**不 import pygame**。

---

## 5. 验证方式

```powershell
# 跑全部测试（12 项）
python -m unittest discover -s tests -v

# 逐张结算 40 张奖励牌，输出战斗结果
python -m scripts.card_showcase

# 文本战斗 demo
python -m soyoi_game
```

---

## 6. 尚未完成 / 待办

- **UI（pygame）尚未接入**：文本界面只是占位，等待美术与 pygame 外壳。
- **敌人**：`core/enemy.py` 有意图系统，但课程 demo 只用了简单测试木桩。
- **奖励/商店/地图/营地**：当前仅单场战斗。
- **更多素材与遗物**：当前 6 种素材、1 个起始遗物；`soyoi_port/` 保留了
  17 种素材与 80 张牌的参考目录，可按需逐步接入。
