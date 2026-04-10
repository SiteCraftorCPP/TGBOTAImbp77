import asyncio
import os
import sys
import time
import traceback

from app.bot import run


def _restart_delay_sec() -> float:
    raw = os.getenv("BOT_RESTART_DELAY_SEC", "5").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 5.0


def main() -> None:
    delay = _restart_delay_sec()
    while True:
        try:
            asyncio.run(run())
            break
        except KeyboardInterrupt:
            print("\nОстановка (Ctrl+C).", file=sys.stderr)
            break
        except SystemExit:
            raise
        except Exception:
            print(
                f"Сбой при работе бота, перезапуск через {delay:.0f} с…",
                file=sys.stderr,
            )
            traceback.print_exc()
            time.sleep(delay)


if __name__ == "__main__":
    main()
