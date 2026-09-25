# Bug 清单

> 下面记录开发中实际遇到，或在测试中提前拦住的问题。每条都写了现象，原因，修法和对应测试。

---

## 一，总表

| # | Bug | 症状 | 根本原因 | 修法 | 对应测试 |
| --- | --- | --- | --- | --- | --- |
| 1 | 字段名不一致 | 卡牌保存成功，界面显示“已保存”，对局里毫无效果 | 拼牌组时读 `spec.cost`，真实字段是 `base_cost`；动态类型不报错 | 统一由 `CardSpec` 承接；端到端测试断言实际伤害 | `test_user_card_actually_plays_in_combat` |
| 2 | 输入没有校验范围 | 费用填“两点”，伤害填 99999 也能存进 JSON | 信任了输入控件的类型，而 Tkinter 输入框本质是字符串 | 枚举白名单 + 范围校验，一次性返回“字段 → 提示” | `test_cost_must_be_integer` 等 6 项 |
| 3 | 一个坏 JSON 拖垮整局 | 手改文件写错逗号，对战程序启动即抛异常 | 加载时没有隔离单个文件的错误 | `load_cards()` 逐个 try/except，坏卡跳过并汇总提示 | `test_load_cards_skips_broken_file_and_reports` |
| 4 | 复制了不存在的属性 | `spec.cost` / `spec.text` 触发 `AttributeError` 崩溃 | 与 ▼1 同源：对数据对象的字段约定不统一 | 以 `base_cost` / `base_text` 为准，并用测试锁住约定 | `test_record_maps_to_core_card_spec` |
| 5 | 同名卡互相覆盖 | 连造两张“重击”，第一张被悄悄覆盖 | 覆盖策略绑定在文件名上，而不是用户意图上 | 默认不覆盖，同名加 `-2`；只有“载入老卡未改名”才覆盖 | `test_reloading_and_resaving_same_title_overwrites` |

### 二，卡组和素材功能增加后补修的 4 条

> 这四条是在增加卡组和素材类别后，运行 `python scripts/audit_replication.py` 检查创作端到战斗端的数据流时发现的。它们大多不会让程序崩溃，但会让结果算错。

| # | Bug | 症状 | 根本原因 | 修法 | 对应测试 |
| --- | --- | --- | --- | --- | --- |
| 6 | 关键字只写在卡面上 | 勾了“消耗”，卡面写着“消耗”，打出后却照常进弃牌堆 | `make_card_spec()` 忘了把 `keywords` 转成 `CardKeyword` 填进 `CardSpec` | 加 `CARD_KEYWORDS` 表，构造 `CardSpec` 时填 `base_keywords` | `test_exhaust_card_goes_to_the_exhaust_pile`,`test_retain_card_stays_in_hand_at_turn_end` |
| 7 | “一次性”素材用不掉 | 选了类别“一次性”，素材却永远留在槽里，每次打出都再结算一遍 | 类别只当成标签存了，没有翻译成 `consumes_component` | 一次性 → `consumes_component=True`(与参考数据的 17 种素材一致) | `test_one_shot_material_is_used_up_but_normal_material_is_not` |
| 8 | 编号撞车 → 加错牌 | “重击A”和“猛击A”的编号都算成 `a`，第二张存成 `a-2`，卡组里加的却还是 `a`：打出“猛击A”变成“重击A”的效果 | `save_card()` 撞名时改的是内部副本的编号，调用方仍拿旧的 `record["card_id"]` | 新增 `saved_card_id(path)`，保存后一律用它(文件名就是编号) | `test_saving_a_card_whose_id_clashes_adds_the_right_one_to_the_deck` |
| 9 | 演示默认路径被卡组带偏 | `--no-user-cards` 只不读自制卡，牌组照样用创作端选中的那副，本地卡组一改演示效果就变 | 卡组功能是后加的，没回到“关掉玩家数据”的原意 | `use_user_cards=False` 且没指定 `--deck` 时直接用角色起始牌组 | `test_no_user_cards_falls_back_to_the_character_starting_deck` |

## 三，修复时留下的约定

1. **先检查模块交接处。**
   这次的问题大多出现在表单，JSON,CardSpec 和战斗对象之间的转换。
2. **要特别防止静默算错。**
   ▼1 和 ▼4 是同一类问题的两种表现：一个不报错，只是没效果，一个直接崩。
   不报错的那个花了我们更多时间。
3. **校验放在入口，并在读档时再做一次。**
   界面做一次为了体验(提示落在出错那一行)，读取 JSON 时再做一次为了安全(手改的越界值进不来)。
4. **每个修复都留一条回归测试。**
   测试直接复现原来的现象，之后改代码时可以及时发现回归。

---

## 四，怎么用这份清单

- 第一部分是早期遇到或提前拦住的 5 条；第二部分是增加卡组和素材类别后补修的 4 条。
- 想验证某条 bug 的修法，可以直接跑对应测试，例如：

```powershell
python -m unittest tests.test_data -v                  # 创作端校验 / JSON / 卡组
python -m unittest tests.test_ui -v                    # 界面流程
python -m unittest discover -s tests                   # 全量 80 项
```

- 想亲手复现“输入不校验”的后果，可以手改 `user_cards/*.json` 里的 `value` 为 `99999`,
  再运行 `python main.py --list`，会看到这张卡被拒绝并给出原因。
