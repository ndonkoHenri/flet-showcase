import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import flet as ft
import numpy as np

MAX_SIDE = 1200  # bigger photos are shrunk first, so the filters stay quick and look the same
BG, SURFACE, LINE, MUTED, ACCENT = "#0B0B0F", "#17171D", "#26262E", "#9CA3AF", "#F59E0B"


def decode(data: bytes) -> np.ndarray | None:
    """A photo's bytes as OpenCV pixels (BGR), at most MAX_SIDE wide or high; None if unreadable."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    scale = MAX_SIDE / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return img


TIGER = decode((Path(__file__).parent / "assets" / "tiger.jpg").read_bytes())


def pencil(img: np.ndarray) -> np.ndarray:
    """Gray photo divided by its blurred negative: flat areas go white, edges stay as strokes."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(255 - gray, (0, 0), 8)
    sketch = cv2.divide(gray, 255 - blur, scale=256)
    sketch = cv2.multiply(sketch, sketch, scale=1 / 255)  # darker strokes
    return cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)


def cartoon(img: np.ndarray) -> np.ndarray:
    """Smooth colors (edge-preserving), stronger color, few brightness levels, black outlines."""
    small = cv2.resize(img, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    for _ in range(5):
        small = cv2.bilateralFilter(small, 9, 40, 7)
    color = cv2.resize(small, (img.shape[1], img.shape[0]))
    hsv = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)
    hsv[..., 1] = cv2.multiply(hsv[..., 1], 1.6)
    hsv[..., 2] = (hsv[..., 2] // 40) * 40 + 30
    flat = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    gray = cv2.medianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 7)
    lines = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 3)
    return cv2.bitwise_and(flat, flat, mask=lines)


def neon(img: np.ndarray) -> np.ndarray:
    """Canny edges with a soft glow, colored by a NumPy gradient (magenta on top, cyan below)."""
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 60, 140), np.ones((2, 2), np.uint8))
    glow = np.minimum(np.maximum(edges, cv2.GaussianBlur(edges, (0, 0), 3) * 1.2) / 255, 1)
    h, w = edges.shape
    t = np.linspace(0, 1, h)[:, None, None]
    top, bottom = np.array([255, 60, 230]), np.array([255, 230, 40])  # BGR
    gradient = top * (1 - t) + bottom * t
    return (gradient * glow[..., None] * np.ones((1, w, 1))).astype(np.uint8)


SEPIA = np.array([
    [0.131, 0.534, 0.272],  # new blue from B, G, R
    [0.168, 0.686, 0.349],  # new green
    [0.189, 0.769, 0.393],  # new red
])  # fmt: skip


def vintage(img: np.ndarray) -> np.ndarray:
    """Sepia color matrix, then a Gaussian vignette that darkens the corners."""
    sepia = cv2.transform(img.astype(np.float32), SEPIA)
    h, w = img.shape[:2]
    mask = cv2.getGaussianKernel(h, h / 2) @ cv2.getGaussianKernel(w, w / 2).T
    mask = 0.3 + 0.7 * mask / mask.max()
    return np.clip(sepia * mask[..., None], 0, 255).astype(np.uint8)


FILTERS = [  # (name, how it's made, function); the strip shows the name's first word
    ("Original", "cv2.imdecode(photo_bytes)", None),
    ("Pencil sketch", "cv2.divide(gray, blur)", pencil),
    ("Cartoon", "bilateralFilter + threshold", cartoon),
    ("Neon edges", "Canny + NumPy gradient", neon),
    ("Vintage", "sepia matrix + vignette", vintage),
]


def to_jpg(img: np.ndarray, quality: int = 90) -> bytes:
    """OpenCV pixels as JPEG bytes, which an ft.Image shows as they are."""
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


@dataclass
class Photo:
    """A photo through every filter, ready to show."""

    name: str  # the start of the saved file's name
    looks: list[np.ndarray]  # one per filter, the original first
    previews: list[bytes]  # small JPEGs of the looks, for the filter strip


def apply_filters(name: str, img: np.ndarray) -> Photo:
    """Run every filter on the photo once; switching filters later is instant."""
    looks = [img if apply is None else apply(img) for _, _, apply in FILTERS]
    previews = [
        to_jpg(cv2.resize(look, (160, round(160 * look.shape[0] / look.shape[1]))), 85)
        for look in looks
    ]
    return Photo(name, looks, previews)


