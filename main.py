import asyncio
import sys

from app.bot import run


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nОстановка (Ctrl+C).", file=sys.stderr)


if __name__ == "__main__":
    main()
