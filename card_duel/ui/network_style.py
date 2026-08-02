"""Sketch-paper visual tokens for the network UI."""

import FreeSimpleGUI as sg

THEME = "SketchPaper"
WINDOW_SIZE = (1200, 660)
WINDOW_TITLE = "Card Duel · 手绘对战"

COLOR_BACKGROUND = "#F5F0E6"
COLOR_PAPER = "#FFFDF8"
COLOR_PAPER_DARK = "#EFE6D8"
COLOR_INK = "#2E2A26"
COLOR_MUTED = "#837A70"
COLOR_LINE = "#B9AEA0"
COLOR_RED = "#C86655"
COLOR_RED_LIGHT = "#E8C8BE"
COLOR_BLUE = "#6F89A8"
COLOR_GREEN = "#719775"
COLOR_GOLD = "#C39A55"
COLOR_DISABLED = "#D8D0C5"

FONT_TITLE = ("KaiTi", 24, "bold")
FONT_HEADING = ("KaiTi", 16, "bold")
FONT_BODY = ("Microsoft YaHei UI", 11)
FONT_BODY_BOLD = ("Microsoft YaHei UI", 11, "bold")
FONT_MONO = ("Consolas", 10)

MAX_HAND_BUTTONS = 12
MAX_HEALTH_DISPLAY = 40
MAX_ENERGY_ORBS = 8

PHASE_LABELS = (
    "回合开始时",
    "抽牌阶段",
    "出牌阶段",
    "弃牌阶段",
    "回合结束时",
)

CHAT_INPUT_KEY = "-CHAT-INPUT-"
CHAT_SEND_KEY = "-CHAT-SEND-"


def init_theme() -> None:
    if THEME not in sg.theme_list():
        sg.theme_add_new(
            THEME,
            {
                "BACKGROUND": COLOR_BACKGROUND,
                "TEXT": COLOR_INK,
                "INPUT": COLOR_PAPER,
                "TEXT_INPUT": COLOR_INK,
                "SCROLL": COLOR_PAPER_DARK,
                "BUTTON": (COLOR_INK, COLOR_PAPER),
                "PROGRESS": (COLOR_RED, COLOR_RED_LIGHT),
                "BORDER": 1,
                "SLIDER_DEPTH": 0,
                "PROGRESS_DEPTH": 0,
            },
        )
    sg.theme(THEME)
