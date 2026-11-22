import asyncio
import http.client
import os
import tempfile
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

import cv2
import flet as ft
import numpy as np
import onnxruntime as ort


class Sample(NamedTuple):
    """A sample photo (CC0) the app downloads on the first launch."""

    name: str  # its file name
    url: str
    crop: tuple[float, float, float, float]  # the part to keep, as fractions: x0, y0, x1, y1
    caption: str


# The app's data folder (set by `flet run` and built apps), else the temp folder.
FOLDER = os.path.join(os.environ.get("FLET_APP_STORAGE_DATA") or tempfile.gettempdir(), "ppocr")
# PaddleOCR's PP-OCR mobile models (Apache-2.0), as the ONNX files RapidOCR publishes (Apache-2.0).
MODELS = "https://huggingface.co/SWHL/RapidOCR/resolve/1cfba2e90fc938db55889873735088de210cc173/"
FINDER_URL = MODELS + "PP-OCRv4/ch_PP-OCRv4_det_infer.onnx"  # finds lines of text: 4.7 MB
READER_URL = MODELS + "PP-OCRv3/en_PP-OCRv3_rec_infer.onnx"  # reads English text: 9 MB
COMMONS = "https://upload.wikimedia.org/wikipedia/commons/thumb/"
SAMPLES = [
    Sample(
        "coffee.jpg",
        COMMONS + "4/4c/Coffee-sign-typography-shop_%2824326253515%29.jpg/"
        "960px-Coffee-sign-typography-shop_%2824326253515%29.jpg",
        (0.06, 0.0, 0.94, 1.0),
        "Shop sign",
    ),
    Sample(
        "phoenix.jpg",
        COMMONS + "f/fc/Phoenix_Boulevard_street_name_sign_Jun25.jpg/"
        "960px-Phoenix_Boulevard_street_name_sign_Jun25.jpg",
        (0.27, 0.14, 0.81, 0.68),
        "Street sign",
    ),
    Sample(
        "newts.jpg",
        COMMONS + "3/34/Please_do_not_touch_the_newts.jpg/960px-Please_do_not_touch_the_newts.jpg",
        (0.0, 0.0, 1.0, 1.0),
        "Notice",
    ),
]
# The text finder learned from photos normalized with these per-channel values.
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
MIN_SCORE = 0.6  # lines the reader is less sure about are left out
ACCENT, BOX, INK, MUTED = "#7C3AED", "#FFD60A", "#111827", "#6B7280"
CARD, SOFT, LINE, DARK = "#F5F3FF", "#EDE9FE", "#E9E3FF", "#0B0A10"

Photo = tuple[np.ndarray, bytes]  # what the models read (a cv2 image), and the JPEG to show
Line = tuple[np.ndarray, str, float]  # a box (4 corners, in photo pixels), its text, its score


@dataclass
class Models:
    """The two PP-OCR models, and the characters the reader knows."""

    finder: ort.InferenceSession
    reader: ort.InferenceSession
    alphabet: list[str]


def write_file(path: str, data: bytes):
    """Write a whole file through a temporary one: never leave half a file behind."""
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)


async def download(url: str, name: str, on_progress: Callable[[str, int, int], None]):
    """Download a file into FOLDER, unless it's there already.

    After each chunk, on_progress gets the file's name, the bytes so far and the total.
    """
    path = os.path.join(FOLDER, name)
    if os.path.exists(path):
        return
    os.makedirs(FOLDER, exist_ok=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "FletReadText/1.0 (https://flet.dev)"}
    )
    # Blocking calls run in a thread, a chunk at a time: the UI stays live and shows the progress.
    response = await asyncio.to_thread(urllib.request.urlopen, request, timeout=60)
    total = int(response.headers.get("Content-Length") or 0)
    data = bytearray()
    with response:
        while chunk := await asyncio.to_thread(response.read, 256 * 1024):
            data += chunk
            on_progress(name, len(data), total)
    await asyncio.to_thread(write_file, path, data)


