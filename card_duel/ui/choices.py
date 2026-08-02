"""FreeSimpleGUI implementation of card-effect choices."""

from __future__ import annotations

from collections.abc import Sequence

import FreeSimpleGUI as sg


class GuiChoiceProvider:
    def __init__(self, card_images: Sequence[bytes]):
        self.card_images = card_images

    def choose_integer(self, title, prompt, minimum, maximum, default):
        value = sg.popup_get_text(
            prompt, default_text=str(default), title=title, keep_on_top=True
        )
        if value is None:
            return None
        try:
            return max(minimum, min(maximum, int(value)))
        except ValueError:
            return None

    def choose_option(self, title, prompt, options, default):
        layout = [[sg.Text(prompt)]] + [
            [sg.Button(option, key=option)] for option in options
        ]
        window = sg.Window(title, layout, modal=True, keep_on_top=True)
        event, _ = window.read()
        window.close()
        return event if event in options else None

    def choose_card_indexes(self, title, hand, count, excluded_card_id=None):
        if count == 0:
            return []
        buttons = []
        for index, card_id in enumerate(hand):
            if card_id == excluded_card_id:
                continue
            buttons.append(
                sg.Button(
                    image_data=self.card_images[card_id],
                    key=index,
                    pad=(4, 4),
                )
            )
        layout = [
            [sg.Text(f"请选择 {count} 张牌")],
            [sg.Column([buttons], scrollable=True, size=(620, 240))],
            [sg.Text("已选择 0 张", key="-COUNT-")],
        ]
        window = sg.Window(title, layout, modal=True, keep_on_top=True, finalize=True)
        selected: list[int] = []
        while len(selected) < count:
            event, _ = window.read()
            if event == sg.WIN_CLOSED:
                window.close()
                return None
            if isinstance(event, int) and event not in selected:
                selected.append(event)
                window[event].update(disabled=True)
                window["-COUNT-"].update(f"已选择 {len(selected)} 张")
        window.close()
        return selected
