import asyncio
from dataclasses import dataclass
from pathlib import Path

import cv2
import flet as ft
import numpy as np
import onnxruntime as ort

ASSETS = Path(__file__).parent / "assets"
BACKGROUNDS = [  # (name, color); None keeps the background see-through
    ("yellow", "#FFC940"),
    ("blue", "#4F7DF3"),
    ("pink", "#FF6B8B"),
    ("green", "#3DD68C"),
    ("white", "#FFFFFF"),
    ("see-through", None),
]
CARD_RATIO = 1.1  # the photo card's height / width
# U^2-Net was trained on photos normalized with these (the ImageNet mean and spread).
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
ABOUT_MODEL = "U²-Net small, 4.6 MB, on device"
ACCENT, INK, MUTED, CARD, DARK = "#E00050", "#1B1A22", "#6B6A78", "#F4F3F8", "#0B0A10"


def make_checkerboard(square: int = 10) -> bytes:
    """A gray and white checkerboard tile (PNG), the usual sign of a see-through background."""
    tile = np.full((2 * square, 2 * square, 3), 255, np.uint8)
    tile[:square, :square] = tile[square:, square:] = 222
    return cv2.imencode(".png", tile)[1].tobytes()


CHECKERBOARD = make_checkerboard()


def read_photo(data: bytes, center: float | None = None) -> tuple[np.ndarray, bytes]:
    """A photo's bytes as a cv2 image (at most 1280 px) and as JPEG bytes.

    With `center`, the photo is first cut to the card's shape around that point.
    """
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    if center is not None:
        h, w = img.shape[:2]
        width = min(w, round(h / CARD_RATIO))
        x = min(max(round(center * w - width / 2), 0), w - width)
        img = img[:, x : x + width]
    scale = 1280 / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
    return np.ascontiguousarray(img), jpg


# The sample photos, from Wikimedia Commons (CC0, from Unsplash; credits in the README), as
# (name, cv2 image, JPEG bytes). The number is the middle of the card's crop, across the photo.
SAMPLES = [
    (name, *read_photo((ASSETS / f"{name}.jpg").read_bytes(), center))
    for name, center in [("woman", 0.42), ("dog", 0.74), ("cat", 0.60)]
]
# U^2-Net small ("u2netp", Xuebin Qin et al., Apache-2.0), exported to ONNX by rembg (MIT): see
# assets/u2netp_LICENSE.txt. One session serves every photo, and every visitor of a web app.
MODEL = ort.InferenceSession(str(ASSETS / "u2netp.onnx"), providers=["CPUExecutionProvider"])


def prepare(photo: np.ndarray) -> np.ndarray:
    """The 320x320 RGB input U^2-Net expects: scaled to 0-1, normalized, as 1x3x320x320."""
    small = cv2.resize(photo, (320, 320), interpolation=cv2.INTER_AREA)
    small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype(np.float32)
    small = (small / max(small.max(), 1) - MEAN) / STD
    return small.transpose(2, 0, 1)[None]


def to_alpha(mask: np.ndarray, photo: np.ndarray) -> np.ndarray:
    """The model's 320x320 mask, stretched to 0-1, at the photo's size, as 0-255."""
    m = mask[0, 0]
    m = (m - m.min()) / (m.max() - m.min() + 1e-6)
    h, w = photo.shape[:2]
    return (cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR) * 255).astype(np.uint8)


def cut_out(photo: np.ndarray) -> np.ndarray:
    """The photo with a see-through background (BGRA)."""
    small = prepare(photo)
    mask = MODEL.run(None, {"input.1": small})[0]
    alpha = to_alpha(mask, photo)
    return np.dstack([photo, alpha])


def to_png(rgba: np.ndarray, color: str | None = None, width: int | None = None) -> bytes:
    """A cut-out as PNG bytes: see-through, or flattened onto `color` ("#RRGGBB").
    With `width`, the image is shrunk to that width first (for the small tiles).
    """
    if width:
        height = round(rgba.shape[0] * width / rgba.shape[1])
        rgba = cv2.resize(rgba, (width, height), interpolation=cv2.INTER_AREA)
    if color is not None:
        alpha = rgba[..., 3:] / 255
        bgr = np.array([int(color[k : k + 2], 16) for k in (5, 3, 1)])  # cv2 stores BGR
        rgba = (rgba[..., :3] * alpha + bgr * (1 - alpha)).astype(np.uint8)
    return cv2.imencode(".png", rgba)[1].tobytes()


