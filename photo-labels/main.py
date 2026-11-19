import asyncio
import http.client
import os
import tempfile
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import flet as ft
import numpy as np
import onnxruntime as ort

# MobileNetV2 from the ONNX Model Zoo (Apache-2.0): 14 MB, knows 1,000 kinds of things.
MODEL_URL = (
    "https://github.com/onnx/models/raw/4c46cd00fbdb7cd30b6c1c17ab54f2e1f4f7b177/"
    "validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx"
)
# The names of those 1,000 ImageNet classes, in the model's order (pytorch/hub, BSD-3-Clause).
LABELS_URL = (
    "https://raw.githubusercontent.com/pytorch/hub/"
    "a6fc887fbbbda0dd37c440bf8a145f1da6707d6b/imagenet_classes.txt"
)
COMMONS = "https://upload.wikimedia.org/wikipedia/commons/thumb/"
SAMPLES = [  # (file name, url): CC0 photos from Wikimedia Commons
    (
        "dog.jpg",
        COMMONS + "f/fd/Golden_Retriever_Chewing_A_Stick.jpg/"
        "960px-Golden_Retriever_Chewing_A_Stick.jpg",
    ),
    (
        "ladybug.jpg",
        COMMONS + "c/c1/Ladybug_eating_aphids._%2849485764276%29.jpg/"
        "960px-Ladybug_eating_aphids._%2849485764276%29.jpg",
    ),
    ("pineapple.jpg", COMMONS + "5/5c/Pineapple_fruit_2.jpg/960px-Pineapple_fruit_2.jpg"),
]
# The model learned from photos normalized with these per-channel values (RGB).
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
ACCENT, INK, MUTED, SOFT, LINE = "#4F46E5", "#111827", "#6B7280", "#F3F4F6", "#E5E7EB"
GUESS_COLORS = [(ACCENT, ACCENT), ("#A5B4FC", MUTED), ("#C7D2FE", MUTED)]  # (bar, percent)

Photo = tuple[np.ndarray, bytes]  # what the model reads (a cv2 image), and the JPEG to show


def write_file(path: str, data: bytes):
    """Write a whole file through a temporary one: never leave half a file behind."""
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)