def decode(data: bytes, crop: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)) -> Photo:
    """A photo's bytes as a cv2 image (cropped, at most 1280 px) and as JPEG bytes."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    h, w = img.shape[:2]
    x0, y0, x1, y1 = crop
    img = img[round(y0 * h) : round(y1 * h), round(x0 * w) : round(x1 * w)]
    scale = 1280 / max(img.shape[:2])
    if scale < 1:  # a phone photo is far bigger than the models need
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
    return np.ascontiguousarray(img), jpg


def open_files() -> tuple[Models, list[tuple[Photo, str]]]:
    """The models, and each sample photo with its caption, from the downloaded files (blocking)."""
    cpu = ["CPUExecutionProvider"]
    finder = ort.InferenceSession(os.path.join(FOLDER, "det.onnx"), providers=cpu)
    reader = ort.InferenceSession(os.path.join(FOLDER, "rec.onnx"), providers=cpu)
    # The reader's 95 characters are stored in the model file; 0 is CTC's "blank".
    characters = reader.get_modelmeta().custom_metadata_map["character"].splitlines()
    samples = []
    for sample in SAMPLES:
        with open(os.path.join(FOLDER, sample.name), "rb") as f:
            samples.append((decode(f.read(), sample.crop), sample.caption))
    return Models(finder, reader, ["", *characters, " "]), samples


async def load(
    on_progress: Callable[[str, int, int], None],
) -> tuple[Models, list[tuple[Photo, str]]]:
    """The models and the sample photos; downloaded on the first launch."""
    await download(FINDER_URL, "det.onnx", on_progress)
    await download(READER_URL, "rec.onnx", on_progress)
    for sample in SAMPLES:
        await download(sample.url, sample.name, on_progress)
    return await asyncio.to_thread(open_files)


def corners(points: np.ndarray) -> np.ndarray:
    """4 points ordered top-left, top-right, bottom-right, bottom-left."""
    points = np.asarray(points, np.float32)
    total, diff = points.sum(1), points[:, 1] - points[:, 0]
    return np.float32(
        [
            points[total.argmin()],
            points[diff.argmin()],
            points[total.argmax()],
            points[diff.argmax()],
        ]
    )


def find_boxes(finder: ort.InferenceSession, img: np.ndarray) -> list[np.ndarray]:
    """The finder marks text pixels in a map; each blob in the map becomes a box around a line."""
    h, w = img.shape[:2]
    scale = 736 / max(h, w)  # the finder takes sides that are multiples of 32
    nh, nw = max(32, round(h * scale / 32) * 32), max(32, round(w * scale / 32) * 32)
    x = (cv2.resize(img, (nw, nh)).astype(np.float32) / 255 - MEAN) / STD
    text_map = finder.run(None, {"x": x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    mask = (text_map > 0.3).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        if cv2.contourArea(contour) < 16:
            continue
        inside = np.zeros_like(mask)
        cv2.drawContours(inside, [contour], -1, 1, -1)
        if text_map[inside == 1].mean() < 0.6:  # a weak blob, not text
            continue
        (cx, cy), (bw, bh), angle = cv2.minAreaRect(contour)
        grow = bw * bh * 1.6 / (2 * (bw + bh))  # the map marks a shrunken core of each line
        if min(bw, bh) + 2 * grow < 5:
            continue
        box = cv2.boxPoints(((cx, cy), (bw + 2 * grow, bh + 2 * grow), angle))
        box[:, 0] *= w / nw
        box[:, 1] *= h / nh
        boxes.append(corners(box))
    boxes.sort(key=lambda box: box[:, 1].mean())  # top to bottom
    return boxes


def cut_out(img: np.ndarray, box: np.ndarray) -> np.ndarray:
    """Warp one box flat into its own small image."""
    w = int(max(np.linalg.norm(box[0] - box[1]), np.linalg.norm(box[3] - box[2])))
    h = int(max(np.linalg.norm(box[0] - box[3]), np.linalg.norm(box[1] - box[2])))
    flat = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    piece = cv2.warpPerspective(
        img, cv2.getPerspectiveTransform(box, flat), (w, h), borderMode=cv2.BORDER_REPLICATE
    )
    return np.rot90(piece) if h > 1.5 * w else piece  # a tall box holds vertical text


def read_line(models: Models, piece: np.ndarray) -> tuple[str, float]:
    """The text in one line and how sure the reader is (0-1)."""
    h, w = piece.shape[:2]
    x = (cv2.resize(piece, (max(16, round(48 * w / h)), 48)).astype(np.float32) / 255 - 0.5) / 0.5
    probs = models.reader.run(None, {"x": x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
    # The reader scores every character at each step along the line: keep the best one,
    # then drop repeats and blanks (CTC greedy decoding).
    text, scores, previous = "", [], 0
    for i, score in zip(probs.argmax(1), probs.max(1)):
        if i != previous and i != 0:
            text += models.alphabet[i]
            scores.append(score)
        previous = i
    return text.strip(), float(np.mean(scores)) if scores else 0.0


def read_text(models: Models, img: np.ndarray) -> tuple[list[Line], float]:
    """Every line the reader is sure enough about, and the seconds it all took."""
    start = time.perf_counter()
    lines = []
    for box in find_boxes(models.finder, img):
        text, score = read_line(models, cut_out(img, box))
        if text and score >= MIN_SCORE:
            lines.append((box, text, score))
    return lines, time.perf_counter() - start


def plural(n: int, word: str) -> str:
    """'1 line', '2 lines'."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def cover(control: ft.Control) -> ft.Control:
    """The control, stretched over the whole Stack it's in."""
    control.left, control.top, control.right, control.bottom = 0, 0, 0, 0
    return control


