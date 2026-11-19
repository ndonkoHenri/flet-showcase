import asyncio
import io
import os
import sys
from pathlib import Path

import flet as ft
import flet.canvas as cv
from PIL import Image, ImageOps

# Homebrew installs zbar in /opt/homebrew/lib on Apple silicon Macs, where Python doesn't look.
if sys.platform == "darwin":
    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib:/usr/local/lib:/usr/lib")

from pyzbar.pyzbar import Decoded, decode

MAX_SIDE = 1600  # bigger photos are scaled down first: quicker to scan and to show
COLORS = ["#E11D48", "#2563EB", "#059669", "#D97706", "#7C3AED", "#0891B2"]  # code 1, 2, 3...
KINDS = {  # pyzbar's code.type, in words
    "EAN13": "EAN-13 barcode",
    "EAN8": "EAN-8 barcode",
    "UPCA": "UPC-A barcode",
    "UPCE": "UPC-E barcode",
    "ISBN13": "ISBN-13 barcode",
    "ISBN10": "ISBN-10 barcode",
    "CODE128": "Code 128 barcode",
    "CODE39": "Code 39 barcode",
    "QRCODE": "QR code",
}
ACCENT, INK, MUTED, CARD, DARK = "#2563EB", "#14181F", "#667085", "#F2F4F7", "#1D2027"


def open_photo(data: bytes) -> tuple[Image.Image, bytes]:
    """A photo's bytes as an upright Pillow image (scaled down if big) and as JPEG bytes to show."""
    photo = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    photo.thumbnail((MAX_SIDE, MAX_SIDE))
    jpg = io.BytesIO()
    photo.save(jpg, "JPEG", quality=90)
    return photo, jpg.getvalue()


# The sample photo, opened once for every session.
SAMPLE = open_photo((Path(__file__).parent / "assets" / "coffee.jpg").read_bytes())


def scan(photo: Image.Image) -> list[Decoded]:
    """Every code pyzbar finds in the photo, left to right."""
    return sorted(decode(photo), key=lambda code: code.rect.left)


def code_color(i: int) -> str:
    """The color of code i: its outline on the photo and its card in the list."""
    return COLORS[i % len(COLORS)]


def outline(i: int, code: Decoded, scale: float, left: float, top: float) -> list[cv.Shape]:
    """Code i's outline (pyzbar's polygon, moved onto the canvas) and its number at a corner."""
    color = code_color(i)
    points = [(p.x * scale + left, p.y * scale + top) for p in code.polygon]
    elements = [cv.Path.MoveTo(*points[0])]
    elements += [cv.Path.LineTo(*p) for p in points[1:]] + [cv.Path.Close()]
    x, y = min(points, key=lambda p: p[0] + p[1])  # the top-left corner
    return [
        cv.Path(elements, paint=ft.Paint(color=ft.Colors.with_opacity(0.18, color))),
        cv.Path(
            elements,
            paint=ft.Paint(
                color=color,
                stroke_width=4,
                stroke_join=ft.StrokeJoin.ROUND,
                style=ft.PaintingStyle.STROKE,
            ),
        ),
        cv.Circle(x, y, 15, paint=ft.Paint(color="white")),
        cv.Circle(x, y, 13, paint=ft.Paint(color=color)),
        cv.Text(
            x,
            y,
            str(i + 1),
            style=ft.TextStyle(size=15, weight=ft.FontWeight.W_800, color="white"),
            alignment=ft.Alignment.CENTER,
        ),
    ]


def handle_copy_click(e: ft.Event[ft.IconButton]):
    e.page.show_dialog(ft.SnackBar(ft.Text(f"Copied: {e.control.data}"), duration=2000))


