"""MaderPacker entry point: python -m maderpacker"""
import sys


def main() -> int:
    from maderpacker.app import main as gui_main
    return gui_main()


if __name__ == "__main__":
    sys.exit(main())
