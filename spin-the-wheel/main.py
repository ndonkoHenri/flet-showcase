import asyncio
import io
import math
import os
import random
import tempfile
import wave

import flet as ft
import flet.canvas as cv
import flet_audio as fta
import numpy as np

NAMES = ["Ana", "Ben", "Chloe", "Dev", "Emma", "Femi", "Gus", "Hana"]
COLORS = ["#EF4444", "#F59E0B", "#10B981", "#3B82F6", "#8B5CF6", "#EC4899", "#14B8A6"]
COLORS += ["#F97316", "#0EA5E9", "#84CC16", "#E11D48", "#A855F7"]  # one per name, 12 at most
SIZE = 340  # the wheel's diameter
SPIN_SECONDS = 5
RATE = 44100  # sound samples per second
INK, MUTED, COFFEE = "#111827", "#6B7280", "#6F4E37"


def wav_bytes(samples: np.ndarray) -> bytes:
    """NumPy samples between -1 and 1, as the bytes of a WAV file in memory."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)  # 16-bit
        f.setframerate(RATE)
        f.writeframes((samples * 26000).astype(np.int16).tobytes())
    return buffer.getvalue()


def sound(seconds: float, fade: float, *notes: tuple[float, float]) -> bytes:
    """WAV bytes of sine waves, (pitch in Hz, loudness) each, fading out over the sound."""
    t = np.linspace(0, seconds, int(RATE * seconds))
    mix = sum(level * np.sin(2 * np.pi * pitch * t) for pitch, level in notes)
    return wav_bytes(mix / sum(level for _, level in notes) * np.exp(-fade * t))


# Sounds, created once for every session.
CLICK = sound(0.03, 150, (2000, 1))  # 30 ms, each time a slice passes the pointer
CHIME = sound(0.9, 5, (1319, 1), (1976, 0.6))  # two tones when the wheel stops


def wheel_shapes(names: list[str]) -> list[cv.Shape]:
    """One colored slice per name, with the name written along it."""
    r, step = SIZE / 2, 2 * math.pi / len(names)
    shapes = []
    for i, name in enumerate(names):
        start = -math.pi / 2 + i * step  # the first slice starts at the top
        middle = start + step / 2
        slice_paint = ft.Paint(color=COLORS[i])
        edge_paint = ft.Paint(color="white", stroke_width=3, style=ft.PaintingStyle.STROKE)
        for paint in (slice_paint, edge_paint):
            shapes.append(
                cv.Arc(
                    x=0,
                    y=0,
                    width=SIZE,
                    height=SIZE,
                    start_angle=start,
                    sweep_angle=step,
                    use_center=True,
                    paint=paint,
                )
            )
        shapes.append(
            cv.Text(
                x=r + 0.64 * r * math.cos(middle),
                y=r + 0.64 * r * math.sin(middle),
                value=name,
                alignment=ft.Alignment.CENTER,
                rotate=middle,
                style=ft.TextStyle(size=20, weight=ft.FontWeight.W_800, color="white"),
            )
        )
    rim = ft.Paint(color=INK, stroke_width=5, style=ft.PaintingStyle.STROKE)
    shapes.append(cv.Circle(x=r, y=r, radius=r - 2, paint=rim))
    return shapes


def main(page: ft.Page):
    page.title = "Coffee wheel"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme = ft.Theme(color_scheme_seed=COFFEE)
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    names = list(NAMES)

    def playable(name: str, wav: bytes) -> bytes | str:
        """In-memory WAV bytes, or a .wav file on iOS and macOS, which can't play bytes yet."""
        if page.web or page.platform not in (ft.PagePlatform.IOS, ft.PagePlatform.MACOS):
            return wav
        path = os.path.join(tempfile.gettempdir(), f"coffee-wheel-{name}.wav")
        with open(path, "wb") as f:
            f.write(wav)
        return path

    # release_mode=STOP keeps a sound loaded, so every replay starts at once.
    tick = fta.Audio(src=playable("tick", CLICK), release_mode=fta.ReleaseMode.STOP)
    ding = fta.Audio(src=playable("ding", CHIME), release_mode=fta.ReleaseMode.STOP)

    def show_names():
        """Redraw the wheel and the name chips, and send the change to the screen."""
        wheel.content.shapes = wheel_shapes(names)
        chips.controls = [
            ft.Chip(
                label=name,
                data=name,
                bgcolor=COLORS[i],
                label_text_style=ft.TextStyle(color="white", weight=ft.FontWeight.W_700),
                delete_icon_color="white",
                # A wheel needs two names: hide the delete buttons then.
                on_delete=handle_remove if len(names) > 2 else None,
            )
            for i, name in enumerate(names)
        ]
        page.update()

    def handle_add(e: ft.Event[ft.TextField] | ft.Event[ft.IconButton]):
        name = new_name.value.strip()[:10]  # longer names overflow the slice
        new_name.value = ""
        if name and name not in names and len(names) < len(COLORS) and not spin_button.disabled:
            names.append(name)
        show_names()

    def handle_remove(e: ft.Event[ft.Chip]):
        if spin_button.disabled:  # the names stay put while the wheel turns
            return
        names.remove(e.control.data)
        show_names()

    async def play_ticks(start: float, end: float, step: float):
        """A click each time a slice edge passes the pointer, timed from the curve."""
        loop = asyncio.get_running_loop()
        began = loop.time()
        for edge in range(math.floor(start / step) + 1, math.floor(end / step) + 1):
            done = (edge * step - start) / (end - start)  # share of the whole turn
            at = SPIN_SECONDS * (1 - math.sqrt(1 - done))  # DECELERATE: 1 - (1 - t)²
            await asyncio.sleep(at - (loop.time() - began))
            page.run_task(tick.play)
            pointer.rotate = ft.Rotate(-0.35, alignment=ft.Alignment.TOP_CENTER)  # flick
            pointer.update()
            await asyncio.sleep(0.05)
            pointer.rotate = ft.Rotate(0, alignment=ft.Alignment.TOP_CENTER)
            pointer.update()
        await asyncio.sleep(SPIN_SECONDS - (loop.time() - began))

    async def handle_spin(e: ft.Event[ft.FilledButton]):
        spin_button.disabled = True
        banner.scale = 0
        page.update()
        step = 2 * math.pi / len(names)
        winner = random.randrange(len(names))
        # The wheel angle that puts the winner's slice under the pointer.
        target = -(winner + random.uniform(0.25, 0.75)) * step
        start = wheel.rotate
        wheel.rotate += 5 * 2 * math.pi + (target - start) % (2 * math.pi)  # 5 turns+
        wheel.update()
        await play_ticks(start, wheel.rotate, step)
        page.run_task(ding.play)
        result.value = f"{names[winner]} pays for coffee!"
        banner.scale = 1
        history.controls.append(
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=14,
                bgcolor=COLORS[winner],
                content=ft.Text(names[winner], weight=ft.FontWeight.W_700, color="white"),
            )
        )
        spin_button.disabled = False
        page.update()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                width=380,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(
                                "Who pays for coffee?",
                                size=28,
                                weight=ft.FontWeight.W_800,
                                color=INK,
                            ),
                            ft.Text("Spin the wheel, no arguing", size=16, color=MUTED),
                        ],
                    ),
                    ft.Stack(
                        width=360,
                        height=26 + SIZE,
                        controls=[
                            wheel := ft.Container(
                                left=10,
                                top=26,
                                rotate=0,
                                animate_rotation=ft.Animation(
                                    SPIN_SECONDS * 1000, ft.AnimationCurve.DECELERATE
                                ),
                                content=cv.Canvas(
                                    width=SIZE, height=SIZE, shapes=wheel_shapes(names)
                                ),
                            ),
                            ft.Container(  # the hub
                                left=180 - 36,
                                top=26 + SIZE / 2 - 36,
                                width=72,
                                height=72,
                                border_radius=36,
                                bgcolor="white",
                                border=ft.Border.all(5, INK),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.COFFEE_ROUNDED, size=34, color=COFFEE),
                            ),
                            pointer := ft.Container(
                                left=180 - 22,
                                top=0,
                                rotate=ft.Rotate(0, alignment=ft.Alignment.TOP_CENTER),
                                animate_rotation=60,
                                content=cv.Canvas(
                                    width=44,
                                    height=52,
                                    shapes=[
                                        cv.Path(
                                            elements=[
                                                cv.Path.MoveTo(0, 0),
                                                cv.Path.LineTo(44, 0),
                                                cv.Path.LineTo(22, 52),
                                                cv.Path.Close(),
                                            ],
                                            paint=ft.Paint(color=INK),
                                        )
                                    ],
                                ),
                            ),
                        ],
                    ),
                    banner := ft.Container(
                        height=72,
                        border_radius=20,
                        bgcolor="#FEF3C7",
                        alignment=ft.Alignment.CENTER,
                        animate_scale=ft.Animation(450, ft.AnimationCurve.EASE_OUT_BACK),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.COFFEE_ROUNDED, color="#92400E"),
                                result := ft.Text(
                                    "Spin to pick who pays",
                                    size=22,
                                    weight=ft.FontWeight.W_800,
                                    color=INK,
                                ),
                            ],
                        ),
                    ),
                    ft.Row(
                        controls=[
                            spin_button := ft.FilledButton(
                                "Spin",
                                icon=ft.Icons.REFRESH_ROUNDED,
                                height=56,
                                expand=True,
                                on_click=handle_spin,
                                style=ft.ButtonStyle(
                                    text_style=ft.TextStyle(size=20, weight=ft.FontWeight.W_800)
                                ),
                            )
                        ]
                    ),
                    ft.Container(  # a fixed height: the first name doesn't push the rest down
                        height=32,
                        content=ft.Row(
                            controls=[
                                ft.Text("Paid before:", color=MUTED),
                                history := ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO),
                            ]
                        ),
                    ),
                    ft.Text("On the wheel", weight=ft.FontWeight.W_700, color=INK),
                    chips := ft.Row(spacing=6, run_spacing=6, wrap=True),
                    ft.Row(
                        controls=[
                            new_name := ft.TextField(
                                hint_text="Add a name",
                                dense=True,
                                expand=True,
                                on_submit=handle_add,
                            ),
                            ft.IconButton(ft.Icons.ADD_CIRCLE, on_click=handle_add),
                        ]
                    ),
                ],
            ),
        )
    )

    show_names()  # the name chips


if __name__ == "__main__":
    ft.run(main)
