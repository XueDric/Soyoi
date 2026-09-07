# 所依（酱油部）Python 课程 Demo

把《杀戮尖塔2》人物 mod「所依/酱油部」的**素材加工机制**移植到 Python 的类杀戮尖塔游戏框架。

> 说明：这是适合软件工程课程作业的单场战斗 Demo。它保留「三槽素材加工、
> 承载牌触发素材、素材轮换、起始遗物自动加工」四个核心点，不追求完整复刻 MOD。

---

## 已接入的角色源码

- `soyoi_game/`：队友继续开发的战斗框架与界面。
- `soyoi_game/content/soyoi_cards.py`：实际使用的 40 张精简奖励牌（20 普通、15 罕见、5 稀有）。
- `soyoi_game/content/materials.py`：Demo 使用的 6 种核心素材。
- `soyoi_port/`：原始移植参考目录，仍保存 80 张奖励牌和 17 种素材，方便查阅 MOD 设定。
- `tests/`：角色数据、素材附着与两个模块一致性的基础测试。
- `examples/integration_example.py`：战斗框架接入角色内容包的最小示例。

运行测试：

```powershell
python -m unittest discover -s tests -v
```

40 张入池卡牌的基础版和升级版都已接入统一结算器，不再依赖“只有描述、没有逻辑”的占位行为。

查看每张牌在战斗框架中的实际结算结果：

```powershell
python -m scripts.card_showcase
```

---

## 1. 这个框架解决什么

你（搭框架）和队友（移植人物代码）的分工：

| 你负责 | 队友负责 |
| --- | --- |
| 战斗引擎（抽牌/出牌/能量/回合） | 维护 40 张精简奖励牌和数值 |
| 素材系统的**运行时**（素材盒、槽位、结算管线） | 移植 C# 素材（分类/效果/加工规则） |
| 状态（Power）计算、敌人意图 | 移植 C# 能力（Powers）与遗物 |
| 数据驱动的卡/素材/角色定义 | 把 C# 卡牌转成这份数据/接口格式 |

**关键点：mod 是"内容"，不是"引擎"。** 你搭的框架是引擎，队友移植的是内容。
框架不直接适配 mod 的运行（那需要原版游戏），所以框架**不依赖起 mod 就能独立跑**。

---

## 2. 目录结构

```
soyoi_game/
├── __main__.py          # 入口: python -m soyoi_game
├── core/                # 引擎核心 (纯逻辑，无 UI，不依赖 pygame)
│   ├── cards.py         # 卡牌数据类 + 枚举 (Card/Spec/效果)
│   ├── creature.py      # 生物抽象 (玩家/敌人共有 HP/格挡/状态)
│   ├── powers.py        # 状态(Power)系统 + 伤害/格挡计算
│   ├── pile.py          # 四堆牌 (抽/手/弃/消耗) + 洗回
│   ├── player.py        # 玩家
│   ├── enemy.py         # 敌人 + 意图
│   └── combat.py        # 战斗状态 + 回合循环 (协调者)
├── combat/
│   └── resolver.py      # 卡牌本体效果统一结算器
├── soyoi/               # ★ 素材系统 (mod 核心，队友重点看)
│   ├── materials.py     # 素材枚举 / Spec / Bundle / Loadout
│   ├── card.py          # MaterialCardBase + 承载判定 + get_loadout
│   ├── material_runtime.py     # 素材盒 + 附着/合料 API
│   ├── material_effect_resolver.py  # 素材效果结算器
│   ├── material_lifecycle.py    # 生命周期/回合计数/加工成长
│   └── materials_render.py      # 素材效果文本渲染
├── content/             # 内容层 (数据驱动: 角色/卡/素材/敌人)
│   └── character.py     # 「所依」角色定义 + 示例卡牌
└── ui/                  # 界面层 (当前是文本 demo，可换 pygame)
    └── __main__.py      # 文本战斗循环
```

---

## 3. 核心概念与对应关系（C# → Python）

| C# (mod) | Python (本框架) |
| --- | --- |
| `CardModel` | `core.cards.Card` |
| `MaterialCard` | `soyoi.card.MaterialCardBase` |
| `MaterialCategory` | `soyoi.materials.MaterialCategory` |
| `MaterialBundle` | `soyoi.materials.MaterialBundle` |
| `MaterialLoadout` (3槽) | `soyoi.materials.MaterialLoadout` |
| `MaterialEffectSpec` | `soyoi.materials.MaterialEffectSpec` |
| `MaterialEffectResolver` | `soyoi.material_effect_resolver.MaterialEffectResolver` |
| `MaterialBoxRuntime` | `soyoi.material_runtime` |
| `MaterialAttachmentRuntime` | `soyoi.material_runtime` (附着/合料API) |
| `MaterialTurnRuntime` 回合计数 | `soyoi.material_lifecycle` |
| `RedesignedCardRuntime` 加工成长 | `soyoi.material_lifecycle` |
| `CombatState` | `core.combat.CombatState` |
| `Player` | `core.player.Player` |