def box_view(index: int, on_click: ft.ControlEventHandler[ft.Container]) -> ft.Container:
    """A yellow frame around line `index` over the photo; it pops in once placed."""
    return ft.Container(
        data=index,
        border_radius=4,
        border=ft.Border.all(2.5, BOX),
        bgcolor=ft.Colors.with_opacity(0.18, BOX),
        scale=1.4,
        opacity=0,
        animate=ft.Animation(200),
        animate_scale=ft.Animation(300, ft.AnimationCurve.EASE_OUT_BACK),
        animate_opacity=ft.Animation(200),
        on_click=on_click,
    )


def line_row(
    index: int, text: str, score: float, on_click: ft.ControlEventHandler[ft.Container]
) -> ft.Container:
    """One line of the text, with how sure the reader is; it slides in."""
    return ft.Container(
        data=index,
        key=ft.ScrollKey(index),
        bgcolor=ft.Colors.WHITE,
        border_radius=10,
        border=ft.Border.all(2, LINE),
        padding=ft.Padding.symmetric(horizontal=12, vertical=4),
        opacity=0,
        offset=ft.Offset(0, 0.4),
        animate=ft.Animation(200),
        animate_opacity=ft.Animation(220),
        animate_offset=ft.Animation(260, ft.AnimationCurve.EASE_OUT_CUBIC),
        on_click=on_click,
        content=ft.Row(
            controls=[
                ft.Text(
                    text,
                    size=18,
                    weight=ft.FontWeight.W_700,
                    color=INK,
                    expand=True,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(f"{score:.0%}", size=13, weight=ft.FontWeight.W_600, color=MUTED),
            ]
        ),
    )


@dataclass
class Tile:
    """A photo under the text, with its number of lines once it's read."""

    frame: ft.Container  # outlined while its photo is the one shown
    picture: ft.Container  # the photo, or the "add a photo" icon
    badge: ft.Container  # the number of lines, shown once the photo is read
    view: ft.Column
    photo: Photo | None  # None until the user picks one for the "Your photo" tile


def tile_photo(jpg: bytes) -> ft.Image:
    """A photo filling its tile."""
    return ft.Image(src=jpg, fit=ft.BoxFit.COVER)


def make_tile(
    photo: Photo | None,
    caption: str,
    on_click: ft.ControlEventHandler[ft.Container] | None = None,
    action: ft.PickFiles | None = None,
) -> Tile:
    """A tile for a sample photo, or, without a photo, the "Your photo" tile."""
    view = ft.Column(
        expand=True,
        spacing=3,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            frame := ft.Container(
                height=60,
                border_radius=12,
                bgcolor=SOFT,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                border=ft.Border.all(3, ft.Colors.TRANSPARENT),
                on_click=on_click,
                action=action,
                content=ft.Stack(
                    controls=[
                        picture := cover(
                            ft.Container(
                                content=tile_photo(photo[1])
                                if photo
                                else ft.Icon(
                                    ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, color=ACCENT, size=28
                                )
                            )
                        ),
                        badge := ft.Container(
                            right=4,
                            bottom=4,
                            visible=False,
                            padding=ft.Padding.symmetric(vertical=1, horizontal=7),
                            border_radius=10,
                            bgcolor=ACCENT,
                            content=ft.Text(
                                "", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE
                            ),
                        ),
                    ]
                ),
            ),
            ft.Text(
                caption,
                size=12,
                weight=ft.FontWeight.W_600,
                color=MUTED,
                text_align=ft.TextAlign.CENTER,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
    )
    tile = Tile(frame, picture, badge, view, photo)
    frame.data = tile  # a click on the frame finds its tile
    return tile


async def main(page: ft.Page):
    page.title = "Read text"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ACCENT)
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    if not page.web and page.platform in (
        ft.PagePlatform.MACOS,
        ft.PagePlatform.WINDOWS,
        ft.PagePlatform.LINUX,
    ):
        page.window.width, page.window.height = 430, 880  # phone-shaped

    # The first launch downloads the two models and the sample photos.
    retry = asyncio.Event()

    def handle_progress(name: str, done: int, total: int):
        loading_status.value = f"Downloading {name}"
        loading_bar.value = done / total if total else None
        loading_size.value = f"{done / 1e6:.1f} of {total / 1e6:.1f} MB" if total else ""
        page.update()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                max_width=320,
                expand=True,
                spacing=12,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.DOCUMENT_SCANNER_OUTLINED, size=56, color=ACCENT),
                    ft.Text(
                        "Read text from a photo", size=26, weight=ft.FontWeight.W_800, color=INK
                    ),
                    loading_status := ft.Text("Opening the models…", size=16, color=MUTED),
                    loading_bar := ft.ProgressBar(
                        bar_height=8, border_radius=4, color=ACCENT, bgcolor=LINE
                    ),
                    loading_size := ft.Text(
                        "PP-OCR, two models, 14 MB, downloaded once",
                        size=13,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    retry_button := ft.Button(
                        "Try again",
                        icon=ft.Icons.REFRESH,
                        visible=False,
                        on_click=lambda: retry.set(),
                    ),
                ],
            ),
        )
    )
    while True:
        try:
            models, samples = await load(handle_progress)
            break
        except (OSError, http.client.HTTPException) as error:  # no network, a server said no...
            loading_status.value = "The download didn't finish"
            loading_size.value = str(error)
            loading_bar.visible, retry_button.visible = False, True
            page.update()
            await retry.wait()  # until "Try again" is clicked
            retry.clear()
            loading_bar.visible, retry_button.visible = True, False
            loading_status.value, loading_bar.value = "Trying again…", None
            page.update()
    page.controls.clear()

    reading = asyncio.Lock()  # one photo at a time
    lines: list[Line] = []  # the lines of the photo shown
    shown_size = (1, 1)  # the shown photo's width and height, in pixels
    frame_size = (0.0, 0.0)  # the size the photo's frame reports
    selected: int | None = None  # the line tapped, if any

    def place_boxes():
        """Put each box over its line: the photo is fitted in the frame, centered."""
        (w, h), (iw, ih) = frame_size, shown_size
        scale = min(w / iw, h / ih)
        ox, oy = (w - iw * scale) / 2, (h - ih * scale) / 2
        for box, (quad, _, _) in zip(boxes.controls, lines):
            (x0, y0), (x1, y1) = quad.min(0).tolist(), quad.max(0).tolist()  # plain floats
            x0, y0 = max(0, ox + x0 * scale), max(0, oy + y0 * scale)
            x1, y1 = min(w, ox + x1 * scale), min(h, oy + y1 * scale)
            box.left, box.top, box.width, box.height = x0, y0, x1 - x0, y1 - y0

    def handle_frame_size_change(e: ft.LayoutSizeChangeEvent[ft.Container]):
        nonlocal frame_size
        frame_size = (e.width, e.height)
        place_boxes()
        boxes.update()

    def set_copy_text():
        """Point the Copy button at the selected line, or at all the text."""
        texts = [text for _, text, _ in lines]
        copy_button.disabled = not texts
        copy_button.content = "Copy all" if selected is None else "Copy line"
        text = "\n".join(texts) if selected is None else texts[selected]
        # The client copies right in the tap (Safari allows it only then): set the text first.
        copy_button.action = ft.CopyToClipboard(text) if texts else None

    async def select(index: int | None):
        """Highlight one line in the photo and in the list (None: all of them)."""
        nonlocal selected
        selected = index
        for box, row in zip(boxes.controls, rows.controls):
            on = box.data == index
            box.border = ft.Border.all(3.5 if on else 2.5, ACCENT if on else BOX)
            box.bgcolor = ft.Colors.with_opacity(0.35 if on else 0.18, ACCENT if on else BOX)
            box.opacity = 1 if index is None or on else 0.4
            row.bgcolor = SOFT if on else ft.Colors.WHITE
            row.border = ft.Border.all(2, ACCENT if on else LINE)
        set_copy_text()
        page.update()
        if index is not None:
            await rows.scroll_to(scroll_key=ft.ScrollKey(index), duration=300)

    async def handle_line_click(e: ft.Event[ft.Container]):
        if reading.locked():  # the lines are still coming in
            return
        await select(None if e.control.data == selected else e.control.data)

    def handle_copy_click(e: ft.Event[ft.FilledButton]):
        copied = f"“{lines[selected][1]}”" if selected is not None else plural(len(lines), "line")
        page.show_dialog(ft.SnackBar(f"Copied {copied}", duration=ft.Duration(seconds=2)))

    def show_photo(tile: Tile):
        """Show the tile's photo, with no boxes or text yet."""
        nonlocal shown_size, selected
        img, jpg = tile.photo
        photo_view.src = jpg
        shown_size = (img.shape[1], img.shape[0])
        lines.clear()
        selected = None
        boxes.controls.clear()
        rows.controls.clear()
        for t in tiles:
            t.frame.border = ft.Border.all(3, ACCENT if t is tile else ft.Colors.TRANSPARENT)
        status.value, status.color = "Finding text…", MUTED
        count_pill.visible = False
        hint.value = "PP-OCR · ONNX Runtime · on device"
        set_copy_text()
        page.update()

    async def read(tile: Tile):
        """Show the tile's photo, find and read its text, then show boxes and lines."""
        show_photo(tile)
        (found, seconds), _ = await asyncio.gather(  # at least 0.5 s: the new photo shows first
            asyncio.to_thread(read_text, models, tile.photo[0]), asyncio.sleep(0.5)
        )
        lines.extend(found)
        boxes.controls = [box_view(i, handle_line_click) for i in range(len(lines))]
        place_boxes()
        status.value = f"Reading {plural(len(lines), 'line')}…"
        page.update()
        await asyncio.sleep(0.05)
        for box in boxes.controls:  # the boxes pop in over the text
            box.scale, box.opacity = 1, 1
        page.update()
        await asyncio.sleep(0.5)

        rows.controls = [
            line_row(i, text, score, handle_line_click) for i, (_, text, score) in enumerate(lines)
        ]
        page.update()
        await asyncio.sleep(0.05)
        for row in rows.controls:  # then the lines slide in, one by one
            row.opacity, row.offset = 1, ft.Offset(0, 0)
            page.update()
            await asyncio.sleep(0.09)

        status.color = INK
        status.value = f"Read in {seconds:.1f} s" if lines else "No text found"
        count_pill.content.value = plural(len(lines), "line")
        count_pill.visible = bool(lines)
        tile.badge.content.value = str(len(lines))
        tile.badge.visible = True
        hint.value = "Tap a box or a line to pick it" if lines else "Try a photo with bigger text"
        set_copy_text()
        page.update()

    async def handle_tile_click(e: ft.Event[ft.Container]):
        if not reading.locked():  # a tap while a photo is being read is ignored
            async with reading:
                await read(e.control.data)

    async def handle_pick_result(e: ft.FilePickerResultEvent):
        if not e.files:  # canceled
            return
        async with reading:
            try:
                your_tile.photo = await asyncio.to_thread(decode, e.files[0].bytes)
            except ValueError:
                page.show_dialog(ft.SnackBar(f"Can't read {e.files[0].name}: try a JPEG or PNG"))
                return
            your_tile.picture.content = tile_photo(your_tile.photo[1])
            await read(your_tile)

    # Flet drops a service once nothing refers to it: the "Your photo" tile's action keeps it.
    file_picker = ft.FilePicker(on_result=handle_pick_result)
    tiles = [make_tile(photo, caption, on_click=handle_tile_click) for photo, caption in samples]
    your_tile = make_tile(
        None,
        "Your photo",
        # The client opens the picker right in the tap: browsers (iOS Safari above all)
        # open one only while they handle the click. The picked file comes to on_result.
        action=ft.PickFiles(file_picker, file_type=ft.FilePickerFileType.IMAGE, with_data=True),
    )
    tiles.append(your_tile)

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                max_width=476,  # fills a phone, stays phone-shaped on wide windows
                padding=ft.Padding.only(left=16, right=16, top=8, bottom=8),
                content=ft.Column(
                    expand=True,
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Column(
                            spacing=0,
                            controls=[
                                ft.Text(
                                    "OCR ON DEVICE",
                                    size=13,
                                    weight=ft.FontWeight.W_800,
                                    color=ACCENT,
                                ),
                                ft.Text(
                                    "Read text from a photo",
                                    size=28,
                                    weight=ft.FontWeight.W_900,
                                    color=INK,
                                ),
                            ],
                        ),
                        ft.Container(
                            aspect_ratio=4 / 3,
                            # Its real size differs from one screen to the next:
                            # the boxes are placed with the size it reports.
                            on_size_change=handle_frame_size_change,
                            border_radius=20,
                            bgcolor=DARK,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                            content=ft.Stack(
                                controls=[
                                    photo_view := cover(
                                        ft.Image(
                                            src=tiles[0].photo[1],
                                            fit=ft.BoxFit.CONTAIN,
                                            gapless_playback=True,
                                        )
                                    ),
                                    boxes := cover(ft.Stack()),
                                ]
                            ),
                        ),
                        ft.Container(
                            expand=True,
                            bgcolor=CARD,
                            border_radius=20,
                            padding=ft.Padding.only(left=16, right=16, top=12, bottom=10),
                            content=ft.Column(
                                expand=True,
                                spacing=10,
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.TEXT_FIELDS, color=ACCENT, size=24),
                                            status := ft.Text(
                                                "",
                                                size=17,
                                                weight=ft.FontWeight.W_700,
                                                color=MUTED,
                                                expand=True,
                                            ),
                                            count_pill := ft.Container(
                                                visible=False,
                                                padding=ft.Padding.symmetric(
                                                    horizontal=12, vertical=4
                                                ),
                                                border_radius=14,
                                                bgcolor=ACCENT,
                                                content=ft.Text(
                                                    "",
                                                    size=14,
                                                    weight=ft.FontWeight.W_800,
                                                    color=ft.Colors.WHITE,
                                                ),
                                            ),
                                        ]
                                    ),
                                    rows := ft.Column(
                                        spacing=6, scroll=ft.ScrollMode.AUTO, expand=True
                                    ),
                                    ft.Row(
                                        controls=[
                                            hint := ft.Text("", size=13, color=MUTED, expand=True),
                                            copy_button := ft.FilledButton(
                                                "Copy all",
                                                icon=ft.Icons.COPY,
                                                disabled=True,
                                                on_click=handle_copy_click,
                                            ),
                                        ]
                                    ),
                                ],
                            ),
                        ),
                        ft.Row(spacing=8, controls=[tile.view for tile in tiles]),
                    ],
                ),
            ),
        )
    )
    async with reading:  # the first photo, while taps wait
        await read(tiles[0])


if __name__ == "__main__":
    ft.run(main)
