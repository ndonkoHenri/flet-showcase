import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import flet as ft
import numpy as np

ASSETS = Path(__file__).parent / "assets"
# YuNet, OpenCV Zoo's face detector: a 227 KB ONNX model (MIT, see assets/), shipped with the app.
MODEL = str(ASSETS / "face_detection_yunet_2023mar.onnx")
SAMPLES = [  # (file in assets/, caption): NASA crew portraits, public domain
    ("crew-9.jpg", "Crew-9 aboard Dragon, 2025"),
    ("sts-70.jpg", "STS-70 crew, 1995"),
    ("expedition-75.jpg", "Expedition 75 crew, 2024"),
]
SURE = 0.8  # a face counts when YuNet is at least this sure (0 to 1)
MAX_SIDE = 1280  # bigger photos are shrunk first: faster, and still sharper than the screen
ACCENT, INK, MUTED, CARD, DARK = "#E00050", "#1B1A22", "#6B6A78", "#F4F3F8", "#0B0A10"
BOX = "#2BFF88"  # the boxes and dots on the faces


@dataclass
class Photo:
    """A photo to look at, and its faces once YuNet has found them."""

    pixels: np.ndarray  # what OpenCV reads (BGR)
    jpg: bytes  # what the app shows
    caption: str
    faces: list[list[float]] | None = None  # x, y, w, h, 5 landmarks (x, y), score
    ms: float = 0  # how long finding them took


def decode(data: bytes) -> tuple[np.ndarray, bytes]:
    """A photo's bytes as OpenCV pixels (at most MAX_SIDE wide or high) and as JPEG bytes."""
    pixels = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if pixels is None:
        raise ValueError("not an image")
    scale = MAX_SIDE / max(pixels.shape[:2])
    if scale < 1:
        pixels = cv2.resize(pixels, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return pixels, to_jpg(pixels)


def to_jpg(pixels: np.ndarray) -> bytes:
    """OpenCV pixels as JPEG bytes, which an Image shows as they are."""
    return cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()


SAMPLE_PHOTOS = [(*decode((ASSETS / name).read_bytes()), caption) for name, caption in SAMPLES]


def find_faces(detector: cv2.FaceDetectorYN, pixels: np.ndarray) -> tuple[list[list[float]], float]:
    """Every face in the photo, and the milliseconds it took."""
    h, w = pixels.shape[:2]
    detector.setInputSize((w, h))  # YuNet reads the photo at its own size
    start = time.perf_counter()
    _, faces = detector.detect(pixels)  # None when there are no faces
    ms = (time.perf_counter() - start) * 1000
    return ([] if faces is None else faces.tolist()), ms


def blur_faces(photo: Photo) -> bytes:
    """The photo as JPEG bytes, with every face blurred beyond recognition."""
    pixels = photo.pixels.copy()
    h, w = pixels.shape[:2]
    for x, y, fw, fh, *_ in photo.faces:
        pad = fh * 0.15  # a little past the box: hair and chin too
        x0, y0 = max(int(x - pad), 0), max(int(y - pad), 0)
        x1, y1 = min(int(x + fw + pad), w), min(int(y + fh + pad), h)
        if x1 > x0 and y1 > y0:
            pixels[y0:y1, x0:x1] = cv2.GaussianBlur(pixels[y0:y1, x0:x1], (0, 0), fh / 5)
    return to_jpg(pixels)


def face_marks(photo: Photo, width: float, height: float, hidden: bool) -> list[ft.Container]:
    """A green box and 5 dots per face, placed over the photo shown fitted in width x height.

    Hidden marks start big and transparent, so they pop in once shown.
    """
    ih, iw = photo.pixels.shape[:2]
    s = min(width / iw, height / ih)  # the photo is shown fitted in the card, centered
    ox, oy = (width - iw * s) / 2, (height - ih * s) / 2
    marks = []
    for face in photo.faces:
        x, y, w, h = (v * s for v in face[:4])
        marks.append(
            ft.Container(
                left=x + ox,
                top=y + oy,
                width=w,
                height=h,
                border_radius=6,
                border=ft.Border.all(2.5, BOX),
            )
        )
        for k in range(5):  # eyes, nose tip and mouth corners
            px, py = face[4 + 2 * k] * s + ox, face[5 + 2 * k] * s + oy
            marks.append(
                ft.Container(
                    left=px - 2, top=py - 2, width=4, height=4, border_radius=2, bgcolor=BOX
                )
            )
    for mark in marks:
        mark.scale, mark.opacity = (1.6, 0) if hidden else (1, 1)
        mark.animate_scale = ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_OUT_BACK)
        mark.animate_opacity = ft.Animation(duration=200)
    return marks