---

## 4. 队友移植卡牌的接口契约

### 4.1 简单卡牌（纯本体效果，数据驱动）

继承 `CardSpec`，声明基础/升级效果即可，无需写逻辑：

```python
STRIKE_SPEC = CardSpec(
    card_id="strike_soyoi", title="打击",
    base_cost=1, upgraded_cost=1,
    card_type=CardType.ATTACK, rarity=CardRarity.BASIC,
    target=TargetType.ANY_ENEMY,
    base_text="造成6点伤害。", upgraded_text="造成9点伤害。",
    base_effects=[RewardEffectSpec(RewardEffectOperation.DAMAGE, 6)],
    upgraded_effects=[RewardEffectSpec(RewardEffectOperation.DAMAGE, 9)],
)
```

支持的 `RewardEffectOperation`：伤害/格挡/抽牌/给能量/易伤/虚弱/力量/临时力量/活力/覆甲/荆棘/扣血/治疗/降敌人力量。见 `core/cards.py`。

### 4.2 素材卡

继承 `MaterialCardBase`，填 `material_category` 与 `material_effects`：

```python
def make_perler_color_pack() -> MaterialCardBase:
    return MaterialCardBase(
        card_id="perler_color_pack", title="拼豆色包",
        base_cost=0, upgraded_cost=0,
        card_type=CardType.SKILL, rarity=CardRarity.TOKEN,
        target=TargetType.SELF,
        base_text="普通素材：造成3点伤害。", upgraded_text="",
        base_keywords=[CardKeyword.RETAIN],
        material_category=MaterialCategory.NORMAL,
        material_effects=[MaterialEffectSpec(
            operation=MaterialEffectOperation.MATERIAL_DAMAGE,
            amount=3,
            timing=MaterialEffectTiming.AFTER_CARRIER_PLAYED,
            target=MaterialEffectTarget.INHERITED,
        )],
    )
```

支持的素材效果操作（`MaterialEffectOperation`）：素材伤害/易伤/虚弱/格挡/本回合降力量/覆甲/保留/降费/抽牌/弃牌堆置顶/给能量/返回手牌/加伤口/加费。
触发时机（`MaterialEffectTiming`）：常驻/承载牌打出后/跨回合保留后/下次打出后/本场首打。
目标（`MaterialEffectTarget`）：继承/玩家/承载牌。

### 4.3 素材加工牌

课程版把复杂的选牌窗口简化为 `ATTACH_MATERIAL`。指定素材编号时加工该素材，
不指定时从 6 种核心素材中随机选择：

```python
RewardEffectSpec(
    RewardEffectOperation.ATTACH_MATERIAL,
    material_id="perler_color_pack",
)
```

框架的 `MaterialEffectResolver` 会在承载牌打出后自动结算素材效果，复杂卡的"生成/加工/合料"可通过 `soyoi.material_runtime` 提供的 API 调用：
- `store(player, material)` — 生成素材到素材盒+手牌
- `attach_next_available(player, carrier, bundle)` — 加工到承载牌下一空槽
- `try_merge_from_box(player, left, right)` — 合料
- `positive_count(player)` / `get_materials(player)` — 查询素材盒

---

## 5. 运行

```powershell
# 用文本界面玩一场战斗
> python -m soyoi_game
```

或运行自动测试（会逐张结算 40 张牌的基础版和升级版）：

```powershell
> python -m unittest discover -s tests -v
```

---

## 6. 下一步（队友移植好第一版后要接的）

1. **卡牌平衡**：试玩 40 张精简牌，记录过强或过弱的数值，再小步调整。
2. **敌人**：把 C# 敌人转成 `Enemy` + `act_pattern` 意图序列。
3. **能力（Powers）**：C# 的 `*Power`（加班、夜间回流等）在 `core/powers.py` 里按需扩展，或钩到 `combat` 的事件钩子上（`on_player_turn_start` / `on_round_end` 等）。
4. **遗物扩展**：当前起始遗物已接入；如课程时间充足，再增加奖励遗物。
5. **UI**：现在文本界面只展示/出牌，换 pygame 时替换 `ui/`。
6. **地图/奖励/商店/营地**：当前框架只有单场战斗，这些在 `core` 之上再建一层。

---

## 7. 当前已知简化（在改为完整版之前）

- “选择素材/选择承载牌”被简化为自动选择，未制作复杂的弹窗与拖放操作。
- 原始 80 张奖励牌只作为参考数据，不进入课程 Demo 的奖励池。
- 素材效果的"每回合一次""本场一次"用简化计数器，待队友接入真实卡后完善。
- 无药水与额外奖励遗物（Powers 只实现课程版会用到的基础状态）。
- 无地图与奖励，仅单场战斗验证。
