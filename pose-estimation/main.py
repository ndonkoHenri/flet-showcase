import asyncio
import math
import os
import tempfile
import urllib.request

import cv2
import flet as ft
import flet.canvas as cv
import numpy as np
import onnxruntime as ort

# MoveNet SinglePose Lightning (Google, Apache-2.0), converted to ONNX by Xenova.
MODEL_URL = (
    "https://huggingface.co/Xenova/movenet-singlepose-lightning/resolve/"
    "ed0f314bb7356fd1dbf1e4f52c2d40791bf6534f/onnx/model.onnx"
)
MODEL_SIZE = 9413268  # bytes
COMMONS = "https://upload.wikimedia.org/wikipedia/commons/thumb/"
SAMPLES = [  # (file name, url, crop around the person as fractions x0, y0, x1, y1)
    (
        "ballet.jpg",
        COMMONS + "c/cb/Alfresco_Ballet_9.jpg/960px-Alfresco_Ballet_9.jpg",
        (0.12, 0.0, 1.0, 1.0),
    ),
    (
        "beach.jpg",
        COMMONS + "c/c1/Yoga_in_the_beach_%28Unsplash%29.jpg/"
        "960px-Yoga_in_the_beach_%28Unsplash%29.jpg",
        (0.0, 0.41, 0.722, 0.771),
    ),
    (
        "plank.jpg",
        COMMONS + "5/59/Yoga_CDMX_DSC0844_%2835032895131%29.jpg/"
        "960px-Yoga_CDMX_DSC0844_%2835032895131%29.jpg",
        (0.0, 0.0, 1.0, 1.0),
    ),
]

# MoveNet's 17 points: 0 nose, 1-4 eyes and ears, 5/6 shoulders, 7/8 elbows,
# 9/10 wrists, 11/12 hips, 13/14 knees, 15/16 ankles (odd = the person's left).
LEFT, RIGHT, MIDDLE = "#FF2D78", "#22D3EE", "#FDE047"
BONES = [  # (point, point, color): torso first, then arms, legs and face
    (5, 6, MIDDLE), (5, 11, MIDDLE), (6, 12, MIDDLE), (11, 12, MIDDLE),
    (5, 7, LEFT), (7, 9, LEFT), (6, 8, RIGHT), (8, 10, RIGHT),
    (11, 13, LEFT), (13, 15, LEFT), (12, 14, RIGHT), (14, 16, RIGHT),
    (0, 1, LEFT), (1, 3, LEFT), (0, 2, RIGHT), (2, 4, RIGHT),
]  # fmt: skip
ANGLES = [  # (name, a, b, c, color): the angle at b, between b-a and b-c
    ("Left elbow", 5, 7, 9, LEFT),
    ("Right elbow", 6, 8, 10, RIGHT),
    ("Left knee", 11, 13, 15, LEFT),
    ("Right knee", 12, 14, 16, RIGHT),
]
SEEN = 0.3  # a point counts when the model's score is above this
ACCENT, INK, MUTED, CARD, DARK = "#E00050", "#1B1A22", "#6B6A78", "#F4F3F8", "#0B0A10"


def fetch(url: str, name: str, size: int | None = None) -> str:
    """Download a file once into the app's data folder; return its path."""
    folder = os.path.join(
        os.environ.get("FLET_APP_STORAGE_DATA") or tempfile.gettempdir(), "movenet"
    )
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    if os.path.exists(path) and (size is None or os.path.getsize(path) == size):
        return path
    request = urllib.request.Request(
        url, headers={"User-Agent": "FletPoseDemo/1.0 (https://flet.dev)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)  # never leave half a file behind
    return path


def decode(data: bytes, crop=(0.0, 0.0, 1.0, 1.0)) -> tuple[np.ndarray, bytes]:
    """A photo's bytes as a cv2 image (cropped, at most 1280 px) and as JPEG bytes."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    h, w = img.shape[:2]
    x0, y0, x1, y1 = crop
    img = img[round(y0 * h) : round(y1 * h), round(x0 * w) : round(x1 * w)]
    scale = 1280 / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
    return np.ascontiguousarray(img), jpg


def load() -> tuple[ort.InferenceSession, list[tuple[np.ndarray, bytes]]]:
    """The model and the sample photos, downloaded on the first launch."""
    model = ort.InferenceSession(
        fetch(MODEL_URL, "movenet-lightning.onnx", MODEL_SIZE),
        providers=["CPUExecutionProvider"],
    )
    samples = []
    for name, url, crop in SAMPLES:
        with open(fetch(url, name), "rb") as f:
            samples.append(decode(f.read(), crop))
    return model, samples


def find_pose(model: ort.InferenceSession, photo: np.ndarray) -> list[tuple]:
    """17 points as (x, y, score), in the photo's pixels."""
    h, w = photo.shape[:2]
    side = max(h, w)  # the model takes a square: pad the photo with black bars
    square = np.zeros((side, side, 3), np.uint8)
    top, left = (side - h) // 2, (side - w) // 2
    square[top : top + h, left : left + w] = photo
    small = cv2.resize(square, (192, 192), interpolation=cv2.INTER_AREA)
    small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype(np.int32)[None]
    points = model.run(None, {"input": small})[0][0, 0]  # 17 x (y, x, score), 0-1
    return [(x * side - left, y * side - top, s) for y, x, s in points.tolist()]


def angle(points: list[tuple], a: int, b: int, c: int) -> float | None:
    """The angle at point b in degrees, or None when one of the points isn't seen."""
    if min(points[a][2], points[b][2], points[c][2]) <= SEEN:
        return None
    v1 = (points[a][0] - points[b][0], points[a][1] - points[b][1])
    v2 = (points[c][0] - points[b][0], points[c][1] - points[b][1])
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2) + 1e-6)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


