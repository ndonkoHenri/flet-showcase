from typing import NamedTuple

import flet as ft
import flet_lottie as fl

BASE = "https://raw.githubusercontent.com/xvrh/lottie-flutter/master/example/assets/lottiefiles/"


class Slide(NamedTuple):
    file: str
    title: str
    body: str
    color: str


SLIDES = [
    Slide(
        "coding_ape.json",
        "Write Python",
        "Build the whole app in one language, UI included.",
        ft.Colors.AMBER_600,
    ),
    Slide(
        "rocket.json",
        "Launch fast",
        "Hot reload while you work, ship when you're ready.",
        ft.Colors.INDIGO_500,
    ),
    Slide(
        "mailsent.json",
        "Share it",
        "iOS, Android, desktop and web from the same code.",
        ft.Colors.TEAL_500,
    ),
    Slide(
        "medal.json", "You're all set", "Lottie files play right from a URL.", ft.Colors.PINK_500
    ),
]
LAST = len(SLIDES) - 1
SWIPE_DISTANCE = 40  # pixels a swipe must travel to change the page


def smooth(ms: int = 450) -> ft.Animation:
    """The ease-out animation every change on screen uses."""
    return ft.Animation(ms, ft.AnimationCurve.EASE_OUT)


def load_error() -> ft.Column:
    """What a Lottie shows instead when its file can't be downloaded."""
    return ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ft.Icon(ft.Icons.CLOUD_OFF_ROUNDED, size=64, color=ft.Colors.GREY_400),
            ft.Text("Couldn't load the animation", color=ft.Colors.GREY_600),
        ],
    )


def slide_animation(slide: Slide) -> ft.Container:
    """A slide's Lottie, in a hidden Container that fades and slides in when its page shows."""
    return ft.Container(
        opacity=0,
        offset=ft.Offset(0.3, 0),
        animate_opacity=smooth(),
        animate_offset=smooth(),
        alignment=ft.Alignment.CENTER,
        content=fl.Lottie(
            src=BASE + slide.file,
            repeat=True,
            animate=False,
            fit=ft.BoxFit.CONTAIN,
            width=340,
            height=340,
            error_content=load_error(),
        ),
    )


def page_dot(index: int, on_click: ft.ControlEventHandler[ft.Container]) -> ft.Container:
    """A page indicator; show() makes the current page's dot wide and colored."""
    return ft.Container(
        data=index, height=10, border_radius=5, animate=smooth(350), on_click=on_click
    )


def welcome_screen(on_restart: ft.ControlEventHandler[ft.TextButton]) -> ft.Column:
    """The screen after "Get started": a check mark that plays once, and a way back."""
    return ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=12,
        controls=[
            # repeat=False plays it once and stops on the last frame.
            fl.Lottie(src=BASE + "done.json", repeat=False, width=220, height=220),
            ft.Text("Welcome aboard!", size=30, weight=ft.FontWeight.W_800),
            ft.Text(
                "This is where your app would start.",
                size=18,
                color=ft.Colors.GREY_700,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.TextButton("See the intro again", icon=ft.Icons.REPLAY, on_click=on_restart),
        ],
    )