def paint(box: ft.Container, color: str | None):
    """Give a container the chosen background: a color, or a checkerboard when see-through."""
    box.bgcolor = color
    box.image = (
        None if color else ft.DecorationImage(src=CHECKERBOARD, repeat=ft.ImageRepeat.REPEAT)
    )


def cover(control: ft.Control) -> ft.Control:
    """The control, stretched over the whole Stack it's in."""
    control.left, control.top, control.right, control.bottom = 0, 0, 0, 0
    return control


@dataclass
class Tile:
    """A photo under the card: its name, cv2 image and JPEG bytes, and the tile showing it."""

    box: ft.Container
    backdrop: ft.Container  # the chosen background, behind the cut-out
    cut: ft.Image
    photo: ft.Image  # on top of the cut-out; fades away once the subject is cut out
    name: str
    image: np.ndarray | None = None
    jpg: bytes | None = None


def make_tile(
    index: int,
    on_click: ft.ControlEventHandler[ft.Container],
    sample: tuple[str, np.ndarray, bytes] | None = None,
) -> Tile:
    """A tile for a sample photo, or, without one, the "Your photo" tile."""
    name, image, jpg = sample or ("my-photo", None, None)
    cut = ft.Image(src=jpg or CHECKERBOARD, fit=ft.BoxFit.COVER, gapless_playback=True)
    backdrop = cover(ft.Container(visible=sample is not None, content=cut))
    photo = cover(
        ft.Image(
            src=jpg or CHECKERBOARD,
            fit=ft.BoxFit.COVER,
            visible=sample is not None,
            animate_opacity=ft.Animation(600),
            gapless_playback=True,
        )
    )
    layers = [backdrop, photo]
    if sample is None:  # under the photo, until the user picks one
        layers.insert(
            0,
            cover(
                ft.Container(
                    bgcolor=CARD,
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        controls=[
                            ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, color=ACCENT, size=30),
                            ft.Text(
                                "Your photo", size=13, weight=ft.FontWeight.W_700, color=ACCENT
                            ),
                        ],
                    ),
                )
            ),
        )
    box = ft.Container(
        data=index,
        expand=True,
        height=96,
        border_radius=14,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        border=ft.Border.all(3, ft.Colors.TRANSPARENT),
        on_click=on_click,
        content=ft.Stack(expand=True, controls=layers),
    )
    return Tile(box, backdrop, cut, photo, name, image, jpg)


def make_swatch(
    index: int, color: str | None, on_click: ft.ControlEventHandler[ft.Container]
) -> ft.Container:
    """A round button for one of the backgrounds."""
    swatch = ft.Container(
        data=index,
        width=40,
        height=40,
        shape=ft.BoxShape.CIRCLE,
        border=ft.Border.all(3, ft.Colors.WHITE),
        shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK)),
        animate=ft.Animation(200),
        on_click=on_click,
    )
    paint(swatch, color)
    return swatch


def card_button(
    icon: ft.IconData,
    tooltip: str,
    on_click: ft.ControlEventHandler[ft.IconButton],
    visible: bool = True,
) -> ft.IconButton:
    """A round white button in the photo card's corner."""
    return ft.IconButton(
        icon,
        icon_color=INK,
        bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
        tooltip=tooltip,
        visible=visible,
        on_click=on_click,
    )


