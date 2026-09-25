# 敌人脚本目录

这里放的是**外置游戏脚本**：每写一个 `.txt`，游戏里就多一只敌人，
不需要改任何 Python 代码。

## 脚本格式

```text
# 井盖怪.txt     井号开头是注释，空行会被忽略
name = 井盖怪            # 必填：敌人名字(也用它当编号，除非另外写 id = xxx)
hp = 40                 # 必填：生命值，默认 40
flavor = 它把自己拧在井口上。   # 可选：出场台词，显示在名字下面
appearance = robot / 120,120,110 / 218,91,75   # 可选：形状 / 主色 / 点缀色

# 下面是行动套路，按顺序循环(第 4 回合回到第一条)
attack 9
defend 6
attack 7 effect=weak,1
```

## 三种动作(就是三种意图)

| 写法 | 意思 |
| --- | --- |
| `attack 伤害 [x段数] [effect=状态,层数] [stuff=张数]` | 攻击；`x2` 是打两段，`effect=weak,2` 是附带虚弱 2 层，`stuff=2` 是塞 2 张铁屑 |
| `defend 格挡` | 给自己套格挡 |
| `buff 力量` | 强化自己(每层力量让攻击 +1，能叠加) |

`effect` 可用：`weak`(虚弱，玩家攻击 -25%),`vulnerable`(易伤，玩家受伤 +50%),
`lose_hp`(玩家直接掉血，无视格挡)。

`appearance` 的形状可选：`beast`(野兽)/ `robe`(斗篷)/ `thief`(小偷)/
`robot`(机械)/ `colossus`(巨像)。

## 怎么加载

```powershell
python main.py --battle --scripts my_scripts          # 加载自己的目录
python main.py --battle --scripts-list                # 先看看脚本里有哪些敌人
python main.py --battle --enemy 井盖怪 --scripts my_scripts
```

仓库自带的示例(本目录)会随游戏一起加载，所以直接就能打“井盖怪”“打卡机”“抽奖转盘”。

脚本写错了不会让游戏崩：会在 `--scripts-list` 里告诉你哪个文件，哪一行，错在哪。
