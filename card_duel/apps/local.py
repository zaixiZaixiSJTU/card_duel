"""Local two-player Card Duel application."""

import tkinter as tk
import customtkinter as ctk
from PIL import ImageTk

from card_duel.ui.theme import Theme
from card_duel.ui.background import make_paper_background
from card_duel.ui.selection import SelectionScreen
from card_duel.ui.game import GameScreen


class LocalGameApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")

        self.title("Card Duel · 手绘卡牌对决")
        self.geometry("1060x720")
        self.minsize(920, 620)
        self.configure(fg_color=Theme.BACKGROUND)

        # 纸张背景独立绘制，内容层保持透明。
        self._background_canvas = tk.Canvas(
            self, highlightthickness=0, bd=0
        )
        self._background_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._background_photo = None
        self._resize_job = None
        self._draw_background()
        self.bind("<Configure>", self._on_resize)

        # 页面内容统一挂载在这个容器中。
        self._content_container = ctk.CTkFrame(
            self, fg_color="transparent"
        )
        self._content_container.place(x=0, y=0, relwidth=1, relheight=1)

        self._show_selection_screen()

    # --- 背景 ---
    def _draw_background(self):
        width = max(self.winfo_width(), 920)
        height = max(self.winfo_height(), 620)
        background_image = make_paper_background(width, height)
        self._background_photo = ImageTk.PhotoImage(background_image)
        self._background_canvas.delete("background")
        self._background_canvas.create_image(
            0,
            0,
            anchor="nw",
            image=self._background_photo,
            tags="background",
        )

    def _on_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(250, self._draw_background)

    # --- 页面切换 ---
    def _clear_content(self):
        for widget in self._content_container.winfo_children():
            widget.destroy()

    def _show_selection_screen(self):
        self._clear_content()
        SelectionScreen(
            self._content_container, self._start_game
        ).pack(fill="both", expand=True)

    def _start_game(
        self,
        player_one_character_id,
        player_two_character_id,
    ):
        self._clear_content()
        GameScreen(
            self._content_container,
            player_one_character_id,
            player_two_character_id,
            on_restart=self._show_selection_screen,
        ).pack(fill="both", expand=True)


def main():
    application = LocalGameApp()
    application.mainloop()


if __name__ == "__main__":
    main()
