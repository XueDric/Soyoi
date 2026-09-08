"""soyoi_game 包入口。运行：python -m soyoi_game"""

from .ui.pygame_demo import run

__all__ = ["run"]


def main() -> None:
    run()


if __name__ == "__main__":
    main()