def faces_text(count: int) -> str:
    """The count in words: "1 face", "4 faces" or "No faces"."""
    return "No faces" if count == 0 else f"{count} face{'' if count == 1 else 's'}"


@dataclass
class Tile:
    """A thumbnail under the card, with a pill showing its face count."""

    frame: ft.Container  # outlined while its photo is the one shown
    layers: ft.Stack  # the picture, then the pill
    pill: ft.Container
    count: ft.Text
    photo: Photo | None  # None until the user picks one for the "Your photo" tile


def thumbnail(jpg: bytes) -> ft.Image:
    """A photo filling its tile."""
    return ft.Image(src=jpg, fit=ft.BoxFit.COVER)


def pick_prompt() -> ft.Column:
    """What the "Your photo" tile shows until the user picks a photo."""
    return ft.Column(
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=2,
        controls=[
            ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, color=ACCENT, size=28),
            ft.Text("Your photo", size=12, weight=ft.FontWeight.W_700, color=ACCENT),
        ],
    )


def make_tile(
    photo: Photo | None,
    on_click: ft.ControlEventHandler[ft.Container] | None = None,
    action: ft.PickFiles | None = None,
) -> Tile:
    """A tile for a sample photo, or, without a photo, the "Your photo" tile."""
    frame = ft.Container(
        expand=True,
        height=84,
        border_radius=14,
        bgcolor=CARD,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        border=ft.Border.all(3, ft.Colors.TRANSPARENT),
        on_click=on_click,
        action=action,
        content=(
            layers := ft.Stack(
                fit=ft.StackFit.EXPAND,  # the picture fills the tile
                controls=[
                    thumbnail(photo.jpg) if photo else pick_prompt(),
                    pill := ft.Container(
                        right=6,
                        bottom=6,
                        visible=False,
                        padding=ft.Padding.symmetric(vertical=2, horizontal=9),
                        border_radius=10,
                        bgcolor=ACCENT,
                        content=(
                            count := ft.Text(
                                "", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE
                            )
                        ),
                    ),
                ],
            )
        ),
    )
    tile = Tile(frame, layers, pill, count, photo)
    frame.data = tile  # a tap on the frame finds its tile
    return tile


