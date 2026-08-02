"""Shared character definitions used by the game and user interfaces."""

CHARACTER_NAMES = {
    1: "战士",
    2: "女猎手",
    3: "时间守护者",
    4: "蛞蝓猫",
}

LOCAL_CHARACTER_PROFILES = {
    1: {
        "name": "战士",
        "icon": "⚔",
        "description": "近战之王 · 高生命值",
        "color": "#C86655",
        "health": 45,
        "energy_range": (4, 6),
    },
    2: {
        "name": "女猎手",
        "icon": "➶",
        "description": "远程打击 · 高暴击率",
        "color": "#719775",
        "health": 38,
        "energy_range": (5, 7),
    },
    3: {
        "name": "时间守护者",
        "icon": "⌛",
        "description": "时空操控 · 高能量恢复",
        "color": "#8B79A8",
        "health": 35,
        "energy_range": (6, 8),
    },
    4: {
        "name": "蛞蝓猫",
        "icon": "◡",
        "description": "雨中旅者 · 业力与动能",
        "color": "#C39A55",
        "health": 5,
        "energy_range": (4, 6),
    },
}
