import asyncio
import functools
import itertools
import time

import flet as ft
import flet.canvas as cv
import numpy as np

ACCENT, INK, MUTED, CARD = "#E00050", "#1B1A22", "#6B6A78", "#F4F3F8"
UNLIT = "#ECEBF2"  # an empty pixel of the 8x8 grid, and an empty bar
FAINT = "#D6D5E0"  # the "?" before a guess
BAR_HEIGHT = 56  # a bar at 100% confidence
SURE = 0.5  # below this, the app says "Maybe a ..."


@functools.cache  # trained once, then shared by every window and browser tab
def train():
    """Fit the model on scikit-learn's built-in digits; return it, the digit count and seconds."""
    # Imported here, so the app shows up while scikit-learn loads.
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.datasets import load_digits
    from sklearn.svm import SVC

    digits = load_digits()  # 1,797 handwritten digits, 8x8 pixels each
    start = time.perf_counter()
    svc = SVC(gamma=0.001, C=10)
    model = CalibratedClassifierCV(svc, ensemble=False)  # adds a confidence per digit
    model.fit(digits.data, digits.target)
    return model, len(digits.data), time.perf_counter() - start


def to_8x8(strokes: list[list[tuple[float, float]]], fill=24, pen=6.0) -> np.ndarray:
    """Shrink the strokes to 8x8 pixels of 0-16, the way the training digits were made.

    The drawing is scaled so its longer side spans `fill` of 32 px, centred in a 32x32
    bitmap with a `pen`-wide nib, then each 4x4 block is counted.
    """
    points = np.array([p for stroke in strokes for p in stroke], float)
    (x0, y0), (x1, y1) = points.min(0), points.max(0)
    scale = fill / max(x1 - x0, y1 - y0, 1.0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    yy, xx = np.mgrid[0:32, 0:32] + 0.5
    image = np.zeros((32, 32), bool)
    for stroke in strokes:
        q = [((x - cx) * scale + 16, (y - cy) * scale + 16) for x, y in stroke]
        for (ax, ay), (bx, by) in list(itertools.pairwise(q)) or [(q[0], q[0])]:
            # Light every pixel within pen / 2 of the segment from a to b.
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / length2, 0, 1) if length2 else 0
            image |= np.hypot(xx - (ax + t * dx), yy - (ay + t * dy)) <= pen / 2
    return image.reshape(8, 4, 8, 4).sum((1, 3)).astype(float)


def guess(model, strokes: list[list[tuple[float, float]]]) -> tuple[np.ndarray, np.ndarray, float]:
    """The model's confidence for each digit 0-9, the 8x8 grid it saw, and the milliseconds."""
    grid = to_8x8(strokes)  # shrink your drawing
    start = time.perf_counter()
    chances = model.predict_proba([grid.ravel()])[0]  # one per digit, in order 0-9
    return chances, grid, (time.perf_counter() - start) * 1000


def ink(a: tuple[float, float], b: tuple[float, float]) -> cv.Line:
    """A piece of a stroke, from point a to point b."""
    paint = ft.Paint(color=INK, stroke_width=16, stroke_cap=ft.StrokeCap.ROUND)
    return cv.Line(x1=a[0], y1=a[1], x2=b[0], y2=b[1], paint=paint)


def card(content: ft.Control, expand: bool = False) -> ft.Container:
    """A rounded grey card around content."""
    return ft.Container(bgcolor=CARD, border_radius=18, padding=12, expand=expand, content=content)


def caption(value: str) -> ft.Text:
    """A small grey title for a card."""
    return ft.Text(value, size=13, color=MUTED, weight=ft.FontWeight.W_600)