async def main(page: ft.Page):
    page.title = "Face detection"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    if not page.web and page.platform in (
        ft.PagePlatform.MACOS,
        ft.PagePlatform.WINDOWS,
        ft.PagePlatform.LINUX,
    ):
        page.window.width, page.window.height = 430, 860  # phone-shaped

    # One detector per visitor: a web server shares this file's globals between browser tabs,
    # and detect() changes the detector's input size.
    detector = cv2.FaceDetectorYN.create(MODEL, "", (320, 320), SURE)
    shown = None  # the Photo on the card
    finding = asyncio.Lock()  # one photo at a time

    def card_size() -> tuple[float, float]:
        """The photo card's size: the page's width, up to a phone's, by 4:5."""
        width = min(page.width or 400, 480) - 32
        return width, round(width * 0.8)

    def show_picture():
        """Show the card's photo, its faces blurred when the switch is on."""
        if blur_switch.value and shown.faces:
            picture.src = blur_faces(shown)
        else:
            picture.src = shown.jpg
        page.update()

    async def look_at(tile: Tile):
        """Show a tile's photo, find its faces (once), then pop in a box around each one."""
        nonlocal shown
        shown = photo = tile.photo
        for t in tiles:
            t.frame.border = ft.Border.all(3, ACCENT if t is tile else ft.Colors.TRANSPARENT)
        overlay.controls.clear()
        caption.value = photo.caption
        count.value, count.color = "…", MUTED
        details.value = "Looking for faces"
        show_picture()

        if photo.faces is None:
            photo.faces, photo.ms = await asyncio.to_thread(find_faces, detector, photo.pixels)
        overlay.controls = face_marks(photo, *card_size(), hidden=True)
        show_picture()
        await asyncio.sleep(0.05)  # the marks are drawn hidden first, so they can animate in
        for mark in overlay.controls:
            mark.scale, mark.opacity = 1, 1
        count.value, count.color = faces_text(len(photo.faces)), INK
        details.value = f"found in {photo.ms:.0f} ms"
        tile.count.value, tile.pill.visible = str(len(photo.faces)), True
        page.update()

    async def handle_tile_click(e: ft.Event[ft.Container]):
        if not finding.locked():  # a tap while YuNet works is ignored
            async with finding:
                await look_at(e.control.data)

    async def handle_pick_result(e: ft.FilePickerResultEvent):
        if not e.files:  # canceled
            return
        async with finding:
            try:
                pixels, jpg = await asyncio.to_thread(decode, e.files[0].bytes)
            except ValueError:
                page.show_dialog(ft.SnackBar(f"Can't read {e.files[0].name}: try a JPEG or PNG"))
                return
            your_tile.photo = Photo(pixels, jpg, "Your photo")
            your_tile.layers.controls[0] = thumbnail(jpg)
            await look_at(your_tile)

    def handle_resize(e: ft.PageResizeEvent):
        width, height = card_size()
        column.width, card.width, card.height = width, width, height
        if shown and shown.faces is not None:  # keep the boxes on the faces
            overlay.controls = face_marks(shown, width, height, hidden=False)
        page.update()

    # Flet drops a service once nothing refers to it: the "Your photo" tile's action keeps it.
    file_picker = ft.FilePicker(on_result=handle_pick_result)
    tiles = [
        make_tile(Photo(pixels, jpg, caption), on_click=handle_tile_click)
        for pixels, jpg, caption in SAMPLE_PHOTOS
    ]
    your_tile = make_tile(
        None,
        # The client opens the picker right in the tap: browsers (iOS Safari above all)
        # open one only while they handle the click. The picked file comes to on_result.
        action=ft.PickFiles(file_picker, file_type=ft.FilePickerFileType.IMAGE, with_data=True),
    )
    tiles.append(your_tile)
    page.on_resize = handle_resize
    width, height = card_size()

    page.add(
        ft.SafeArea(
            expand=True,
            content=(
                column := ft.Column(
                    width=width,
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Column(
                            spacing=0,
                            controls=[
                                ft.Container(height=8),
                                ft.Text(
                                    "OPENCV ON DEVICE",
                                    size=13,
                                    weight=ft.FontWeight.W_800,
                                    color=ACCENT,
                                ),
                                ft.Text(
                                    "Find the faces", size=30, weight=ft.FontWeight.W_900, color=INK
                                ),
                            ],
                        ),
                        card := ft.Container(
                            width=width,
                            height=height,
                            border_radius=20,
                            bgcolor=DARK,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            content=ft.Stack(
                                fit=ft.StackFit.EXPAND,
                                controls=[
                                    picture := ft.Image(
                                        src=tiles[0].photo.jpg,
                                        fit=ft.BoxFit.CONTAIN,
                                        gapless_playback=True,
                                    ),
                                    overlay := ft.Stack(),
                                ],
                            ),
                        ),
                        caption := ft.Text("", size=13, color=MUTED),
                        ft.Container(
                            bgcolor=CARD,
                            border_radius=18,
                            padding=ft.Padding.symmetric(vertical=12, horizontal=16),
                            content=ft.Row(
                                spacing=14,
                                controls=[
                                    ft.Container(
                                        width=52,
                                        height=52,
                                        border_radius=14,
                                        bgcolor=ft.Colors.with_opacity(0.12, ACCENT),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(
                                            ft.Icons.FACE_RETOUCHING_NATURAL, color=ACCENT, size=28
                                        ),
                                    ),
                                    ft.Column(
                                        spacing=0,
                                        expand=True,
                                        controls=[
                                            count := ft.Text(
                                                "–", size=32, weight=ft.FontWeight.W_900, color=INK
                                            ),
                                            details := ft.Text("Tap a photo", size=14, color=MUTED),
                                        ],
                                    ),
                                    blur_switch := ft.Switch(
                                        label="Blur",
                                        label_position=ft.LabelPosition.LEFT,
                                        active_color=ACCENT,
                                        on_change=show_picture,
                                    ),
                                ],
                            ),
                        ),
                        ft.Row(spacing=8, controls=[tile.frame for tile in tiles]),
                        ft.Text(
                            "Tap a photo, or try your own. "
                            "Crew photos: NASA, public domain. Model: YuNet, 227 KB.",
                            size=12,
                            color=MUTED,
                        ),
                    ],
                )
            ),
        )
    )
    async with finding:  # the first photo, while taps wait
        await look_at(tiles[0])


if __name__ == "__main__":
    ft.run(main)
