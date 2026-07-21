"""Reusable flat, outlined widgets for the sketch-style interface."""

import customtkinter as ctk

from card_duel.ui.theme import Theme


class SketchFrame(ctk.CTkFrame):
    """A paper card with a simple ink outline."""

    def __init__(self, master, accent=None, **kwargs):
        kwargs.setdefault("fg_color", Theme.PAPER)
        kwargs.setdefault("border_color", accent or Theme.BORDER)
        kwargs.setdefault("border_width", 2)
        kwargs.setdefault("corner_radius", Theme.CORNER_RADIUS)
        super().__init__(master, **kwargs)


class SketchButton(ctk.CTkButton):
    """An outlined button with a muted marker-color hover state."""

    def __init__(self, master, accent=Theme.BLUE, **kwargs):
        kwargs.setdefault("fg_color", Theme.PAPER)
        kwargs.setdefault("hover_color", accent)
        kwargs.setdefault("border_color", Theme.BORDER)
        kwargs.setdefault("border_width", 2)
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("text_color", Theme.TEXT)
        kwargs.setdefault("font", Theme.BODY_FONT)
        super().__init__(master, **kwargs)


class StatBar(ctk.CTkFrame):
    """Compact labelled stat bar used for health and energy."""

    def __init__(self, master, label, maximum_value, color, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.maximum_value = max(maximum_value, 1)
        self._normal_color = color

        label_row = ctk.CTkFrame(self, fg_color="transparent")
        label_row.pack(fill="x")
        ctk.CTkLabel(
            label_row,
            text=label,
            font=Theme.SMALL_FONT,
            text_color=Theme.TEXT_SECONDARY,
        ).pack(side="left")
        self._value_label = ctk.CTkLabel(
            label_row,
            text=str(maximum_value),
            font=Theme.SMALL_FONT,
            text_color=Theme.TEXT,
        )
        self._value_label.pack(side="right")

        self._bar = ctk.CTkProgressBar(
            self,
            progress_color=color,
            fg_color=Theme.PANEL_LIGHT,
            border_color=Theme.BORDER,
            border_width=1,
            height=12,
            corner_radius=3,
        )
        self._bar.pack(fill="x", pady=(3, 0))
        self._bar.set(1.0)

    def update_value(self, value):
        ratio = max(0.0, min(1.0, value / self.maximum_value))
        self._bar.set(ratio)
        self._value_label.configure(text=str(max(0, value)))
        color = Theme.RED if ratio < 0.3 else self._normal_color
        self._bar.configure(progress_color=color)