def main(page: ft.Page):
    page.title = "Lottie onboarding"
    page.padding = ft.Padding.only(left=24, right=24, top=8, bottom=20)
    page.bgcolor = ft.Colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    current = 0
    drag_start_x = 0.0

    def show(n: int):
        """Go to slide n: its animation slides in, and the texts, dots and colors follow."""
        nonlocal current
        current = n
        slide = SLIDES[n]
        for i, box in enumerate(animations.controls):
            box.opacity = 1 if i == n else 0
            box.offset = ft.Offset(0, 0) if i == n else ft.Offset(-0.3 if i < n else 0.3, 0)
            box.content.animate = i == n  # hidden ones pause, and use no CPU
        glow.bgcolor = ft.Colors.with_opacity(0.12, slide.color)
        title.value, body.value = slide.title, slide.body
        for i, dot in enumerate(dots.controls):
            dot.width = 28 if i == n else 10
            dot.bgcolor = slide.color if i == n else ft.Colors.GREY_300
        step.value = f"{n + 1} of {len(SLIDES)}"
        skip_button.visible = n < LAST
        back_button.disabled = n == 0
        next_button.bgcolor = slide.color
        next_label.value = "Get started" if n == LAST else "Next"
        page.update()

    def move(by: int):
        """Show the slide before (-1) or after (1) this one, if there's one."""
        if 0 <= current + by <= LAST:
            show(current + by)

    def handle_next(e: ft.Event[ft.Container]):
        if current < LAST:
            move(1)
        else:
            switcher.content = welcome_screen(handle_restart)
            page.update()

    def handle_dot_click(e: ft.Event[ft.Container]):
        show(e.control.data)

    def handle_restart(e: ft.Event[ft.TextButton]):
        switcher.content = onboarding
        show(0)

    def handle_drag_start(e: ft.DragStartEvent[ft.GestureDetector]):
        nonlocal drag_start_x
        drag_start_x = e.local_position.x

    def handle_drag_end(e: ft.DragEndEvent[ft.GestureDetector]):
        moved = e.local_position.x - drag_start_x
        if moved < -SWIPE_DISTANCE:  # finger moved left: the next slide comes in from the right
            move(1)
        elif moved > SWIPE_DISTANCE:
            move(-1)

    def handle_keyboard_event(e: ft.KeyboardEvent):
        if switcher.content is not onboarding:
            return
        if e.key == "Arrow Right":
            move(1)
        elif e.key == "Arrow Left":
            move(-1)

    page.on_keyboard_event = handle_keyboard_event
    page.add(
        ft.SafeArea(
            expand=True,
            content=(
                switcher := ft.AnimatedSwitcher(
                    max_width=440,  # phone-shaped, centered on wide windows
                    duration=400,
                    reverse_duration=400,
                    content=(
                        onboarding := ft.Column(
                            spacing=0,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                            controls=[
                                ft.Row(
                                    height=48,  # the same with or without Skip
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        step := ft.Text(size=16, color=ft.Colors.GREY_600),
                                        skip_button := ft.TextButton(
                                            on_click=lambda: show(LAST),
                                            content=ft.Text(
                                                "Skip",
                                                size=16,
                                                weight=ft.FontWeight.W_600,
                                                color=ft.Colors.GREY_600,
                                            ),
                                        ),
                                    ],
                                ),
                                ft.GestureDetector(
                                    expand=True,
                                    on_horizontal_drag_start=handle_drag_start,
                                    on_horizontal_drag_end=handle_drag_end,
                                    content=ft.Stack(
                                        alignment=ft.Alignment.CENTER,
                                        controls=[
                                            glow := ft.Container(
                                                width=320,
                                                height=320,
                                                shape=ft.BoxShape.CIRCLE,
                                                animate=smooth(),
                                            ),
                                            animations := ft.Stack(
                                                alignment=ft.Alignment.CENTER,
                                                controls=[
                                                    slide_animation(slide) for slide in SLIDES
                                                ],
                                            ),
                                        ],
                                    ),
                                ),
                                title := ft.Text(
                                    size=30,
                                    weight=ft.FontWeight.W_800,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                body := ft.Text(
                                    size=18,
                                    height=68,  # room for two lines: the dots stay put
                                    color=ft.Colors.GREY_700,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                dots := ft.Row(
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=8,
                                    controls=[
                                        page_dot(i, handle_dot_click) for i in range(len(SLIDES))
                                    ],
                                ),
                                ft.Container(height=28),
                                ft.Row(
                                    spacing=12,
                                    controls=[
                                        back_button := ft.IconButton(
                                            ft.Icons.ARROW_BACK_ROUNDED,
                                            icon_size=28,
                                            tooltip="Back",
                                            on_click=lambda: move(-1),
                                        ),
                                        next_button := ft.Container(
                                            expand=True,
                                            height=58,
                                            border_radius=29,
                                            alignment=ft.Alignment.CENTER,
                                            animate=smooth(),
                                            ink=True,
                                            on_click=handle_next,
                                            content=(
                                                next_label := ft.Text(
                                                    size=18,
                                                    weight=ft.FontWeight.W_700,
                                                    color=ft.Colors.WHITE,
                                                )
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ),
                )
            ),
        )
    )

    show(0)


if __name__ == "__main__":
    ft.run(main)