def code_card(i: int, code: Decoded) -> ft.Container:
    """Code i in the list: its number and kind, what it says, and buttons to copy or open it."""
    color = code_color(i)
    text = code.data.decode(errors="replace")
    link = text.startswith(("http://", "https://"))
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.07, color),
        border=ft.Border.all(2, color),
        border_radius=18,
        padding=ft.Padding.only(left=12, right=4, top=10, bottom=10),
        content=ft.Row(
            spacing=10,
            controls=[
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=18,
                    bgcolor=color,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(str(i + 1), size=17, weight=ft.FontWeight.W_800, color="white"),
                ),
                ft.Column(
                    spacing=2,
                    expand=True,
                    controls=[
                        ft.Text(
                            KINDS.get(code.type, f"{code.type} code"),
                            size=14,
                            weight=ft.FontWeight.W_700,
                            color=MUTED,
                        ),
                        ft.Text(
                            text,
                            size=16,
                            weight=ft.FontWeight.W_800,
                            color=INK,
                            selectable=True,
                        ),
                    ],
                ),
                ft.IconButton(
                    ft.Icons.CONTENT_COPY_ROUNDED,
                    icon_color=color,
                    tooltip="Copy",
                    data=text,
                    # The client copies inside the tap: browsers allow it only then.
                    action=ft.CopyToClipboard(text),
                    on_click=handle_copy_click,
                ),
                ft.IconButton(
                    ft.Icons.OPEN_IN_NEW_ROUNDED,
                    icon_color=color,
                    tooltip="Open",
                    visible=link,
                    action=ft.OpenUrl(text, target=ft.UrlTarget.BLANK) if link else None,
                ),
            ],
        ),
    )


