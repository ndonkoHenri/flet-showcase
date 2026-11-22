import asyncio
import io
import os
import tempfile
import wave

import flet as ft
import flet_audio as fta
import numpy as np

RATE = 44100  # sound samples per second
BPM, MIN_BPM, MAX_BPM = 100, 60, 180  # the beat's starting tempo, and how slow or fast it goes
BG, CARD, CELL, BEAT_CELL, MUTED = "#0E0E14", "#16161F", "#2A2A36", "#3A3A4A", "#9CA3AF"
rng = np.random.default_rng(7)  # the same noise, so the same drums, on every run


def times(seconds: float) -> np.ndarray:
    """The time of each sample, for a sound that lasts `seconds`."""
    return np.arange(int(RATE * seconds)) / RATE


def hiss(t: np.ndarray) -> np.ndarray:
    """White noise with the low end removed: the sizzle of a cymbal."""
    noise = rng.uniform(-1, 1, len(t))
    return noise - np.convolve(noise, np.ones(8) / 8, mode="same")


def kick() -> np.ndarray:
    """A sine that drops in pitch, then dies away."""
    t = times(0.4)
    pitch = 45 + 110 * np.exp(-30 * t)  # Hz: 155 falls to 45
    return np.sin(2 * np.pi * np.cumsum(pitch) / RATE) * np.exp(-8 * t)


def snare() -> np.ndarray:
    """Random noise plus a tone, cut short."""
    t = times(0.4)
    noise = rng.uniform(-1, 1, len(t))
    return (noise + np.sin(2 * np.pi * 185 * t)) * np.exp(-20 * t)


def clap() -> np.ndarray:
    """Three quick bursts of hiss, then a short tail."""
    t = times(0.3)
    bursts = sum(np.exp(-200 * np.clip(t - d, 0, None)) * (t >= d) for d in (0, 0.011, 0.022))
    return hiss(t) * (bursts + 0.5 * np.exp(-25 * t))


def hi_hat(seconds: float, fade: float) -> np.ndarray:
    """A hiss that fades: short for a closed hat, long for an open one."""
    t = times(seconds)
    return hiss(t) * np.exp(-fade * t)


def tom() -> np.ndarray:
    """A low sine that drops a little in pitch."""
    t = times(0.45)
    pitch = 95 + 40 * np.exp(-12 * t)
    return np.sin(2 * np.pi * np.cumsum(pitch) / RATE) * np.exp(-7 * t)


def rim() -> np.ndarray:
    """A high tone and some hiss, gone in a flash: a click."""
    t = times(0.08)
    return (np.sin(2 * np.pi * 1700 * t) + 0.6 * hiss(t)) * np.exp(-90 * t)


def cowbell() -> np.ndarray:
    """Two tones that don't quite fit together, with an overtone each."""
    t = times(0.35)
    tone = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(6 * np.pi * f * t) for f in (540, 800))
    return tone * np.exp(-12 * t)


def to_wav(samples: np.ndarray, peak: float) -> bytes:
    """16-bit mono WAV bytes in memory, loudest sample at `peak`, with 3 ms fades so nothing clicks."""
    i = np.arange(len(samples))
    fades = np.minimum(1, np.minimum(i + 1, i[::-1]) / (RATE * 0.003))
    pcm = samples * fades / np.abs(samples).max() * peak * 32767
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.astype(np.int16).tobytes())
    return buffer.getvalue()


# The eight pads: color, how Python makes the sound, and the sound as WAV bytes, made once for
# every session. Hats, claps and bells sound louder than kicks, so their loudest sample is lower.
PADS = {
    "Kick": ("#EF4444", "a falling sine", to_wav(kick(), peak=0.4)),
    "Snare": ("#F97316", "noise + a tone", to_wav(snare(), peak=0.32)),
    "Clap": ("#EAB308", "three noise bursts", to_wav(clap(), peak=0.26)),
    "Hi-hat": ("#22C55E", "a short hiss", to_wav(hi_hat(0.1, fade=55), peak=0.15)),
    "Open hat": ("#14B8A6", "a long hiss", to_wav(hi_hat(0.45, fade=9), peak=0.15)),
    "Tom": ("#3B82F6", "a low sine", to_wav(tom(), peak=0.4)),
    "Rim": ("#8B5CF6", "a click", to_wav(rim(), peak=0.22)),
    "Cowbell": ("#EC4899", "two tones", to_wav(cowbell(), peak=0.2)),
}
PAD_FOR_KEY = {str(i): name for i, name in enumerate(PADS, start=1)}  # keys 1 to 8 play the pads
KEY_FOR_PAD = {name: key for key, name in PAD_FOR_KEY.items()}
PATTERN = {  # the beat: 16 eighth-note steps = 2 bars; "x" = hit
    "Kick": "x..xx...x..xx...",
    "Snare": "..x...x...x...x.",
    "Clap": "......x.......x.",
    "Hi-hat": "xxxxxxx.xxxxxx..",
    "Open hat": ".......x.......x",
    "Tom": ".............x.x",
    "Rim": ".....x...x......",
    "Cowbell": "....x.......x...",
}
STEPS = len(PATTERN["Kick"])


