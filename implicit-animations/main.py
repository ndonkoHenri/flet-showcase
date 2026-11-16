import math
from dataclasses import dataclass

import flet as ft


@dataclass
class Move:
    """One card: the animate_* property to switch on, and the values the box goes between."""

    prop: str
    color: ft.ColorValue
    curve: ft.AnimationCurve
    start: dict
    end: dict


MOVES = [
    # A Container's own `animate` covers its size, color, corners and padding at once.
    Move(
        "animate",
        ft.Colors.INDIGO_500,
        ft.AnimationCurve.EASE_IN_OUT_CUBIC,
        start={"width": 56, "bgcolor": ft.Colors.INDIGO_500},
        end={"width": 130, "bgcolor": ft.Colors.CYAN_500},
    ),
    Move(
        "animate_opacity",
        ft.Colors.PINK_500,
        ft.AnimationCurve.EASE_IN_OUT,
        start={"opacity": 1},
        end={"opacity": 0.12},
    ),
    Move(
        "animate_rotation",
        ft.Colors.AMBER_800,
        ft.AnimationCurve.ELASTIC_OUT,
        start={"rotate": 0},
        end={"rotate": math.pi},  # half a turn
    ),
    Move(
        "animate_offset",
        ft.Colors.TEAL_600,
        ft.AnimationCurve.BOUNCE_OUT,
        start={"offset": (0, 0)},
        end={"offset": (1.6, 0)},  # 1.6 box widths to the right
    ),
    Move(
        "animate_scale",
        ft.Colors.DEEP_PURPLE_500,
        ft.AnimationCurve.EASE_OUT_BACK,
        start={"scale": 1},
        end={"scale": 1.6},
    ),
]
EACH_OWN = "EACH_OWN"  # curve menu key: every card keeps its own curve
START_DURATION = 800  # milliseconds


def curve_name(curve: ft.AnimationCurve) -> str:
    """ELASTIC_OUT -> "elastic out"."""
    return curve.name.lower().replace("_", " ")


def set_values(box: ft.Container, values: dict):
    """Set each property in values (like rotate or opacity) on the box."""
    for name, value in values.items():
        setattr(box, name, value)


def at_end(box: ft.Container) -> bool:
    """Whether the box shows its end values."""
    return all(getattr(box, name) == value for name, value in box.data.end.items())


def make_box(move: Move) -> ft.Container:
    """A star box at its start values, with its animation already on."""
    box = ft.Container(
        data=move,
        width=56,
        height=56,
        border_radius=16,
        bgcolor=move.color,
        content=ft.Icon(ft.Icons.STAR_ROUNDED, color=ft.Colors.WHITE, size=30),
    )
    # Switched on from the start: the first change would jump otherwise.
    setattr(box, move.prop, ft.Animation(START_DURATION, move.curve))
    set_values(box, move.start)
    return box


def card(
    box: ft.Container, curve_text: ft.Text, on_click: ft.ControlEventHandler[ft.Container]
) -> ft.Container:
    """A tinted card with the property name, its curve and the box; a tap flips the box."""
    move: Move = box.data
    return ft.Container(
        data=box,
        on_click=on_click,
        height=80,
        border_radius=22,
        bgcolor=ft.Colors.with_opacity(0.08, move.color),
        padding=ft.Padding.symmetric(horizontal=16),
        content=ft.Row(
            spacing=12,
            controls=[
                ft.Column(
                    width=150,
                    spacing=2,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            move.prop,
                            size=15,
                            weight=ft.FontWeight.W_700,
                            font_family="monospace",
                            color=move.color,
                        ),
                        curve_text,
                    ],
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.only(left=12),  # room for the zoomed box
                    alignment=ft.Alignment.CENTER_LEFT,
                    content=box,
                ),
            ],
        ),
    )


def main(page: ft.Page):
    page.title = "Implicit animations"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    boxes = [make_box(move) for move in MOVES]
    curve_texts = {
        box: ft.Text(curve_name(box.data.curve), size=15, color=ft.Colors.GREY_600) for box in boxes
    }

    def chosen_curve(move: Move) -> ft.AnimationCurve:
        """The curve picked in the menu, or the card's own one."""
        if curve_menu.value == EACH_OWN:
            return move.curve
        return ft.AnimationCurve[curve_menu.value]

    def send(box: ft.Container, values: dict):
        """Give the box the chosen curve and duration, then its new values: Flet animates them."""
        move: Move = box.data
        setattr(box, move.prop, ft.Animation(int(duration.value), chosen_curve(move)))
        set_values(box, values)

    def handle_card_click(e: ft.Event[ft.Container]):
        box = e.control.data
        send(box, box.data.start if at_end(box) else box.data.end)
        page.update()

    def handle_play_click(e: ft.Event[ft.FilledButton]):
        for box in boxes:
            send(box, box.data.end)
        page.update()

    def handle_reset_click(e: ft.Event[ft.OutlinedButton]):
        for box in boxes:
            send(box, box.data.start)
        page.update()

    def handle_curve_select(e: ft.Event[ft.Dropdown]):
        for box, curve_text in curve_texts.items():
            curve_text.value = curve_name(chosen_curve(box.data))
        page.update()

    def handle_duration_change(e: ft.Event[ft.Slider]):
        duration_text.value = f"{int(e.control.value)} ms"
        page.update()

    page.add(
        ft.SafeArea(
            content=ft.Column(
                max_width=430,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Text("Implicit animations", size=30, weight=ft.FontWeight.W_800),
                    ft.Text(
                        "Tap a card to change its value: Flet animates it.",
                        size=17,
                        color=ft.Colors.GREY_600,
                    ),
                    *[card(box, curve_texts[box], handle_card_click) for box in boxes],
                    ft.Row(
                        controls=[
                            curve_menu := ft.Dropdown(
                                expand=True,  # as wide as the cards (it needs a Row for that)
                                label="Curve",
                                value=EACH_OWN,
                                menu_height=320,
                                on_select=handle_curve_select,
                                options=[
                                    ft.DropdownOption(key=EACH_OWN, text="Each its own"),
                                    *[
                                        ft.DropdownOption(key=curve.name, text=curve_name(curve))
                                        for curve in ft.AnimationCurve
                                    ],
                                ],
                            )
                        ]
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Duration", size=16),
                            duration := ft.Slider(
                                expand=True,
                                min=100,
                                max=3000,
                                divisions=29,
                                value=START_DURATION,
                                on_change=handle_duration_change,
                            ),
                            duration_text := ft.Text(f"{START_DURATION} ms", size=16, width=72),
                        ]
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.FilledButton(
                                "Animate all",
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                on_click=handle_play_click,
                            ),
                            ft.OutlinedButton(
                                "Reset", icon=ft.Icons.REPLAY_ROUNDED, on_click=handle_reset_click
                            ),
                        ],
                    ),
                ],
            )
        )
    )


if __name__ == "__main__":
    ft.run(main)
