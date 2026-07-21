"""Character-selection screen for the local demo."""

import customtkinter as ctk

from card_duel.core.characters import LOCAL_CHARACTER_PROFILES
from card_duel.ui.character_card import CharacterCard
from card_duel.ui.theme import Theme
from card_duel.ui.widgets import SketchButton


class SelectionScreen(ctk.CTkFrame):
    def __init__(self, master, on_start):
        super().__init__(master, fg_color="transparent")
        self._on_start = on_start
        self._selected_character_ids = {1: None, 2: None}
        self._selecting_player_id = 1

        ctk.CTkLabel(
            self,
            text="CARD DUEL",
            font=Theme.TITLE_FONT,
            text_color=Theme.TEXT,
        ).pack(pady=(42, 0))
        ctk.CTkLabel(
            self,
            text="——  简单一点，出牌吧  ——",
            font=Theme.BODY_FONT,
            text_color=Theme.TEXT_SECONDARY,
        ).pack(pady=(2, 28))

        self._phase_label = ctk.CTkLabel(
            self,
            text="玩家 1 · 选择角色",
            font=Theme.HEADING_FONT,
            text_color=Theme.CYAN,
        )
        self._phase_label.pack(pady=(0, 18))

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(pady=10)
        self._character_cards = {}
        for column_index, character_id in enumerate(LOCAL_CHARACTER_PROFILES):
            character_card = CharacterCard(
                cards_frame,
                character_id,
                self._select_character,
            )
            character_card.grid(
                row=0, column=column_index, padx=12, pady=6
            )
            character_card.configure(width=220, height=238)
            self._character_cards[character_id] = character_card

        self._confirm_button = SketchButton(
            self,
            text="确认  →",
            accent=Theme.GREEN,
            command=self._confirm_selection,
            width=180,
            height=44,
            state="disabled",
        )
        self._confirm_button.pack(pady=28)

        self._summary_label = ctk.CTkLabel(
            self,
            text="",
            font=Theme.BODY_FONT,
            text_color=Theme.TEXT_DIM,
        )
        self._summary_label.pack()

    def _select_character(self, character_id):
        for character_card in self._character_cards.values():
            character_card.set_selected(False)
        self._character_cards[character_id].set_selected(True)
        self._selected_character_ids[self._selecting_player_id] = character_id
        self._confirm_button.configure(state="normal")

    def _confirm_selection(self):
        character_id = self._selected_character_ids[self._selecting_player_id]
        if character_id is None:
            return

        if self._selecting_player_id == 1:
            character_name = LOCAL_CHARACTER_PROFILES[character_id]["name"]
            self._summary_label.configure(
                text=f"玩家 1 已选：{character_name}  ✓",
                text_color=Theme.CYAN,
            )
            self._selecting_player_id = 2
            self._phase_label.configure(
                text="玩家 2 · 选择角色",
                text_color=Theme.PINK,
            )
            for character_card in self._character_cards.values():
                character_card.set_selected(False)
            self._confirm_button.configure(state="disabled")
            return

        self._on_start(
            self._selected_character_ids[1],
            self._selected_character_ids[2],
        )