def drum_pad(
    name: str, show_key: bool, on_tap_down: ft.EventHandler[ft.TapEvent[ft.Container]]
) -> ft.Container:
    """A pad in its color, with its name, how its sound is made and, if asked, its computer key."""
    color, how, _ = PADS[name]
    return ft.Container(
        data=name,
        expand=True,
        border_radius=22,
        bgcolor=ft.Colors.with_opacity(0.16, color),
        border=ft.Border.all(2, color),
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        alignment=ft.Alignment.TOP_LEFT,
        animate=ft.Animation(110, ft.AnimationCurve.EASE_OUT),  # the flash
        animate_scale=ft.Animation(110, ft.AnimationCurve.EASE_OUT),  # the press
        on_tap_down=on_tap_down,  # on touch, not on release, like a real pad
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    KEY_FOR_PAD[name],
                    size=15,
                    weight=ft.FontWeight.W_700,
                    color=color,
                    visible=show_key,
                ),
                ft.Container(expand=True),
                ft.Text(name, size=22, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                ft.Text(how, size=14, color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE)),
            ],
        ),
    )


def main(page: ft.Page):
    page.title = "Drum pad"
    page.padding = ft.Padding.symmetric(horizontal=16)
    page.bgcolor = BG
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.DARK
    page.dark_theme = ft.Theme(
        color_scheme=ft.ColorScheme(primary=ft.Colors.WHITE, on_primary=BG),  # white buttons
        system_overlay_style=ft.SystemOverlayStyle(  # light status bar icons on phones
            status_bar_icon_brightness=ft.Brightness.LIGHT, status_bar_brightness=ft.Brightness.DARK
        ),
    )
    phone = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)

    def playable(name: str, wav: bytes) -> bytes | str:
        """In-memory WAV bytes, or a .wav file on iOS and macOS, which can't play bytes yet."""
        if page.web or page.platform not in (ft.PagePlatform.IOS, ft.PagePlatform.MACOS):
            return wav
        path = os.path.join(tempfile.gettempdir(), f"drum-pad-{name.replace(' ', '-')}.wav")
        with open(path, "wb") as f:
            f.write(wav)
        return path

    # One player per pad. release_mode=STOP keeps each sound loaded,
    # so a pad plays again at once, even while it still rings.
    sounds = {
        name: fta.Audio(src=playable(name, wav), release_mode=fta.ReleaseMode.STOP)
        for name, (_, _, wav) in PADS.items()
    }
    lit = dict.fromkeys(PADS, 0)  # how many hits light each pad right now
    beat = {"task": None, "bpm": BPM}  # the beat playing now, and its tempo

    async def flash(name: str):
        """Light up and shrink a pad for a moment, then let it go."""
        pad, color = pads[name], PADS[name][0]
        lit[name] += 1
        pad.bgcolor, pad.scale = color, 0.93
        pad.update()
        await asyncio.sleep(0.12)
        lit[name] -= 1
        if not lit[name]:  # not hit again meanwhile
            pad.bgcolor, pad.scale = ft.Colors.with_opacity(0.16, color), 1
            pad.update()

    def hit(name: str):
        """Sound a pad and flash it, for the user or for the beat."""
        page.run_task(sounds[name].play)
        page.run_task(flash, name)

    def show_step(step: int | None):
        """Light the step playing now and show its bar, or show the row at rest."""
        # Every 4th step is lighter, so a bar reads in halves.
        for i, cell in enumerate(steps.controls):
            cell.bgcolor = ft.Colors.WHITE if i == step else BEAT_CELL if i % 4 == 0 else CELL
        bar_text.value = "2 BARS, 16 STEPS" if step is None else f"BAR {step // 8 + 1} / 2"

    async def play_beat():
        """Play the pattern on a loop, a step every eighth note, until Stop."""
        beat_button.content, beat_button.icon = "Stop", ft.Icons.STOP_ROUNDED
        page.update()
        try:
            # Keep time on the loop clock: each step starts on time, however long updates take.
            loop = asyncio.get_running_loop()
            next_time, step = loop.time(), 0
            while True:
                await asyncio.sleep(max(0, next_time - loop.time()))
                show_step(step)
                for name, hits in PATTERN.items():
                    if hits[step] == "x":
                        hit(name)
                page.update()
                next_time += 60 / beat["bpm"] / 2  # an eighth note at the tempo set now
                step = (step + 1) % STEPS
        finally:  # when Stop cancels the beat
            beat["task"] = None
            show_step(None)
            beat_button.content, beat_button.icon = "Play beat", ft.Icons.PLAY_ARROW_ROUNDED
            page.update()

    def stop_beat():
        """Stop the beat, if it plays."""
        if beat["task"]:
            beat["task"].cancel()

    def toggle_beat():
        """Start the beat, or stop it if it plays."""
        if beat["task"]:
            stop_beat()
        else:
            beat["task"] = page.run_task(play_beat)

    def change_tempo(by: int):
        """Make the beat faster or slower, within its range, even while it plays."""
        beat["bpm"] = min(max(MIN_BPM, beat["bpm"] + by), MAX_BPM)
        bpm_text.value = f"{beat['bpm']} BPM"
        slower_button.disabled = beat["bpm"] == MIN_BPM
        faster_button.disabled = beat["bpm"] == MAX_BPM
        page.update()

    def handle_pad_tap_down(e: ft.TapEvent[ft.Container]):
        hit(e.control.data)

    def handle_keyboard_event(e: ft.KeyboardEvent):
        if e.ctrl or e.alt or e.meta:  # leave shortcuts alone
            return
        if e.key in PAD_FOR_KEY:
            hit(PAD_FOR_KEY[e.key])
        elif e.key == " ":
            toggle_beat()

    pads = {
        name: drum_pad(name, show_key=not phone, on_tap_down=handle_pad_tap_down) for name in PADS
    }
    names = list(PADS)

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                max_width=420,  # phone-shaped, centered on wide windows
                expand=True,
                spacing=12,
                controls=[
                    ft.Column(
                        spacing=2,
                        margin=ft.Margin.only(top=8),
                        controls=[
                            ft.Text(
                                "Drum pad",
                                size=28,
                                weight=ft.FontWeight.W_800,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                "Tap the pads: every hit is made by Python"
                                if phone
                                else "Click the pads, or press 1 to 8 (Space plays the beat)",
                                size=15,
                                color=MUTED,
                            ),
                        ],
                    ),
                    ft.Container(
                        bgcolor=CARD,
                        border_radius=14,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        content=ft.Column(
                            spacing=8,
                            controls=[
                                bar_text := ft.Text(
                                    size=13, weight=ft.FontWeight.W_700, color=MUTED
                                ),
                                steps := ft.Row(
                                    [
                                        ft.Container(
                                            expand=True,
                                            height=16,
                                            border_radius=5,
                                            animate=ft.Animation(80),
                                        )
                                        for _ in range(STEPS)
                                    ],
                                    spacing=4,
                                ),
                            ],
                        ),
                    ),
                    ft.Column(
                        expand=True,
                        spacing=12,
                        controls=[
                            ft.Row(expand=True, spacing=12, controls=[pads[a], pads[b]])
                            for a, b in zip(names[::2], names[1::2])
                        ],
                    ),
                    ft.Row(
                        margin=ft.Margin.only(bottom=12),
                        controls=[
                            beat_button := ft.FilledButton(
                                "Play beat",
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                height=48,
                                expand=True,
                                on_click=toggle_beat,
                            ),
                            ft.Container(
                                bgcolor="#1F1F2B",
                                border_radius=999,
                                content=ft.Row(
                                    spacing=0,
                                    controls=[
                                        slower_button := ft.IconButton(
                                            ft.Icons.REMOVE_ROUNDED,
                                            on_click=lambda: change_tempo(-5),
                                        ),
                                        bpm_text := ft.Text(
                                            f"{BPM} BPM",
                                            size=16,
                                            weight=ft.FontWeight.W_800,
                                            color=ft.Colors.WHITE,
                                        ),
                                        faster_button := ft.IconButton(
                                            ft.Icons.ADD_ROUNDED, on_click=lambda: change_tempo(5)
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        )
    )

    show_step(None)  # the row at rest
    page.update()

    # The page hears every key press, wherever the focus is (desktop, web, a tablet's keyboard).
    page.on_keyboard_event = handle_keyboard_event
    # A closed browser tab or app window ends the beat, so its loop doesn't play on for no one.
    page.on_disconnect = page.on_close = lambda e: stop_beat()


if __name__ == "__main__":
    ft.run(main)
