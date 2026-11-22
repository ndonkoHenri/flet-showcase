import asyncio
import os
from typing import TYPE_CHECKING

import flet as ft
import numpy as np

if TYPE_CHECKING:  # for type hints only: the app imports it in WaveFigure
    import flet_charts as fch

# On phones, keep matplotlib's font cache in the app's storage, so it is built only once.
if data_dir := os.environ.get("FLET_APP_STORAGE_DATA"):
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(data_dir, "matplotlib"))

INK = "#111827"
MUTED = "#6B7280"
LINE = "#E5E7EB"
ACCENT = "#4F46E5"
LIGHT_ACCENT = "#E0E7FF"
VALUE_STYLE = ft.TextStyle(size=22, weight=ft.FontWeight.W_800, color=ACCENT)
F_MIN, F_MAX, F_START = 0.5, 3.5, 0.5  # frequency, in Hz
FADE_MIN, FADE_MAX, FADE_START = 1.0, 6.0, 3.0  # fade time, in seconds

t = np.linspace(0, 6, 900)


def wave(f: float, fade: float) -> tuple[np.ndarray, np.ndarray]:
    """The envelope e^(-t/fade) and the damped cosine of frequency f inside it."""
    envelope = np.exp(-t / fade)
    return envelope, envelope * np.cos(2 * np.pi * f * t)


class WaveFigure:
    """A matplotlib figure of the damped wave, shown in the app by a MatplotlibChart."""

    def __init__(self):
        # Imported here, once the app shows a status: on a new device, the first matplotlib
        # import builds a font cache, which can take half a minute.
        import flet_charts as fch  # also makes matplotlib draw through flet-charts
        import matplotlib.pyplot as plt

        plt.rcParams.update(
            {"font.size": 14, "axes.titlesize": 17, "xtick.labelsize": 13, "ytick.labelsize": 13}
        )
        self.fig, ax = plt.subplots()
        self.fig.subplots_adjust(left=0.22, right=0.95, top=0.87, bottom=0.14)
        envelope, y = wave(F_START, FADE_START)
        self.upper = ax.plot(t, envelope, "--", color="#9CA3AF", lw=1.6)[0]
        self.lower = ax.plot(t, -envelope, "--", color="#9CA3AF", lw=1.6)[0]
        self.fill = ax.fill_between(t, y, 0, color=ACCENT, alpha=0.14, lw=0)
        self.line = ax.plot(t, y, color=ACCENT, lw=2.6)[0]
        self.label = ax.text(
            0.97,
            0.95,
            "",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=15,
            color=INK,
            bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": LINE},
        )
        ax.set_title(r"$y = e^{-t/\tau}\,\cos(2\pi f\,t)$", pad=12)
        ax.set_xlabel("time (s)")
        ax.set_ylabel("amplitude", labelpad=4)
        ax.set_xlim(0, 6)
        ax.set_ylim(-1.15, 1.15)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.3)
        # The text MatplotlibChart's on_message reports for the point under the pointer.
        ax.format_coord = lambda x, y: f"t = {x:.2f} s    y = {y:.2f}"
        self.chart = fch.MatplotlibChart(figure=self.fig, expand=True)

    def show(self, f: float, fade: float):
        """Put the wave for this frequency and fade time on the figure, and redraw it."""
        envelope, y = wave(f, fade)
        self.line.set_ydata(y)
        self.fill.set_data(t, y, 0)
        self.upper.set_ydata(envelope)
        self.lower.set_ydata(-envelope)
        self.label.set_text(f"f = {f:.2f} Hz,  τ = {fade:.1f} s")
        self.fig.canvas.draw_idle()  # asks MatplotlibChart for a new frame

    def close(self):
        """Let matplotlib forget the figure (a web server keeps running after a visitor leaves)."""
        import matplotlib.pyplot as plt

        plt.close(self.fig)


def setting(name: str, value: ft.Text, slider: ft.Slider) -> ft.Column:
    """A slider with its name on the left and its value on the right."""
    return ft.Column(
        spacing=0,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[ft.Text(name, size=17, weight=ft.FontWeight.W_600, color=INK), value],
            ),
            slider,
        ],
    )


