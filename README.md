# Soyoi 课程游戏仓库

正式项目位于 [`soyoi-game/`](soyoi-game/)。该目录包含 pygame 可视化 Demo、战斗引擎、
40 张精简卡牌、素材系统、测试和协作文档。

```powershell
cd soyoi-game
python -m pip install -e .
python -m soyoi_game
```

运行测试：

```powershell
cd soyoi-game
python -m unittest discover -s tests -v
```

协作时请从仓库根目录执行 Git 命令，从 `soyoi-game/` 目录运行游戏与测试。