def render(photo: Photo, index: int, strength: float) -> bytes:
    """Filter `index` mixed over the original (strength 0 to 1), as JPEG bytes."""
    look = photo.looks[index]
    if strength < 1:
        look = cv2.addWeighted(photo.looks[0], 1 - strength, look, strength, 0)
    return to_jpg(look)


def notice(text: str) -> ft.Column:
    """What the photo area shows while the app works."""
    return ft.Column(
        key=text,  # a new key makes the AnimatedSwitcher fade
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=16,
        controls=[
            ft.ProgressRing(color=ACCENT),
            ft.Text(text, size=16, color=MUTED, text_align=ft.TextAlign.CENTER),
        ],
    )


def filter_tile(index: int, on_click: ft.ControlEventHandler[ft.Container]) -> ft.Container:
    """A tile in the filter strip: the filter's name over a small preview of it."""
    return ft.Container(
        data=index,
        expand=True,
        height=72,
        border_radius=14,
        bgcolor=SURFACE,
        border=ft.Border.all(3, ft.Colors.TRANSPARENT),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        on_click=on_click,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.END,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Container(
                    bgcolor="#B3000000",  # dark enough to read on the white pencil sketch
                    padding=ft.Padding.symmetric(vertical=2),
                    content=ft.Text(
                        FILTERS[index][0].split()[0],
                        size=12,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.WHITE,
                        text_align=ft.TextAlign.CENTER,
                        no_wrap=True,
                    ),
                )
            ],
        ),
    )