async def main(page: ft.Page):
    page.title = "Damped wave"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed=ACCENT,
        slider_theme=ft.SliderTheme(
            active_track_color=ACCENT,
            inactive_track_color=LIGHT_ACCENT,
            thumb_color=ACCENT,
            padding=ft.Padding.symmetric(horizontal=16, vertical=20),
        ),
    )
    page.bgcolor = ft.Colors.WHITE
    page.padding = 0
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    hint = (
        "Tap zoom, then drag a box"
        if page.platform.is_mobile()
        else "Point at the wave to read it, or zoom in"
    )

    # A loading status first; once the figure is ready, the app fades in to replace it.
    page.add(
        screen := ft.AnimatedSwitcher(
            expand=True,
            duration=400,
            content=ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.ProgressRing(color=ACCENT),
                        ft.Text("Loading matplotlib…", size=17, weight=ft.FontWeight.W_600),
                        ft.Text(
                            "On the first launch it builds its font cache,\n"
                            "which can take half a minute.",
                            color=MUTED,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            ),
        )
    )

    # A thread keeps the status above live; Pyodide (a static website) has no threads.
    figure = WaveFigure() if page.pyodide else await asyncio.to_thread(WaveFigure)
    page.on_close = figure.close

    def show_wave():
        """Redraw the wave for the sliders' values and show those values."""
        figure.show(frequency.value, fade.value)
        frequency_value.value = f"{frequency.value:.2f} Hz"
        fade_value.value = f"{fade.value:.1f} s"
        page.update()

    def handle_zoom_click(e: ft.Event[ft.IconButton] | None = None):
        figure.chart.zoom()  # turns matplotlib's zoom tool on, or off again
        zoom_button.selected = not zoom_button.selected
        readout.value = "Drag a box to zoom in" if zoom_button.selected else hint
        page.update()

    def handle_reset_click(e: ft.Event[ft.IconButton]):
        if zoom_button.selected:
            handle_zoom_click()
        figure.chart.home()
        frequency.value, fade.value = F_START, FADE_START
        show_wave()

    def handle_message(e: "fch.MatplotlibChartMessageEvent"):
        readout.value = e.message or hint
        readout.update()  # the chart's events update only the chart by themselves

    def handle_toolbar_buttons_update(e: "fch.MatplotlibChartToolbarButtonsUpdateEvent"):
        back_button.disabled = not e.back_enabled
        back_button.update()

    figure.chart.on_message = handle_message
    figure.chart.on_toolbar_buttons_update = handle_toolbar_buttons_update

    screen.content = ft.SafeArea(
        expand=True,
        content=ft.Container(
            expand=True,
            max_width=480,  # keeps the phone-like layout in a wide desktop window
            padding=ft.Padding.symmetric(horizontal=20),
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=12),
                        content=ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(
                                    "Damped wave",
                                    size=28,
                                    weight=ft.FontWeight.W_800,
                                    color=INK,
                                ),
                                ft.Text(
                                    "A real matplotlib figure, in a Flet app",
                                    size=15,
                                    color=MUTED,
                                ),
                            ],
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        border_radius=20,
                        border=ft.Border.all(1, LINE),
                        bgcolor=ft.Colors.WHITE,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        padding=4,
                        content=figure.chart,
                    ),
                    ft.Row(
                        spacing=0,
                        controls=[
                            readout := ft.Text(hint, expand=True, size=13, color=MUTED),
                            zoom_button := ft.IconButton(
                                ft.Icons.ZOOM_IN,
                                selected=False,
                                style=ft.ButtonStyle(
                                    bgcolor={ft.ControlState.SELECTED: LIGHT_ACCENT}
                                ),
                                tooltip="Zoom",
                                on_click=handle_zoom_click,
                            ),
                            back_button := ft.IconButton(
                                ft.Icons.UNDO,
                                disabled=True,
                                tooltip="Previous view",
                                on_click=figure.chart.back,
                            ),
                            ft.IconButton(
                                ft.Icons.RESTART_ALT,
                                tooltip="Reset",
                                on_click=handle_reset_click,
                            ),
                        ],
                    ),
                    setting(
                        "Frequency",
                        frequency_value := ft.Text(style=VALUE_STYLE),
                        frequency := ft.Slider(
                            min=F_MIN, max=F_MAX, value=F_START, on_change=show_wave
                        ),
                    ),
                    setting(
                        "Fade time",
                        fade_value := ft.Text(style=VALUE_STYLE),
                        fade := ft.Slider(
                            min=FADE_MIN,
                            max=FADE_MAX,
                            value=FADE_START,
                            divisions=10,
                            on_change=show_wave,
                        ),
                    ),
                ],
            ),
        ),
    )
    screen.update()

    show_wave()


if __name__ == "__main__":
    ft.run(main)
