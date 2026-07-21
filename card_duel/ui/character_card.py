"""Clickable character-card widget."""

import customtkinter as ctk

from card_duel.core.characters import LOCAL_CHARACTER_PROFILES
from card_duel.ui.theme import Theme
from card_duel.ui.widgets import SketchFrame


class CharacterCard(SketchFrame):
    def __init__(self, master, character_id, on_select, **kwargs):
        self._profile = LOCAL_CHARACTER_PROFILES[character_id]
        super().__init__(master, **kwargs)
        self._character_id = character_id
        self._on_select = on_select
        self._accent_color = self._profile["color"]
        self.configure(cursor="hand2")

        ctk.CTkLabel(
            self,
            text=f"0{character_id}",
            font=Theme.SMALL_FONT,
            text_color=Theme.TEXT_DIM,
        ).place(x=12, y=10)

        icon_label = ctk.CTkLabel(
            self,
            text=self._profile["icon"],
            font=Theme.ICON_FONT,
            text_color=self._accent_color,
        )
        icon_label.pack(pady=(28, 8))

        name_label = ctk.CTkLabel(
            self,
            text=self._profile["name"],
            font=Theme.SUBHEADING_FONT,
            text_color=Theme.TEXT,
        )
        name_label.pack(pady=(0, 2))

        description_label = ctk.CTkLabel(
            self,
            text=self._profile["description"],
            font=Theme.SMALL_FONT,
            text_color=Theme.TEXT_SECONDARY,
        )
        description_label.pack(pady=(4, 8))

        minimum_energy, maximum_energy = self._profile["energy_range"]
        stats_text = (
            f"HP {self._profile['health']}  |  "
            f"EP {minimum_energy}-{maximum_energy}"
        )
        stats_label = ctk.CTkLabel(
            self,
            text=stats_text,
            font=Theme.SMALL_FONT,
            text_color=Theme.TEXT_DIM,
        )
        stats_label.pack(pady=(0, 20))

        for widget in (
            self,
            icon_label,
            name_label,
            description_label,
            stats_label,
        ):
            widget.bind("<Button-1>", self._handle_click)

    def _handle_click(self, _event):
        self._on_select(self._character_id)

    def set_selected(self, is_selected):
        if is_selected:
            self.configure(
                border_color=self._accent_color,
                fg_color=Theme.PANEL_LIGHT,
                border_width=3,
            )
        else:
            self.configure(
                border_color=Theme.BORDER,
                fg_color=Theme.PAPER,
                border_width=2,
            )