async def main(page: ft.Page):
    page.title = "Cut out the background"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    card_width = min(page.width or 400, 500) - 36  # the photo card fits the screen
    card_height = round(card_width * CARD_RATIO)

    # Flet drops a service once nothing refers to it: the click handlers keep these two.
    file_picker = ft.FilePicker()
    share = ft.Share()
    # The share sheet sends the PNG to other apps or saves it to the photos, on phones only.
    can_share = not page.web and page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
    state = {"busy": False, "color": BACKGROUNDS[0][1], "tile": None, "cut_out": None}

    def show_status(icon: ft.IconData, title: str, text: str = ABOUT_MODEL):
        """The status card: an icon, a title and a line under it."""
        status_icon.icon, status.value, detail.value = icon, title, text

    def color_name() -> str:
        """The name of the chosen background."""
        return next(name for name, color in BACKGROUNDS if color == state["color"])

    def show_original(original: bool):
        """Show the original photo on the card, or fade it away to show the cut-out."""
        photo_box.opacity = 1 if original else 0
        badge_text.value = "ORIGINAL" if original else "CUT OUT"
        badge.bgcolor = ft.Colors.with_opacity(0.55, ft.Colors.BLACK) if original else ACCENT

    async def cut(tile: Tile):
        """Show a tile's photo on the card, find its subject, then fade the background away."""
        state["cut_out"] = None
        photo_view.src = tile.jpg
        show_original(True)
        show_status(ft.Icons.AUTO_FIX_HIGH, "Finding the subject...")
        for other in tiles:
            other.box.border = ft.Border.all(3, ACCENT if other is tile else ft.Colors.TRANSPARENT)
        page.update()

        rgba, _ = await asyncio.gather(  # at least 0.7 s: the new photo fades in first
            asyncio.to_thread(cut_out, tile.image), asyncio.sleep(0.7)
        )
        cut_view.src = to_png(rgba)  # under the photo, which hides it for now
        tile.cut.src, tile.backdrop.visible = to_png(rgba, width=240), True
        page.update()
        await asyncio.sleep(0.1)  # let the cut-out load before the photo fades away

        state["tile"], state["cut_out"] = tile, rgba
        show_original(False)
        tile.photo.opacity = 0
        kept = (rgba[..., 3] > 127).mean()
        show_status(
            ft.Icons.CHECK_CIRCLE,
            f"Background → {color_name()}",
            f"Subject kept: {kept:.0%} of the photo",
        )
        page.update()

    async def pick_photo(tile: Tile) -> bool:
        """Let the user pick a photo for the last tile; False when they cancel."""
        files = await file_picker.pick_files(
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True,  # the bytes, on every platform (the web has no paths)
        )
        if not files:
            return False
        try:
            tile.image, tile.jpg = read_photo(files[0].bytes)
        except ValueError:
            show_status(ft.Icons.ERROR_OUTLINE, "Can't read that file", "Try a JPEG or PNG photo")
            page.update()
            return False
        tile.photo.src, tile.photo.visible, tile.photo.opacity = tile.jpg, True, 1
        return True

    async def handle_tile_click(e: ft.Event[ft.Container]):
        if state["busy"]:  # one photo at a time
            return
        state["busy"] = True
        try:
            tile = tiles[e.control.data]
            if tile is not tiles[-1] or await pick_photo(tile):
                await cut(tile)
        finally:
            state["busy"] = False

    def choose_background(index: int):
        """Put the cut-outs on background `index` and mark its swatch."""
        state["color"] = BACKGROUNDS[index][1]
        for i, swatch in enumerate(swatches):
            swatch.border = ft.Border.all(3, ACCENT if i == index else ft.Colors.WHITE)
        for box in [backdrop] + [tile.backdrop for tile in tiles]:
            paint(box, state["color"])
        if state["cut_out"] is not None:
            status.value = f"Background → {color_name()}"
        page.update()

    def handle_swatch_click(e: ft.Event[ft.Container]):
        choose_background(e.control.data)

    def handle_card_click(e: ft.Event[ft.Container]):
        if state["cut_out"] is not None:  # flip between the original and the cut-out
            show_original(photo_box.opacity == 0)
            page.update()

    def file_name() -> str:
        """The name to save or share the shown cut-out as."""
        return f"{state['tile'].name}-cut-out.png"

    async def handle_save_click(e: ft.Event[ft.IconButton]):
        if state["cut_out"] is None:
            return
        name = file_name()
        path = await file_picker.save_file(
            file_name=name, src_bytes=to_png(state["cut_out"], state["color"])
        )
        if page.web:  # the browser downloads it, without asking where
            show_status(ft.Icons.DOWNLOAD_DONE, "Downloaded", name)
        elif path:
            show_status(ft.Icons.DOWNLOAD_DONE, "Saved", name)
        page.update()

    async def handle_share_click(e: ft.Event[ft.IconButton]):
        if state["cut_out"] is None:
            return
        png = to_png(state["cut_out"], state["color"])
        await share.share_files(
            [ft.ShareFile.from_bytes(png, mime_type="image/png", name=file_name())]
        )

    tiles = [make_tile(i, handle_tile_click, sample) for i, sample in enumerate(SAMPLES)]
    tiles.append(make_tile(len(tiles), handle_tile_click))

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                width=card_width,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Container(height=8),
                            ft.Text(
                                "ON-DEVICE AI", size=13, weight=ft.FontWeight.W_800, color=ACCENT
                            ),
                            ft.Text(
                                "Cut out the background",
                                size=26,
                                weight=ft.FontWeight.W_900,
                                color=INK,
                            ),
                        ],
                    ),
                    ft.Container(
                        width=card_width,
                        height=card_height,
                        border_radius=24,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        on_click=handle_card_click,
                        content=(
                            backdrop := ft.Container(  # the new background
                                content=ft.Stack(
                                    controls=[
                                        cut_view := cover(
                                            ft.Image(
                                                src=SAMPLES[0][2],
                                                fit=ft.BoxFit.CONTAIN,
                                                gapless_playback=True,
                                            )
                                        ),
                                        # The photo sits on top of its cut-out, on a dark box for
                                        # photos of another shape: fading it shows the cut-out.
                                        photo_box := cover(
                                            ft.Container(
                                                bgcolor=DARK,
                                                animate_opacity=ft.Animation(600),
                                                content=(
                                                    photo_view := ft.Image(
                                                        src=SAMPLES[0][2],
                                                        fit=ft.BoxFit.CONTAIN,
                                                        gapless_playback=True,
                                                    )
                                                ),
                                            )
                                        ),
                                        badge := ft.Container(
                                            left=12,
                                            top=12,
                                            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                                            border_radius=12,
                                            animate=ft.Animation(300),
                                            content=(
                                                badge_text := ft.Text(
                                                    "ORIGINAL",
                                                    size=13,
                                                    weight=ft.FontWeight.W_800,
                                                    color=ft.Colors.WHITE,
                                                )
                                            ),
                                        ),
                                        ft.Row(
                                            right=8,
                                            top=8,
                                            spacing=6,
                                            controls=[
                                                card_button(
                                                    ft.Icons.IOS_SHARE,
                                                    "Share",
                                                    handle_share_click,
                                                    visible=can_share,
                                                ),
                                                card_button(
                                                    ft.Icons.DOWNLOAD,
                                                    "Save as PNG",
                                                    handle_save_click,
                                                ),
                                            ],
                                        ),
                                    ]
                                )
                            )
                        ),
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=(
                            swatches := [
                                make_swatch(i, color, handle_swatch_click)
                                for i, (_, color) in enumerate(BACKGROUNDS)
                            ]
                        ),
                    ),
                    ft.Container(
                        bgcolor=CARD,
                        border_radius=18,
                        padding=ft.Padding.symmetric(vertical=12, horizontal=16),
                        content=ft.Row(
                            spacing=14,
                            controls=[
                                status_icon := ft.Icon(
                                    ft.Icons.IMAGE_OUTLINED, color=ACCENT, size=28
                                ),
                                ft.Column(
                                    spacing=0,
                                    expand=True,
                                    controls=[
                                        status := ft.Text(
                                            "Ready", size=19, weight=ft.FontWeight.W_800, color=INK
                                        ),
                                        detail := ft.Text(ABOUT_MODEL, size=14, color=MUTED),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    ft.Row(spacing=8, controls=[tile.box for tile in tiles]),
                    ft.Text(
                        "Tap a photo or pick your own. Tap the card to compare.",
                        size=13,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                        width=card_width,
                    ),
                ],
            ),
        )
    )

    choose_background(0)
    state["busy"] = True  # the first photo, while taps wait
    await cut(tiles[0])
    state["busy"] = False


if __name__ == "__main__":
    ft.run(main)
