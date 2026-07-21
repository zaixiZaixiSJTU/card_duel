"""Battle screen for the lightweight local game."""

import customtkinter as ctk

from card_duel.core.demo import LocalGame
from card_duel.ui.theme import Theme
from card_duel.ui.widgets import SketchButton, SketchFrame, StatBar


class GameScreen(ctk.CTkFrame):
    def __init__(
        self,
        master,
        player_one_character_id,
        player_two_character_id,
        on_restart,
    ):
        super().__init__(master, fg_color="transparent")
        self._on_restart = on_restart
        self._game = LocalGame(
            player_one_character_id,
            player_two_character_id,
        )
        self._build_ui()
        self._start_new_round()

    def _build_ui(self):
        top_panel = SketchFrame(self)
        top_panel.pack(fill="x", padx=20, pady=(14, 8))
        top_content = ctk.CTkFrame(top_panel, fg_color="transparent")
        top_content.pack(fill="x", padx=16, pady=10)

        self._round_label = ctk.CTkLabel(
            top_content,
            text="ROUND 1",
            font=Theme.HEADING_FONT,
            text_color=Theme.GOLD,
        )
        self._round_label.pack(side="left")
        self._turn_label = ctk.CTkLabel(
            top_content,
            text="",
            font=Theme.SUBHEADING_FONT,
            text_color=Theme.CYAN,
        )
        self._turn_label.pack(side="right")

        middle_panel = ctk.CTkFrame(self, fg_color="transparent")
        middle_panel.pack(fill="both", expand=True, padx=20, pady=6)
        middle_panel.grid_columnconfigure(0, weight=1)
        middle_panel.grid_columnconfigure(1, weight=2)
        middle_panel.grid_columnconfigure(2, weight=1)
        middle_panel.grid_rowconfigure(0, weight=1)

        player_one_panel = self._build_player_panel(
            middle_panel, 1, self._game.players[1]
        )
        player_one_panel.grid(
            row=0, column=0, sticky="nsew", padx=(0, 6)
        )

        log_panel = SketchFrame(middle_panel)
        log_panel.grid(row=0, column=1, sticky="nsew", padx=6)
        ctk.CTkLabel(
            log_panel,
            text="战斗记录  /  NOTES",
            font=Theme.SUBHEADING_FONT,
            text_color=Theme.TEXT_SECONDARY,
        ).pack(pady=(10, 4))
        self._log_textbox = ctk.CTkTextbox(
            log_panel,
            font=Theme.BODY_FONT,
            fg_color=Theme.PAPER,
            text_color=Theme.TEXT,
            border_width=1,
            border_color=Theme.BORDER_SOFT,
            corner_radius=6,
            activate_scrollbars=True,
            wrap="word",
        )
        self._log_textbox.pack(
            fill="both", expand=True, padx=10, pady=(0, 10)
        )
        self._log_textbox.configure(state="disabled")

        player_two_panel = self._build_player_panel(
            middle_panel, 2, self._game.players[2]
        )
        player_two_panel.grid(
            row=0, column=2, sticky="nsew", padx=(6, 0)
        )

        self._build_controls()

    def _build_player_panel(self, parent, player_id, player):
        panel = SketchFrame(parent, accent=player.color)
        ctk.CTkLabel(
            panel,
            text=player.icon,
            font=Theme.ICON_FONT,
            text_color=player.color,
        ).pack(pady=(16, 2))
        ctk.CTkLabel(
            panel,
            text=f"P{player_id}",
            font=Theme.SMALL_FONT,
            text_color=Theme.TEXT_DIM,
        ).pack()
        ctk.CTkLabel(
            panel,
            text=player.name,
            font=Theme.SUBHEADING_FONT,
            text_color=Theme.TEXT,
        ).pack(pady=(2, 12))

        health_bar = StatBar(panel, "生命", player.max_health, Theme.GREEN)
        health_bar.pack(fill="x", padx=14, pady=(0, 6))
        energy_bar = StatBar(panel, "能量", 10, Theme.BLUE)
        energy_bar.pack(fill="x", padx=14, pady=(0, 16))
        energy_bar.update_value(0)

        if player_id == 1:
            self._player_one_health_bar = health_bar
            self._player_one_energy_bar = energy_bar
        else:
            self._player_two_health_bar = health_bar
            self._player_two_energy_bar = energy_bar
        return panel

    def _build_controls(self):
        bottom_panel = SketchFrame(self)
        bottom_panel.pack(fill="x", padx=20, pady=(8, 14))
        button_row = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        button_row.pack(pady=12)

        self._play_button = SketchButton(
            button_row,
            text="＋  出牌",
            accent=Theme.BLUE,
            command=self._play_card,
            width=130,
            height=42,
        )
        self._play_button.pack(side="left", padx=8)
        self._end_turn_button = SketchButton(
            button_row,
            text="→  结束回合",
            accent=Theme.GOLD,
            command=self._end_turn,
            width=130,
            height=42,
        )
        self._end_turn_button.pack(side="left", padx=8)
        SketchButton(
            button_row,
            text="≡  查看属性",
            accent=Theme.CYAN,
            command=self._show_status,
            width=130,
            height=42,
        ).pack(side="left", padx=8)
        SketchButton(
            button_row,
            text="···  留言",
            accent=Theme.PINK,
            command=self._toggle_chat,
            width=130,
            height=42,
        ).pack(side="left", padx=8)

        self._chat_frame = ctk.CTkFrame(
            bottom_panel, fg_color="transparent"
        )
        self._chat_entry = ctk.CTkEntry(
            self._chat_frame,
            placeholder_text="输入消息...",
            font=Theme.BODY_FONT,
            fg_color=Theme.PAPER,
            border_color=Theme.BORDER,
            corner_radius=10,
            width=320,
            height=36,
        )
        self._chat_entry.pack(side="left", padx=(0, 8))
        self._chat_entry.bind("<Return>", self._send_chat)
        SketchButton(
            self._chat_frame,
            text="发送",
            accent=Theme.PINK,
            command=self._send_chat,
            width=72,
            height=36,
        ).pack(side="left")
        self._is_chat_visible = False

    def _append_log(self, message):
        self._log_textbox.configure(state="normal")
        self._log_textbox.insert("end", message + "\n")
        self._log_textbox.see("end")
        self._log_textbox.configure(state="disabled")

    def _sync_bars(self):
        player_one = self._game.players[1]
        player_two = self._game.players[2]
        self._player_one_health_bar.update_value(player_one.health)
        self._player_two_health_bar.update_value(player_two.health)
        self._player_one_energy_bar.update_value(player_one.energy)
        self._player_two_energy_bar.update_value(player_two.energy)

    def _refresh_turn(self):
        if self._game.is_over:
            return
        current_player = self._game.current_player
        self._turn_label.configure(
            text=(
                f"▶  玩家{self._game.active_player_id} "
                f"({current_player.name})"
            ),
            text_color=current_player.color,
        )

    def _start_new_round(self):
        messages = self._game.start_round()
        self._sync_bars()
        self._round_label.configure(
            text=f"ROUND {self._game.round_number}"
        )
        for message in messages:
            self._append_log(message)
        self._refresh_turn()

    def _play_card(self):
        if self._game.is_over:
            return
        was_played, damage = self._game.play_card()
        if not was_played:
            self._append_log("  !  能量不足（需要 2 点能量）")
            return

        self._sync_bars()
        self._append_log(
            f"  +  玩家{self._game.active_player_id} 出牌"
            f" → 造成 {damage} 点伤害!"
        )
        if self._game.is_over:
            self._show_game_over()

    def _end_turn(self):
        if self._game.is_over:
            return
        self._append_log(
            f"  ⏭ 玩家{self._game.active_player_id} 结束回合"
        )
        self._append_log("─" * 36)
        if self._game.end_turn() == "switch":
            self._refresh_turn()
        else:
            self._start_new_round()

    def _show_status(self):
        for line in self._game.format_status():
            self._append_log(line)

    def _toggle_chat(self):
        if self._is_chat_visible:
            self._chat_frame.pack_forget()
        else:
            self._chat_frame.pack(pady=(0, 10))
            self._chat_entry.focus()
        self._is_chat_visible = not self._is_chat_visible

    def _send_chat(self, _event=None):
        message = self._chat_entry.get().strip()
        if not message:
            return
        self._append_log(self._game.format_chat(message))
        self._chat_entry.delete(0, "end")

    def _show_game_over(self):
        winner_id = self._game.winner_id
        self._append_log(f"\n★  玩家{winner_id} 获胜  ★\n")
        self._turn_label.configure(
            text=f"★  玩家{winner_id} 获胜",
            text_color=Theme.GOLD,
        )
        self._play_button.configure(state="disabled")
        self._end_turn_button.configure(state="disabled")
        SketchButton(
            self,
            text="↻  再来一局",
            accent=Theme.CYAN,
            command=self._on_restart,
            width=160,
            height=42,
        ).pack(pady=(0, 10))