async def main(page: ft.Page):
    page.title = "Draw a digit"
    page.bgcolor = ft.Colors.WHITE
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    if not page.web and page.platform.is_desktop():
        page.window.width, page.window.height = 440, 860  # phone-shaped, room to draw
    strokes: list[list[tuple[float, float]]] = []  # each stroke is a list of (x, y) points

    def show_guess():
        """Show what the model makes of the strokes, or the empty state, on the screen."""
        hint.visible = not strokes
        undo_button.disabled = clear_button.disabled = not strokes
        if strokes:
            chances, grid, ms = guess(model, strokes)
            digit = int(chances.argmax())
            verdict.value = (
                f"Looks like a {digit}" if chances[digit] >= SURE else f"Maybe a {digit}?"
            )
            verdict.color = INK
            big.value, big.color = str(digit), ACCENT
            meta.value = f"{chances[digit]:.0%} sure · {ms:.1f} ms"
        else:
            chances, grid, digit = np.zeros(10), np.zeros((8, 8)), None
            verdict.value, verdict.color = "Waiting for a digit", MUTED
            big.value, big.color = "?", FAINT
            meta.value = ""
        for pixel, value in zip(pixels.controls, grid.ravel()):
            pixel.bgcolor = (
                ft.Colors.with_opacity(0.08 + 0.92 * value / 16, INK) if value else UNLIT
            )
        for d, (bar, chance) in enumerate(zip(bars.controls, chances)):
            bar.content.height = BAR_HEIGHT * chance
            bar.content.bgcolor = ACCENT if d == digit else MUTED
        page.update()

    def draw_to(point: ft.Offset):
        """Extend the current stroke to point, on the canvas too."""
        canvas.shapes.append(ink(strokes[-1][-1], (point.x, point.y)))
        strokes[-1].append((point.x, point.y))

    def handle_pan_start(e: ft.DragStartEvent):
        strokes.append([(e.local_position.x, e.local_position.y)])

    def handle_pan_update(e: ft.DragUpdateEvent):
        draw_to(e.local_position)
        canvas.update()

    def handle_pan_end(e: ft.DragEndEvent):
        draw_to(e.local_position)  # updates are throttled, so the last one may be missing
        show_guess()

    def handle_undo(e: ft.Event[ft.IconButton] | None = None):
        if strokes:
            strokes.pop()
            canvas.shapes = [ink(a, b) for stroke in strokes for a, b in itertools.pairwise(stroke)]
            show_guess()

    def handle_clear(e: ft.Event[ft.IconButton] | None = None):
        strokes.clear()
        canvas.shapes.clear()
        show_guess()

    def handle_keyboard_event(e: ft.KeyboardEvent):
        if e.key == "Backspace":
            handle_undo()
        elif e.key == "Escape":
            handle_clear()

    page.on_keyboard_event = handle_keyboard_event

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                max_width=400,  # fills a phone, stays phone-shaped on wide windows
                expand=True,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text(
                                "SCIKIT-LEARN ON DEVICE",
                                size=13,
                                weight=ft.FontWeight.W_800,
                                color=ACCENT,
                            ),
                            ft.Text("Draw a digit", size=30, weight=ft.FontWeight.W_900, color=INK),
                        ],
                    ),
                    card(
                        ft.Row(
                            spacing=12,
                            controls=[
                                status_icon := ft.Container(
                                    width=40,
                                    height=40,
                                    border_radius=12,
                                    bgcolor=ft.Colors.with_opacity(0.12, ACCENT),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.ProgressRing(
                                        width=20, height=20, stroke_width=2.5, color=ACCENT
                                    ),
                                ),
                                ft.Column(
                                    spacing=1,
                                    expand=True,
                                    controls=[
                                        status := ft.Text(
                                            "Training on scikit-learn's digits…",
                                            size=16,
                                            weight=ft.FontWeight.W_600,
                                            color=INK,
                                        ),
                                        ft.Text(
                                            "An SVC model, right here on this device",
                                            size=13,
                                            color=MUTED,
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ),
                    ft.Container(
                        expand=True,
                        border_radius=22,
                        bgcolor="#FAFAFC",
                        border=ft.Border.all(1.5, "#E3E2EC"),
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        content=ft.Stack(
                            expand=True,
                            controls=[
                                ft.Container(
                                    left=0,
                                    top=0,
                                    right=0,
                                    bottom=0,
                                    alignment=ft.Alignment.CENTER,
                                    content=(
                                        hint := ft.Text(
                                            "Getting ready…",
                                            size=17,
                                            color="#B5B4C2",
                                            weight=ft.FontWeight.W_500,
                                        )
                                    ),
                                ),
                                canvas := cv.Canvas(left=0, top=0, right=0, bottom=0),
                                ft.Row(
                                    right=4,
                                    top=4,
                                    spacing=0,
                                    controls=[
                                        undo_button := ft.IconButton(
                                            ft.Icons.UNDO_ROUNDED,
                                            tooltip="Undo the last stroke (Backspace)",
                                            on_click=handle_undo,
                                        ),
                                        clear_button := ft.IconButton(
                                            ft.Icons.DELETE_OUTLINE_ROUNDED,
                                            tooltip="Clear (Esc)",
                                            on_click=handle_clear,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    ft.Row(
                        height=190,
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            card(
                                expand=True,
                                content=ft.Column(
                                    spacing=0,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        verdict := ft.Text(size=15, weight=ft.FontWeight.W_600),
                                        big := ft.Text(size=80, weight=ft.FontWeight.W_900),
                                        meta := ft.Text(size=13, color=MUTED),
                                    ],
                                ),
                            ),
                            card(
                                ft.Column(
                                    spacing=8,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        caption("What the model sees"),
                                        pixels := ft.GridView(
                                            width=134,
                                            height=134,
                                            runs_count=8,
                                            spacing=2,
                                            run_spacing=2,
                                            controls=[
                                                ft.Container(border_radius=3, bgcolor=UNLIT)
                                                for _ in range(64)
                                            ],
                                        ),
                                    ],
                                )
                            ),
                        ],
                    ),
                    card(
                        ft.Column(
                            spacing=6,
                            controls=[
                                caption("How sure it is, per digit"),
                                bars := ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.END,
                                    controls=[
                                        ft.Container(  # the empty bar, filled from the bottom
                                            width=24,
                                            height=BAR_HEIGHT,
                                            border_radius=6,
                                            bgcolor=UNLIT,
                                            alignment=ft.Alignment.BOTTOM_CENTER,
                                            content=ft.Container(
                                                width=24,
                                                height=0,
                                                border_radius=6,
                                                animate=ft.Animation(
                                                    250, ft.AnimationCurve.EASE_OUT
                                                ),
                                            ),
                                        )
                                        for _ in range(10)
                                    ],
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(
                                            str(digit),
                                            width=24,
                                            text_align=ft.TextAlign.CENTER,
                                            weight=ft.FontWeight.W_700,
                                            color=INK,
                                        )
                                        for digit in range(10)
                                    ],
                                ),
                            ],
                        )
                    ),
                ],
            ),
        )
    )

    show_guess()  # the empty state
    model, count, seconds = await asyncio.to_thread(train)
    status.value = f"Trained on {count:,} digits in {seconds:.2f} s"
    status_icon.content = ft.Icon(ft.Icons.SCHOOL_ROUNDED, color=ACCENT, size=22)
    hint.value = f"Draw a digit here with your {'finger' if page.platform.is_mobile() else 'mouse'}"
    # Drawing starts once the model is ready.
    canvas.content = ft.GestureDetector(
        mouse_cursor=ft.MouseCursor.PRECISE,
        drag_interval=16,  # at most one update every 16 ms, about 60 a second
        on_pan_start=handle_pan_start,
        on_pan_update=handle_pan_update,
        on_pan_end=handle_pan_end,
    )
    page.update()


if __name__ == "__main__":
    ft.run(main)