async def download(url: str, name: str, on_progress: Callable[[str, int, int], None]) -> str:
    """Download a file once into the app's data folder; return its path.

    After each chunk, on_progress gets the file's name, the bytes so far and the total.
    """
    folder = os.path.join(
        os.environ.get("FLET_APP_STORAGE_DATA") or tempfile.gettempdir(), "mobilenet"
    )
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    if os.path.exists(path):
        return path
    request = urllib.request.Request(
        url, headers={"User-Agent": "FletPhotoLabels/1.0 (https://flet.dev)"}
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
    return path


def decode(data: bytes) -> Photo:
    """A photo's bytes as a cv2 image and as JPEG bytes, at most 1024 px on its long side."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    scale = 1024 / max(img.shape[:2])
    if scale < 1:  # a phone photo is far bigger than the screen needs
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
    return img, jpg


def open_files(
    model_path: str, labels_path: str, photo_paths: list[str]
) -> tuple[ort.InferenceSession, list[str], list[Photo]]:
    """The model, its labels and the sample photos, from the downloaded files (blocking)."""
    model = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    labels = Path(labels_path).read_text().splitlines()
    return model, labels, [decode(Path(path).read_bytes()) for path in photo_paths]


async def load(
    on_progress: Callable[[str, int, int], None],
) -> tuple[ort.InferenceSession, list[str], list[Photo]]:
    """The model, its labels and the sample photos; downloaded on the first launch."""
    files = [("mobilenetv2-12.onnx", MODEL_URL), ("imagenet_classes.txt", LABELS_URL), *SAMPLES]
    model_path, labels_path, *photo_paths = [
        await download(url, name, on_progress) for name, url in files
    ]
    return await asyncio.to_thread(open_files, model_path, labels_path, photo_paths)


def prepare(img: np.ndarray) -> np.ndarray:
    """The 224x224 RGB square the model reads: short side to 256, center crop, normalized."""
    h, w = img.shape[:2]
    scale = 256 / min(h, w)
    img = cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    h, w = img.shape[:2]
    y, x = (h - 224) // 2, (w - 224) // 2
    img = cv2.cvtColor(img[y : y + 224, x : x + 224], cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    return ((img - MEAN) / STD).transpose(2, 0, 1)[None]  # 1 x 3 x 224 x 224


def top3(
    model: ort.InferenceSession, labels: list[str], img: np.ndarray
) -> tuple[list[tuple[str, float]], float]:
    """The three most likely labels with their probability, and the milliseconds it took."""
    image = prepare(img)
    start = time.perf_counter()
    scores = model.run(None, {"input": image})[0][0]  # one score per label
    ms = (time.perf_counter() - start) * 1000
    chances = np.exp(scores - scores.max())  # softmax: scores to probabilities
    chances /= chances.sum()
    best = chances.argsort()[::-1][:3]
    return [(labels[i][:1].upper() + labels[i][1:], float(chances[i])) for i in best], ms


def pct(p: float) -> str:
    """A probability as a percent, with one more digit below 1%."""
    return f"{p:.1%}" if p >= 0.01 else f"{p:.2%}"


@dataclass
class Guess:
    """One of the three result lines: a label, its percent and a bar."""

    name: ft.Text
    score: ft.Text
    bar: ft.ProgressBar
    view: ft.Column

    def show(self, p: float):
        """Fill the bar and the percent up to p."""
        self.bar.value, self.score.value = p, pct(p)

    def clear(self):
        """Empty the line, while the model works."""
        self.name.value = self.score.value = ""
        self.bar.value = 0


def make_guess(bar_color: str, score_color: str) -> Guess:
    """An empty result line."""
    view = ft.Column(
        spacing=8,
        controls=[
            ft.Row(
                controls=[
                    name := ft.Text(
                        "",
                        size=18,
                        weight=ft.FontWeight.W_700,
                        color=INK,
                        expand=True,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    score := ft.Text("", size=18, weight=ft.FontWeight.W_800, color=score_color),
                ]
            ),
            bar := ft.ProgressBar(
                value=0, bar_height=12, border_radius=6, color=bar_color, bgcolor=LINE
            ),
        ],
    )
    return Guess(name, score, bar, view)


@dataclass
class Tile:
    """A photo under the results, with its best label once the model has read it."""

    frame: ft.Container  # outlined while its photo is the one shown
    name: ft.Text
    score: ft.Text
    view: ft.Column
    photo: Photo | None  # None until the user picks one for the "Your photo" tile


def picture(jpg: bytes) -> ft.Image:
    """A photo filling its tile."""
    return ft.Image(src=jpg, fit=ft.BoxFit.COVER)


def pick_prompt() -> ft.Column:
    """What the "Your photo" tile shows until the user picks a photo."""
    return ft.Column(
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=2,
        controls=[
            ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, color=ACCENT, size=26),
            ft.Text("Your photo", size=12, weight=ft.FontWeight.W_700, color=ACCENT),
        ],
    )


def make_tile(
    photo: Photo | None,
    on_click: ft.ControlEventHandler[ft.Container] | None = None,
    action: ft.PickFiles | None = None,
) -> Tile:
    """A tile for a sample photo, or, without a photo, the "Your photo" tile."""
    view = ft.Column(
        expand=True,
        spacing=2,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            frame := ft.Container(
                height=74,
                border_radius=14,
                bgcolor=SOFT,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                border=ft.Border.all(3, ft.Colors.TRANSPARENT),
                on_click=on_click,
                action=action,
                content=picture(photo[1]) if photo else pick_prompt(),
            ),
            name := ft.Text(
                "",
                size=11,
                weight=ft.FontWeight.W_600,
                color="#374151",
                max_lines=2,  # a phone's tiles are narrow: "Golden retriever" takes two lines
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.CENTER,
            ),
            score := ft.Text(
                "",
                size=14,
                weight=ft.FontWeight.W_800,
                color=ACCENT,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
    )
    tile = Tile(frame, name, score, view, photo)
    frame.data = tile  # a click on the frame finds its tile
    return tile


async def main(page: ft.Page):
    page.title = "Photo labels"
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

    # The first launch downloads the model, its labels and the sample photos.
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
                    ft.Icon(ft.Icons.IMAGE_SEARCH, size=56, color=ACCENT),
                    ft.Text("Photo labels", size=28, weight=ft.FontWeight.W_800, color=INK),
                    loading_status := ft.Text("Opening the model…", size=16, color=MUTED),
                    loading_bar := ft.ProgressBar(
                        bar_height=8, border_radius=4, color=ACCENT, bgcolor=LINE
                    ),
                    loading_size := ft.Text(
                        "MobileNetV2, 14 MB, downloaded once",
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
            model, labels, samples = await load(handle_progress)
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

    labeling = asyncio.Lock()  # one photo at a time
    shown = 0  # photos shown so far: gives each one a new key, so the switcher animates

    async def label(tile: Tile):
        """Show the tile's photo, let the model label it, then grow the three bars."""
        nonlocal shown
        img, jpg = tile.photo
        shown += 1
        photo_view.content = ft.Container(
            key=str(shown), image=ft.DecorationImage(src=jpg, fit=ft.BoxFit.COVER)
        )
        for t in tiles:
            t.frame.border = ft.Border.all(3, ACCENT if t is tile else ft.Colors.TRANSPARENT)
        status.value = "Running MobileNetV2…"
        for guess in guesses:
            guess.clear()
        page.update()

        (top, ms), _ = await asyncio.gather(  # at least 0.6 s: the new photo shows first
            asyncio.to_thread(top3, model, labels, img), asyncio.sleep(0.6)
        )
        status.value = f"Top 3 of 1,000 labels · {ms:.0f} ms"
        for guess, (name, _) in zip(guesses, top):
            guess.name.value = name
        steps = 24
        for step in range(1, steps + 1):  # the bars grow fast, then slow down
            grown = 1 - (1 - step / steps) ** 3
            for guess, (_, p) in zip(guesses, top):
                guess.show(p * grown)
            results.update()
            await asyncio.sleep(0.8 / steps)
        tile.name.value, tile.score.value = top[0][0], pct(top[0][1])
        tile.view.update()

    async def handle_tile_click(e: ft.Event[ft.Container]):
        if not labeling.locked():  # a tap while a photo is being labeled is ignored
            async with labeling:
                await label(e.control.data)

    async def handle_pick_result(e: ft.FilePickerResultEvent):
        if not e.files:  # canceled
            return
        async with labeling:
            try:
                your_tile.photo = await asyncio.to_thread(decode, e.files[0].bytes)
            except ValueError:
                page.show_dialog(ft.SnackBar(f"Can't read {e.files[0].name}: try a JPEG or PNG"))
                return
            your_tile.frame.content = picture(your_tile.photo[1])
            await label(your_tile)

    # Flet drops a service once nothing refers to it: the "Your photo" tile's action keeps it.
    file_picker = ft.FilePicker(on_result=handle_pick_result)
    guesses = [make_guess(*colors) for colors in GUESS_COLORS]
    your_tile = make_tile(
        None,
        # The client opens the picker right in the tap: browsers (iOS Safari above all)
        # open one only while they handle the click. The picked file comes to on_result.
        action=ft.PickFiles(file_picker, file_type=ft.FilePickerFileType.IMAGE, with_data=True),
    )
    tiles = [make_tile(photo, on_click=handle_tile_click) for photo in samples] + [your_tile]

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                max_width=476,  # fills a phone, stays phone-shaped on wide windows
                padding=ft.Padding.only(left=18, right=18, top=8, bottom=10),
                content=ft.Column(
                    expand=True,
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(
                                    "Photo labels", size=28, weight=ft.FontWeight.W_800, color=INK
                                ),
                                ft.Text(
                                    "MobileNetV2 · ONNX Runtime · on device", size=15, color=MUTED
                                ),
                            ],
                        ),
                        ft.Container(
                            expand=True,
                            border_radius=26,
                            bgcolor=SOFT,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            content=(
                                photo_view := ft.AnimatedSwitcher(
                                    duration=450,
                                    transition=ft.AnimatedSwitcherTransition.SCALE,
                                    switch_in_curve=ft.AnimationCurve.EASE_OUT_BACK,
                                    content=ft.Container(
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(
                                            ft.Icons.PHOTO_OUTLINED,
                                            size=64,
                                            color=ft.Colors.GREY_400,
                                        ),
                                    ),
                                )
                            ),
                        ),
                        results := ft.Container(
                            bgcolor="#F8FAFC",
                            border_radius=22,
                            padding=ft.Padding.symmetric(horizontal=18, vertical=16),
                            border=ft.Border.all(1, LINE),
                            content=ft.Column(
                                spacing=14,
                                controls=[
                                    status := ft.Text(
                                        "Tap a photo below, or pick your own",
                                        size=15,
                                        weight=ft.FontWeight.W_600,
                                        color=MUTED,
                                    ),
                                    *[guess.view for guess in guesses],
                                ],
                            ),
                        ),
                        ft.Row(spacing=8, controls=[tile.view for tile in tiles]),
                    ],
                ),
            ),
        )
    )


if __name__ == "__main__":
    ft.run(main)
