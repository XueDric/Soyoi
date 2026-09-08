# 两人协作方案

## 代码边界

| 负责人 | 目录 | 工作内容 |
| --- | --- | --- |
| 角色与规则 | `soyoi_game/content/`、`soyoi_game/soyoi/` | 卡牌、素材、角色数值与规则测试 |
| 界面与流程 | `soyoi_game/ui/`、`assets/` | pygame 界面、输入、动画与资源 |
| 双方共同 | `soyoi_game/core/`、`tests/` | 战斗接口、回归测试和最终验收 |

UI 层只把玩家输入转换为 `CombatState` 命令，不直接修改生命、格挡、能量或牌堆。
内容层不导入 pygame。需要修改共同文件时，先在群里说明文件名，避免同时编辑。

## Main 协作流程

项目按当前约定直接使用 `main`，不再建立功能分支。每次开始工作前执行：

```powershell
git switch main
git pull origin main
```

每次只完成一个小目标，测试通过后提交：

```powershell
python -m unittest discover -s tests -v
git add 修改过的文件
git commit -m "feat: 简短说明本次改动"
git pull --rebase origin main
git push origin main
```

如果 `git pull --rebase` 出现冲突，先停止推送，与修改同一文件的队友一起确认保留内容。
不要使用 `git push --force`，也不要上传 `__pycache__`、虚拟环境或临时截图。

## 当前对接状态

1. 战斗核心、四个牌堆、能量与敌人意图已接通。
2. 所依 5 类起始牌、40 张奖励牌和 6 种素材已可结算。
3. pygame 已支持点击出牌、目标选择、结束回合、胜负和重新开始。
4. 下一步优先完成战斗奖励选牌、三种普通敌人与一个 Boss。

## 提交门禁

- 全部自动测试通过。
- `python -m soyoi_game` 可以进入可视化战斗。
- 一张卡不能同时出现在两个牌堆。
- UI 不绕过 `CombatState` 直接修改战斗数据。
- 卡牌文字、费用和素材槽在 1280×720 下无重叠。
- 提交信息说明实际改动，不使用“update files”等模糊描述。