async def main(page: ft.Page):
    page.title = "Scan a barcode"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme=ft.ColorScheme(primary=ACCENT))
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    W = min(page.width or 400, 500) - 36  # the photo card is W x W
    file_picker = ft.FilePicker()
    shown = {"photo": SAMPLE[0], "codes": [], "size": (W, W)}  # what the canvas shows, its size

    def show_status(icon: ft.IconData, title: str, text: str):
        """The status card: an icon, a title and a line under it."""
        status_icon.icon, status.value, detail.value = icon, title, text
        page.update()

    def set_busy(busy: bool):
        """Turn the photo buttons off while a photo is read."""
        sample_button.disabled = pick_button.disabled = busy
        page.update()

    def draw_codes():
        """Outline the codes read so far, over the photo."""
        w, h = shown["size"]
        pw, ph = shown["photo"].size
        scale = min(w / pw, h / ph)  # the photo is fitted in the card, centered
        left, top = (w - pw * scale) / 2, (h - ph * scale) / 2
        canvas.shapes = [
            shape
            for i, code in enumerate(shown["codes"])
            for shape in outline(i, code, scale, left, top)
        ]

    def handle_canvas_resize(e: cv.CanvasResizeEvent):
        shown["size"] = (e.width, e.height)
        draw_codes()  # keep the outlines on the codes

    async def read(photo: Image.Image, jpg: bytes, label: str):
        """Show a photo, scan it, then outline and list each code found."""
        set_busy(True)
        try:
            shown["photo"], shown["codes"] = photo, []
            photo_view.src, photo_label.value = jpg, label
            canvas.shapes, counter.value = [], "0 found"
            results.controls.clear()
            scan_line.opacity = 1
            scan_line.top = 0 if scan_line.top else shown["size"][1] - 4  # sweep down, or up
            show_status(ft.Icons.DOCUMENT_SCANNER_OUTLINED, "Scanning...", "pyzbar.decode(photo)")

            codes, _ = await asyncio.gather(  # at least 1.3 s: the line sweeps over the photo
                asyncio.to_thread(scan, photo), asyncio.sleep(1.3)
            )
            scan_line.opacity = 0
            for i, code in enumerate(codes):  # one at a time
                shown["codes"].append(code)
                draw_codes()
                results.controls.append(code_card(i, code))
                counter.value = f"{i + 1} found"
                page.update()
                await asyncio.sleep(0.5)
            if codes:
                found = "1 code" if len(codes) == 1 else f"{len(codes)} codes"
                show_status(
                    ft.Icons.CHECK_CIRCLE, f"{found} read", "Copy what a code says, or open it"
                )
            else:
                show_status(
                    ft.Icons.SEARCH_OFF_ROUNDED, "No codes found", "Try a sharper, closer photo"
                )
        finally:
            set_busy(False)

    async def handle_sample_click(e: ft.Event[ft.OutlinedButton] | None = None):
        await read(*SAMPLE, "Sample photo")

    async def handle_pick_click(e: ft.Event[ft.FilledButton]):
        files = await file_picker.pick_files(
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True,  # the bytes, on every platform (the web has no paths)
        )
        if not files:  # canceled
            return
        try:
            photo, jpg = await asyncio.to_thread(open_photo, files[0].bytes)
        except OSError:  # not an image Pillow can open
            show_status(ft.Icons.ERROR_OUTLINE, "Can't open that file", "Try a JPEG or PNG photo")
            return
        await read(photo, jpg, "Your photo")

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                width=W,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(height=4),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=0,
                                controls=[
                                    ft.Text(
                                        "PYZBAR · ON THIS DEVICE",
                                        size=13,
                                        weight=ft.FontWeight.W_800,
                                        color=ACCENT,
                                    ),
                                    ft.Text(
                                        "Scan a barcode",
                                        size=28,
                                        weight=ft.FontWeight.W_900,
                                        color=INK,
                                    ),
                                ],
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                                border_radius=20,
                                bgcolor=ft.Colors.with_opacity(0.12, ACCENT),
                                content=(
                                    counter := ft.Text(
                                        "0 found", size=15, weight=ft.FontWeight.W_700, color=ACCENT
                                    )
                                ),
                            ),
                        ],
                    ),
                    ft.Container(
                        width=W,
                        height=W,
                        border_radius=24,
                        bgcolor=DARK,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Stack(
                            controls=[
                                photo_view := ft.Image(
                                    src=SAMPLE[1],
                                    fit=ft.BoxFit.CONTAIN,
                                    left=0,
                                    top=0,
                                    right=0,
                                    bottom=0,
                                ),
                                # Covers the photo. Its real size can differ from W x W (a narrow
                                # window squeezes the card): the outlines use the size it reports.
                                canvas := cv.Canvas(
                                    left=0, top=0, right=0, bottom=0, on_resize=handle_canvas_resize
                                ),
                                scan_line := ft.Container(
                                    left=0,
                                    right=0,
                                    top=0,
                                    height=4,
                                    opacity=0,
                                    bgcolor=ACCENT,
                                    shadow=ft.BoxShadow(
                                        blur_radius=14,
                                        spread_radius=2,
                                        color=ft.Colors.with_opacity(0.8, ACCENT),
                                    ),
                                    animate_position=ft.Animation(
                                        1300, ft.AnimationCurve.EASE_IN_OUT
                                    ),
                                    animate_opacity=ft.Animation(250),
                                ),
                                ft.Container(
                                    left=0,
                                    right=0,
                                    bottom=10,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=9, vertical=4),
                                        border_radius=10,
                                        bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
                                        content=(
                                            photo_label := ft.Text(
                                                "Sample photo",
                                                size=12,
                                                weight=ft.FontWeight.W_600,
                                                color="white",
                                            )
                                        ),
                                    ),
                                ),
                            ]
                        ),
                    ),
                    ft.Row(
                        spacing=10,
                        controls=[
                            sample_button := ft.OutlinedButton(
                                "Sample photo",
                                icon=ft.Icons.IMAGE_OUTLINED,
                                expand=True,
                                height=46,
                                on_click=handle_sample_click,
                            ),
                            pick_button := ft.FilledButton(
                                "Your photo",
                                icon=ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,
                                expand=True,
                                height=46,
                                on_click=handle_pick_click,
                            ),
                        ],
                    ),
                    ft.Container(
                        bgcolor=CARD,
                        border_radius=18,
                        padding=ft.Padding.symmetric(vertical=12, horizontal=14),
                        content=ft.Row(
                            spacing=14,
                            controls=[
                                status_icon := ft.Icon(
                                    ft.Icons.QR_CODE_SCANNER_ROUNDED, size=28, color=ACCENT
                                ),
                                ft.Column(
                                    spacing=1,
                                    expand=True,
                                    controls=[
                                        status := ft.Text(
                                            "Ready", size=19, weight=ft.FontWeight.W_800, color=INK
                                        ),
                                        detail := ft.Text("", size=15, color=MUTED),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    results := ft.Column(spacing=10),
                    ft.Container(height=4),
                ],
            ),
        )
    )

    await handle_sample_click()


if __name__ == "__main__":
    ft.run(main)