async def main(page: ft.Page):
    page.title = "Strike a pose"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    W = min(page.width or 400, 500) - 36  # the photo card's size
    H = round(W * 0.75)

    message = ft.Text("Downloading the model (9.4 MB)...", size=17, color=MUTED)
    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    tight=True,
                    spacing=16,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[ft.ProgressRing(color=ACCENT), message],
                ),
            ),
        )
    )
    try:
        model, photos = await asyncio.to_thread(load)  # a thread: the UI stays live
    except OSError as error:
        message.value = f"Can't download the model or photos: {error}"
        page.update()
        return
    page.controls.clear()

    # Flet drops a service once nothing refers to it: the click handler keeps this one.
    file_picker = ft.FilePicker()
    busy = {"now": False}

    photo_view = ft.Image(
        src=photos[0][1], fit=ft.BoxFit.CONTAIN, left=0, top=0, right=0, bottom=0
    )
    # The canvas covers the photo; its real size can differ from W x H (a narrow
    # window squeezes the card), so the skeleton is placed with the size it reports.
    canvas = cv.Canvas(left=0, top=0, right=0, bottom=0)
    shown = {"size": (W, H), "points": None, "photo": None}  # what the canvas shows
    status_icon = ft.Icon(ft.Icons.ACCESSIBILITY_NEW, color=ACCENT, size=30)
    status = ft.Text("Ready", size=19, weight=ft.FontWeight.W_800, color=INK)
    detail = ft.Text("MoveNet Lightning, 9.4 MB, on device", size=14, color=MUTED)

    angle_values = []
    angle_tiles = []
    for name, *_, color in ANGLES:
        angle_values.append(
            value := ft.Text("–", size=26, weight=ft.FontWeight.W_900, color=INK)
        )
        angle_tiles.append(
            ft.Container(
                expand=True,
                bgcolor=CARD,
                border_radius=16,
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                content=ft.Column(
                    spacing=0,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Container(
                                    width=10, height=10, border_radius=5, bgcolor=color
                                ),
                                ft.Text(
                                    name,
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                    color=MUTED,
                                ),
                            ],
                        ),
                        value,
                    ],
                ),
            )
        )

    def thumb(i: int, content: ft.Control) -> ft.Container:
        """A tile under the angles: a sample photo, or "Your photo"."""
        return ft.Container(
            data=i,
            expand=True,
            height=104,
            border_radius=14,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor=DARK if i < len(SAMPLES) else CARD,
            border=ft.Border.all(3, ft.Colors.TRANSPARENT),
            on_click=handle_thumb_click,
            content=content,
        )

    badges = []  # the "17 pts" pill on each tile, shown after its photo is read
    tile_photos = []  # the photo filling each tile
    for i in range(len(SAMPLES) + 1):
        badges.append(
            ft.Container(
                right=6,
                bottom=6,
                visible=False,
                padding=ft.Padding.symmetric(vertical=2, horizontal=8),
                border_radius=10,
                bgcolor=ACCENT,
                content=ft.Text("", size=13, weight=ft.FontWeight.W_800, color="white"),
            )
        )
        tile_photos.append(
            ft.Image(
                src=photos[min(i, len(SAMPLES) - 1)][1],  # the last tile's comes later
                visible=i < len(SAMPLES),
                fit=ft.BoxFit.COVER,
                left=0,
                top=0,
                right=0,
                bottom=0,
            )
        )
    add_photo = ft.Container(
        left=0,
        top=0,
        right=0,
        bottom=0,
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

    async def draw_skeleton(animate: bool):
        """Draw the shown points and the bones between them over the photo."""
        points, img = shown["points"], shown["photo"]
        w, h = shown["size"]
        ih, iw = img.shape[:2]
        s = min(w / iw, h / ih)  # the photo is shown fitted in the card, centered
        ox, oy = (w - iw * s) / 2, (h - ih * s) / 2

        def xy(k: int) -> tuple[float, float]:
            """Point k on the canvas."""
            return points[k][0] * s + ox, points[k][1] * s + oy

        seen = [k for k in range(17) if points[k][2] > SEEN]
        canvas.shapes = [
            cv.Circle(*xy(k), 6, paint=ft.Paint(color="white")) for k in seen
        ]
        if animate:
            canvas.update()
            await asyncio.sleep(0.15)
        for a, b, color in BONES:  # one bone at a time: the skeleton draws itself
            if a in seen and b in seen:
                canvas.shapes.append(
                    cv.Line(
                        *xy(a),
                        *xy(b),
                        paint=ft.Paint(
                            color=color,
                            stroke_width=5,
                            stroke_cap=ft.StrokeCap.ROUND,
                            style=ft.PaintingStyle.STROKE,
                        ),
                    )
                )
                if animate:
                    canvas.update()
                    await asyncio.sleep(0.04)
        for k in seen:  # dots on top of the bones
            canvas.shapes.append(cv.Circle(*xy(k), 3.5, paint=ft.Paint(color=INK)))
        canvas.update()

    async def handle_canvas_resize(e: cv.CanvasResizeEvent):
        shown["size"] = (e.width, e.height)
        if shown["points"] is not None and not busy["now"]:
            await draw_skeleton(animate=False)  # keep the skeleton on the person

    canvas.on_resize = handle_canvas_resize

    async def analyze(i: int):
        """Show photo i, find its pose, then draw the skeleton and fill in the angles."""
        img, jpg = photos[i]
        photo_view.src = jpg
        shown["points"] = None
        canvas.shapes.clear()
        for j, tile in enumerate(tiles):
            tile.border = ft.Border.all(3, ACCENT if j == i else ft.Colors.TRANSPARENT)
        status_icon.icon = ft.Icons.SEARCH
        status.value = "Finding the pose..."
        detail.value = "MoveNet Lightning, 9.4 MB, on device"
        for value in angle_values:
            value.value = "–"
        page.update()

        points, _ = await asyncio.gather(  # at least 0.4 s: the new photo shows first
            asyncio.to_thread(find_pose, model, img), asyncio.sleep(0.4)
        )
        shown["points"], shown["photo"] = points, img
        await draw_skeleton(animate=True)

        seen = [k for k in range(17) if points[k][2] > SEEN]
        status_icon.icon = ft.Icons.CHECK_CIRCLE if seen else ft.Icons.PERSON_OFF
        status.value = f"{len(seen)} of 17 body points"
        detail.value = "Found by MoveNet, drawn on a canvas"
        for value, (_, a, b, c, _) in zip(angle_values, ANGLES):
            degrees = angle(points, a, b, c)
            value.value = "–" if degrees is None else f"{degrees:.0f}°"
        badges[i].content.value = f"{len(seen)} pts"
        badges[i].visible = True
        page.update()

    async def pick_photo() -> bool:
        """Let the user pick a photo for the last tile; False when they cancel."""
        files = await file_picker.pick_files(
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True,  # the bytes, on every platform (the web has no paths)
        )
        if not files:
            return False
        try:
            photo = decode(files[0].bytes)
        except ValueError:
            status_icon.icon = ft.Icons.ERROR_OUTLINE
            status.value = "Can't read that file"
            detail.value = "Try a JPEG or PNG photo"
            page.update()
            return False
        photos[len(SAMPLES) :] = [photo]  # replaces the previous one, if any
        tile_photos[-1].src, tile_photos[-1].visible = photo[1], True
        add_photo.visible = False
        return True

    async def handle_thumb_click(e: ft.Event[ft.Container]):
        if busy["now"]:  # one photo at a time
            return
        busy["now"] = True
        try:
            i = e.control.data
            if i < len(SAMPLES) or await pick_photo():
                await analyze(i)
        finally:
            busy["now"] = False

    tiles = []
    for i in range(len(SAMPLES) + 1):
        layers = [tile_photos[i], badges[i]]
        if i == len(SAMPLES):
            layers.insert(1, add_photo)
        tiles.append(thumb(i, ft.Stack(expand=True, controls=layers)))

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                width=W,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Container(height=8),
                            ft.Text(
                                "ON-DEVICE AI",
                                size=13,
                                weight=ft.FontWeight.W_800,
                                color=ACCENT,
                            ),
                            ft.Text(
                                "Strike a pose",
                                size=28,
                                weight=ft.FontWeight.W_900,
                                color=INK,
                            ),
                        ],
                    ),
                    ft.Container(
                        width=W,
                        height=H,
                        border_radius=22,
                        bgcolor=DARK,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Stack(controls=[photo_view, canvas]),
                    ),
                    ft.Container(
                        bgcolor=CARD,
                        border_radius=18,
                        padding=ft.Padding.symmetric(vertical=12, horizontal=16),
                        content=ft.Row(
                            spacing=14,
                            controls=[
                                status_icon,
                                ft.Column(
                                    spacing=0, expand=True, controls=[status, detail]
                                ),
                            ],
                        ),
                    ),
                    ft.Row(spacing=10, controls=angle_tiles[:2]),
                    ft.Row(spacing=10, controls=angle_tiles[2:]),
                    ft.Row(spacing=8, controls=tiles),
                    ft.Text(
                        "Tap a photo, or try your own.",
                        size=13,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                        width=W,
                    ),
                ],
            ),
        )
    )
    busy["now"] = True  # the first photo, while taps wait
    await analyze(0)
    busy["now"] = False


if __name__ == "__main__":
    ft.run(main)
