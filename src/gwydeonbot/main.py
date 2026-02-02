from __future__ import annotations

from .bot import GwydeonBot


def main() -> None:
    bot = GwydeonBot()
    bot.run(bot.settings.discord_token)


if __name__ == "__main__":
    main()
