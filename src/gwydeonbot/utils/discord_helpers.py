from __future__ import annotations

import discord


def class_color(class_id: int | None) -> discord.Color:
    by_id: dict[int, discord.Color] = {
        1: discord.Color.from_rgb(198, 155, 109),
        2: discord.Color.from_rgb(244, 140, 186),
        3: discord.Color.from_rgb(170, 211, 114),
        4: discord.Color.from_rgb(255, 244, 104),
        5: discord.Color.from_rgb(255, 255, 255),
        6: discord.Color.from_rgb(196, 30, 58),
        7: discord.Color.from_rgb(0, 112, 222),
        8: discord.Color.from_rgb(63, 199, 235),
        9: discord.Color.from_rgb(135, 136, 238),
        10: discord.Color.from_rgb(0, 255, 152),
        11: discord.Color.from_rgb(255, 125, 10),
        12: discord.Color.from_rgb(163, 48, 201),
        13: discord.Color.from_rgb(51, 147, 127),
    }
    return by_id.get(class_id or -1, discord.Color.blurple())