async def main(page: ft.Page):
    page.title = "Photo filters"
    page.padding = 0
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        color_scheme_seed=ACCENT,
        system_overlay_style=ft.SystemOverlayStyle(
            status_bar_icon_brightness=ft.Brightness.LIGHT, status_bar_brightness=ft.Brightness.DARK
        ),
    )
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    if page.web:  # a browser shows the app, the filters run in the Python server
        runs_on = "on the server"
    elif page.platform.is_mobile():
        runs_on = "on the phone"
    else:  # desktop
        runs_on = "on this computer"

    file_picker = ft.FilePicker()
    shown = {"photo": None, "filter": 0, "jpg": b""}  # what the app shows now

    def show_filter(index: int):
        """Show the photo through a filter, at the slider's strength."""
        name, how, _ = FILTERS[index]
        shown["filter"] = index
        shown["jpg"] = render(shown["photo"], index, strength.value / 100)
        photo_view.content = ft.Image(
            key=f"{shown['photo'].name}-{index}-{strength.value}",
            src=shown["jpg"],
            fit=ft.BoxFit.CONTAIN,
        )
        filter_name.value, filter_how.value = name, how
        strength.disabled = index == 0  # the original has nothing to mix
        for tile in strip.controls:
            tile.border = ft.Border.all(3, ACCENT if tile.data == index else ft.Colors.TRANSPARENT)
        page.update()

    def lock(busy: bool):
        """Lock the controls while the app works; Save needs a photo too."""
        panel.disabled = busy or shown["photo"] is None
        pick_button.disabled = busy
        save_button.disabled = busy or shown["photo"] is None

    async def open_photo(name: str, img: np.ndarray):
        """Run the filters on a new photo in a thread, then show it with the current filter."""
        photo_view.content = notice("Applying filters...")
        lock(True)
        page.update()
        shown["photo"] = await asyncio.to_thread(apply_filters, name, img)  # the UI stays live
        for tile, preview in zip(strip.controls, shown["photo"].previews):
            tile.image = ft.DecorationImage(src=preview, fit=ft.BoxFit.COVER)
        lock(False)
        show_filter(shown["filter"])

    async def handle_tile_click(e: ft.Event[ft.Container]):
        show_filter(e.control.data)

    async def handle_strength_change(e: ft.Event[ft.Slider]):
        strength_text.value = f"{e.control.value:.0f}%"
        page.update()

    async def handle_strength_change_end(e: ft.Event[ft.Slider]):
        show_filter(shown["filter"])  # mixing and encoding once, when the finger lifts

    async def handle_pick_click(e: ft.Event[ft.OutlinedButton]):
        files = await file_picker.pick_files(
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True,  # the bytes, on every platform (the web has no paths)
        )
        if not files:
            return
        img = await asyncio.to_thread(decode, files[0].bytes)
        if img is None:
            page.show_dialog(ft.SnackBar(f"Can't read {files[0].name}: try a JPEG or PNG photo"))
            return
        await open_photo(os.path.splitext(files[0].name)[0], img)

    async def handle_save_click(e: ft.Event[ft.FilledButton]):
        look = FILTERS[shown["filter"]][0].lower().replace(" ", "-")
        saved = await file_picker.save_file(
            file_name=f"{shown['photo'].name}-{look}.jpg",
            src_bytes=shown["jpg"],  # the JPEG on screen, at the slider's strength
        )
        if saved:  # None when canceled, and on the web, where the browser downloads it
            page.show_dialog(ft.SnackBar("Photo saved"))

    async def handle_keyboard_event(e: ft.KeyboardEvent):
        if panel.disabled or e.key not in ("Arrow Left", "Arrow Right"):
            return
        step = 1 if e.key == "Arrow Right" else -1
        show_filter((shown["filter"] + step) % len(FILTERS))

    page.on_keyboard_event = handle_keyboard_event

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                width=460,  # phone-shaped, centered in a wide window
                padding=ft.Padding.only(left=18, right=18, top=8, bottom=10),
                content=ft.Column(
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(
                                    "Photo filters",
                                    size=28,
                                    weight=ft.FontWeight.W_800,
                                    color=ft.Colors.WHITE,
                                ),
                                ft.Text(f"OpenCV + NumPy · {runs_on}", size=15, color=MUTED),
                            ],
                        ),
                        ft.Container(
                            expand=True,
                            border_radius=26,
                            bgcolor=SURFACE,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            content=(
                                photo_view := ft.AnimatedSwitcher(
                                    duration=450,
                                    reverse_duration=300,
                                    transition=ft.AnimatedSwitcherTransition.FADE,
                                    content=notice("Applying filters..."),
                                )
                            ),
                        ),
                        panel := ft.Column(
                            spacing=14,
                            disabled=True,
                            controls=[
                                ft.Container(
                                    bgcolor=SURFACE,
                                    border_radius=20,
                                    border=ft.Border.all(1, LINE),
                                    padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                                    content=ft.Row(
                                        spacing=14,
                                        controls=[
                                            ft.Container(
                                                width=44,
                                                height=44,
                                                border_radius=22,
                                                bgcolor="#2A2116",
                                                alignment=ft.Alignment.CENTER,
                                                content=ft.Icon(
                                                    ft.Icons.AUTO_FIX_HIGH_ROUNDED,
                                                    size=24,
                                                    color=ACCENT,
                                                ),
                                            ),
                                            ft.Column(
                                                spacing=3,
                                                expand=True,
                                                controls=[
                                                    filter_name := ft.Text(
                                                        FILTERS[0][0],
                                                        size=22,
                                                        weight=ft.FontWeight.W_800,
                                                        color=ft.Colors.WHITE,
                                                    ),
                                                    filter_how := ft.Text(
                                                        FILTERS[0][1],
                                                        size=15,
                                                        color=MUTED,
                                                        font_family="monospace",
                                                        font_family_fallback=["Menlo", "Courier"],
                                                        no_wrap=True,
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ),
                                ft.Row(
                                    spacing=0,
                                    controls=[
                                        ft.Text("Strength", size=14, color=MUTED),
                                        strength := ft.Slider(
                                            expand=True,
                                            min=0,
                                            max=100,
                                            value=100,
                                            divisions=20,
                                            label="{value}%",
                                            active_color=ACCENT,
                                            disabled=True,
                                            on_change=handle_strength_change,
                                            on_change_end=handle_strength_change_end,
                                        ),
                                        strength_text := ft.Text(
                                            "100%", size=14, color=MUTED, width=40
                                        ),
                                    ],
                                ),
                                strip := ft.Row(
                                    spacing=8,
                                    controls=[
                                        filter_tile(i, handle_tile_click)
                                        for i in range(len(FILTERS))
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=10,
                            controls=[
                                pick_button := ft.OutlinedButton(
                                    "Pick a photo",
                                    icon=ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,
                                    expand=True,
                                    disabled=True,
                                    on_click=handle_pick_click,
                                ),
                                save_button := ft.FilledButton(
                                    "Save",
                                    icon=ft.Icons.DOWNLOAD,
                                    expand=True,
                                    disabled=True,
                                    on_click=handle_save_click,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        )
    )

    await open_photo("tiger", TIGER)


if __name__ == "__main__":
    ft.run(main)
