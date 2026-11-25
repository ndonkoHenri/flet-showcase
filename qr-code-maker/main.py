import io
from typing import Any

import flet as ft
import segno
from segno import helpers

COLORS = {"Ink": "#14181F", "Blue": "#2563EB", "Teal": "#0F766E", "Rose": "#BE123C"}
KINDS = {  # what a code can hold: its label, icon and the hint shown while it's empty
    "text": ("Text", ft.Icons.LINK_ROUNDED, "Type text or a link"),
    "wifi": ("Wi-Fi", ft.Icons.WIFI_ROUNDED, "Type the network name"),
    "contact": ("Contact", ft.Icons.PERSON_ROUNDED, "Type a name"),
}
LEVELS = {"L": 7, "M": 15, "Q": 25, "H": 30}  # error correction: % of the code that can be damaged
ACCENT, INK, MUTED, CARD = "#2563EB", "#14181F", "#667085", "#F2F4F7"
QR_SIZE = 240


def make_png(text: str, level: str, color: str) -> tuple[segno.QRCode, bytes]:
    """The QR code for `text` and its PNG bytes (dark modules in `color` on white)."""
    qr = segno.make_qr(text, error=level, boost_error=False)  # exactly the level picked
    buffer = io.BytesIO()
    width = qr.symbol_size()[0]  # in modules, with the quiet zone around the code
    qr.save(buffer, kind="png", scale=max(4, 1000 // width), dark=color)  # ~1000 px wide
    return qr, buffer.getvalue()


# The image needs a valid PNG from the start; it stays hidden until there's something to encode.
FIRST_PNG = make_png("https://flet.dev", "M", INK)[1]


def wifi_data(name: str, password: str, security: str) -> str:
    """What a Wi-Fi code says: phone cameras offer to join the network."""
    if security == "nopass":  # an open network
        return helpers.make_wifi_data(name)
    return helpers.make_wifi_data(name, password or None, security)


def contact_data(name: str, phone: str, email: str) -> str:
    """What a contact code says: a vCard that phone cameras offer to save."""
    *first, last = name.split()  # a vCard name is "Last;First"
    return helpers.make_vcard_data(
        f"{last};{' '.join(first)}", name.strip(), email=email or None, phone=phone or None
    )


def text_field(label: str, icon: ft.IconData, **options: Any) -> ft.TextField:
    """A form field: what's typed goes straight into the code, so no autocorrect."""
    return ft.TextField(
        label=label,
        prefix_icon=icon,
        text_size=16,
        border=ft.OutlineInputBorder(border_radius=14),
        autocorrect=False,
        enable_suggestions=False,
        **options,
    )


def color_chip(name: str, on_click: ft.ControlEventHandler[ft.Chip]) -> ft.Chip:
    """A chip that paints the code in the color `name`."""
    return ft.Chip(
        label=ft.Text(name, size=14, weight=ft.FontWeight.W_600),
        data=name,
        selected=name == "Ink",
        show_checkmark=False,
        selected_color="#DBEAFE",
        label_padding=ft.Padding.only(left=2, right=4),
        leading=ft.Container(width=16, height=16, border_radius=8, bgcolor=COLORS[name]),
        on_click=on_click,
    )


async def main(page: ft.Page):
    page.title = "Make a QR code"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme=ft.ColorScheme(primary=ACCENT))
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    W = min(page.width or 400, 500) - 36  # the column's width
    file_picker = ft.FilePicker()
    share = ft.Share()
    # The share sheet needs a phone app: a browser shares only inside a tap, and desktops have none.
    can_share = not page.web and page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
    shown = {"color": "Ink", "png": FIRST_PNG}

    def code_text() -> str:
        """What the code says, from the form of the chosen kind ("" while it's empty)."""
        kind = kinds.selected[0]
        if kind == "wifi":
            if not wifi_name.value:
                return ""
            return wifi_data(wifi_name.value, wifi_password.value, security.selected[0])
        if kind == "contact":
            if not contact_name.value.strip():
                return ""
            return contact_data(contact_name.value, contact_phone.value, contact_email.value)
        return message.value

    def render():
        """Redraw the code from the form, or say why there's none."""
        _, icon, prompt = KINDS[kinds.selected[0]]
        level, text = levels.selected[0], code_text()
        qr = None
        if text:
            try:
                qr, shown["png"] = make_png(text, level, COLORS[shown["color"]])
            except segno.DataOverflowError:  # more than the biggest QR code (version 40) holds
                pass
        placeholder.visible = qr is None
        qr_image.visible = qr is not None
        save_button.disabled = share_button.disabled = qr is None
        if qr:
            n = qr.symbol_size(border=0)[0]
            qr_image.src = shown["png"]  # PNG bytes
            version.value = f"Version {qr.version}"
            caption.value = f"{n} × {n} modules · survives {LEVELS[level]}% damage"
        else:
            hint.value = "Too long for a QR code" if text else prompt
            version.value = "No code"
            caption.value = "From 21 × 21 modules up to 177 × 177"
        says_icon.icon = icon
        says.value = text.replace("\r\n", "\n").strip() or "Nothing yet"  # vCard lines end in \r\n
        page.update()

    def handle_kind_change(e: ft.Event[ft.SegmentedButton]):
        for form in forms.controls:
            form.visible = form.data == e.control.selected[0]
        render()

    def handle_security_change(e: ft.Event[ft.SegmentedButton]):
        wifi_password.disabled = e.control.selected[0] == "nopass"
        render()

    def handle_color_click(e: ft.Event[ft.Chip]):
        shown["color"] = e.control.data
        for chip in chips.controls:
            chip.selected = chip is e.control
        render()

    async def handle_save_click(e: ft.Event[ft.OutlinedButton]):
        saved = await file_picker.save_file(
            file_name=f"qr-{kinds.selected[0]}.png", src_bytes=shown["png"]
        )
        if saved:  # None when canceled, and on the web, where the browser downloads it
            page.show_dialog(ft.SnackBar("QR code saved"))

    async def handle_share_click(e: ft.Event[ft.FilledButton]):
        png = ft.ShareFile.from_bytes(shown["png"], mime_type="image/png", name="qr-code.png")
        await share.share_files([png])

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                width=W,
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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
                                        "SEGNO · ON THIS DEVICE",
                                        size=13,
                                        weight=ft.FontWeight.W_800,
                                        color=ACCENT,
                                    ),
                                    ft.Text(
                                        "Make a QR code",
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
                                    version := ft.Text(
                                        "No code", size=15, weight=ft.FontWeight.W_700, color=ACCENT
                                    )
                                ),
                            ),
                        ],
                    ),
                    kinds := ft.SegmentedButton(
                        selected=["text"],
                        show_selected_icon=False,
                        on_change=handle_kind_change,
                        segments=[
                            ft.Segment(value=kind, label=label, icon=icon)
                            for kind, (label, icon, _) in KINDS.items()
                        ],
                    ),
                    forms := ft.Column(
                        spacing=10,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            message := text_field(
                                "Text or link", ft.Icons.LINK_ROUNDED, data="text", on_change=render
                            ),
                            ft.Column(
                                data="wifi",
                                visible=False,
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                controls=[
                                    wifi_name := text_field(
                                        "Network name", ft.Icons.WIFI_ROUNDED, on_change=render
                                    ),
                                    wifi_password := text_field(
                                        "Password",
                                        ft.Icons.LOCK_ROUNDED,
                                        password=True,
                                        can_reveal_password=True,
                                        on_change=render,
                                    ),
                                    security := ft.SegmentedButton(
                                        selected=["WPA"],
                                        show_selected_icon=False,
                                        on_change=handle_security_change,
                                        segments=[
                                            ft.Segment(value="WPA", label="WPA/WPA2"),
                                            ft.Segment(value="WEP", label="WEP"),
                                            ft.Segment(value="nopass", label="Open"),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Column(
                                data="contact",
                                visible=False,
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                controls=[
                                    contact_name := text_field(
                                        "Name",
                                        ft.Icons.PERSON_ROUNDED,
                                        capitalization=ft.TextCapitalization.WORDS,
                                        on_change=render,
                                    ),
                                    contact_phone := text_field(
                                        "Phone",
                                        ft.Icons.PHONE_ROUNDED,
                                        keyboard_type=ft.KeyboardType.PHONE,
                                        on_change=render,
                                    ),
                                    contact_email := text_field(
                                        "Email",
                                        ft.Icons.EMAIL_ROUNDED,
                                        keyboard_type=ft.KeyboardType.EMAIL,
                                        on_change=render,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        border_radius=24,
                        bgcolor=CARD,
                        padding=16,
                        content=ft.Column(
                            spacing=10,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=QR_SIZE,
                                    height=QR_SIZE,
                                    border_radius=18,
                                    bgcolor=ft.Colors.WHITE,
                                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Stack(
                                        alignment=ft.Alignment.CENTER,
                                        controls=[
                                            placeholder := ft.Column(
                                                spacing=10,
                                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                controls=[
                                                    ft.Icon(
                                                        ft.Icons.QR_CODE_2_ROUNDED,
                                                        size=110,
                                                        color="#D0D5DD",
                                                    ),
                                                    hint := ft.Text("", size=16, color=MUTED),
                                                ],
                                            ),
                                            qr_image := ft.Image(
                                                src=FIRST_PNG,
                                                width=QR_SIZE,
                                                height=QR_SIZE,
                                                fit=ft.BoxFit.CONTAIN,
                                                gapless_playback=True,  # no blink between keys
                                                filter_quality=ft.FilterQuality.HIGH,
                                                visible=False,
                                            ),
                                        ],
                                    ),
                                ),
                                caption := ft.Text(
                                    "",
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                    color=MUTED,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                    ),
                    ft.Row(
                        spacing=10,
                        controls=[
                            save_button := ft.OutlinedButton(
                                "Save PNG",
                                icon=ft.Icons.DOWNLOAD_ROUNDED,
                                expand=True,
                                height=46,
                                on_click=handle_save_click,
                            ),
                            share_button := ft.FilledButton(
                                "Share",
                                icon=ft.Icons.SHARE_ROUNDED,
                                expand=True,
                                height=46,
                                visible=can_share,
                                on_click=handle_share_click,
                            ),
                        ],
                    ),
                    chips := ft.Row(
                        spacing=6,
                        controls=[color_chip(name, handle_color_click) for name in COLORS],
                    ),
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Error level",
                                size=15,
                                weight=ft.FontWeight.W_600,
                                color=INK,
                                expand=True,
                            ),
                            levels := ft.SegmentedButton(
                                selected=["M"],
                                show_selected_icon=False,
                                on_change=render,
                                segments=[ft.Segment(value=level, label=level) for level in LEVELS],
                            ),
                        ]
                    ),
                    ft.Container(
                        bgcolor=CARD,
                        border_radius=18,
                        padding=ft.Padding.symmetric(vertical=12, horizontal=14),
                        content=ft.Row(
                            spacing=14,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                says_icon := ft.Icon(ft.Icons.LINK_ROUNDED, size=28, color=ACCENT),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(
                                            "What the code says",
                                            size=17,
                                            weight=ft.FontWeight.W_800,
                                            color=INK,
                                        ),
                                        says := ft.Text(
                                            "",
                                            size=14,
                                            color=MUTED,
                                            max_lines=8,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    ft.Container(height=4),
                ],
            ),
        )
    )
    render()


if __name__ == "__main__":
    ft.run(main)
