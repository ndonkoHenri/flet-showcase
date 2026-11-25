import asyncio
from dataclasses import dataclass
from urllib.parse import quote

import flet as ft

ACCENT = "#E00050"
MUTED = ft.Colors.GREY_700
GREEN, RED = ft.Colors.GREEN_700, ft.Colors.RED_700
CLOSE_AFTER_SECONDS = 5

WEB_PAGE = "https://flet.dev"
EMAIL = (
    f"mailto:hello@example.com?subject={quote('Hello from Flet')}&body={quote('Sent from my app')}"
)
PHONE = "tel:+15550123"
WHATSAPP = "whatsapp://send?text=Hello"  # an app that may not be installed
# The Eiffel Tower: Android's geo: links open any maps app, Apple Maps links open Maps on Apple
# devices, and Google Maps works in every browser.
GEO_MAP = "geo:48.8584,2.2945?q=48.8584,2.2945(Eiffel%20Tower)"
APPLE_MAP = "https://maps.apple.com/?q=Eiffel%20Tower&ll=48.8584,2.2945"
GOOGLE_MAP = "https://www.google.com/maps/search/?api=1&query=48.8584,2.2945"
MAP_URLS = {
    ft.PagePlatform.ANDROID: GEO_MAP,
    ft.PagePlatform.ANDROID_TV: GEO_MAP,
    ft.PagePlatform.IOS: APPLE_MAP,
    ft.PagePlatform.MACOS: APPLE_MAP,
    ft.PagePlatform.WINDOWS: GOOGLE_MAP,
    ft.PagePlatform.LINUX: GOOGLE_MAP,
}

# The ways a web page can open, with a plain label for each.
MODES = {
    ft.LaunchMode.IN_APP_BROWSER_VIEW: "In-app browser view",
    ft.LaunchMode.IN_APP_WEB_VIEW: "In-app web view",
    ft.LaunchMode.EXTERNAL_APPLICATION: "External browser",
    ft.LaunchMode.PLATFORM_DEFAULT: "Platform default",
}

# What a "no" from can_launch_url() means where the app runs.
ANDROID_NOTE = (
    "Android 11+ answers only for schemes the app declares in [tool.flet.android.queries]."
)
CHECK_NOTES = {
    ft.PagePlatform.ANDROID: ANDROID_NOTE,
    ft.PagePlatform.ANDROID_TV: ANDROID_NOTE,
    ft.PagePlatform.IOS: "iOS answers only for schemes the app lists in LSApplicationQueriesSchemes.",
    ft.PagePlatform.MACOS: "macOS says yes when some app handles the URL.",
    ft.PagePlatform.WINDOWS: "Windows says yes when some app is registered for the scheme.",
    ft.PagePlatform.LINUX: "Linux says yes when some app is registered for the scheme.",
}
WEB_CHECK_NOTE = "Browsers can't see your apps: they say yes to http(s), mailto, tel and sms only."


@dataclass
class Link:
    """A link the app hands to the system."""

    title: str
    subtitle: str
    url: str
    icon: ft.IconData
    color: str


def short(url: str) -> str:
    """The URL without its query, short enough for the status bar."""
    return url.split("?")[0]


def icon_tile(icon: ft.IconData, color: str) -> ft.Container:
    """A white icon on a colored rounded square."""
    return ft.Container(
        width=48,
        height=48,
        border_radius=14,
        bgcolor=color,
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(icon, color=ft.Colors.WHITE, size=26),
    )


def section_title(text: str) -> ft.Text:
    """A bold heading over a group of cards."""
    return ft.Text(text, size=18, weight=ft.FontWeight.W_700)


def check_row(url: str, can_open: bool) -> ft.Row:
    """One answer of can_launch_url(): yes or no, and the URL it was about."""
    return ft.Row(
        spacing=8,
        controls=[
            ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if can_open else ft.Icons.CANCEL_ROUNDED,
                color=GREEN if can_open else RED,
                size=20,
            ),
            ft.Text("Yes" if can_open else "No", width=30, weight=ft.FontWeight.W_600),
            ft.Text(
                url,
                size=13,
                font_family="monospace",
                color=MUTED,
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
    )


async def main(page: ft.Page):
    page.title = "Links"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ACCENT, color_scheme=ft.ColorScheme(primary=ACCENT))
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    launcher = ft.UrlLauncher()  # kept here: Flet drops a service nothing refers to
    links = [
        Link("Email", "hello@example.com, with a subject", EMAIL, ft.Icons.MAIL_ROUNDED, "#1A73E8"),
        Link("Phone", "+1 555 0123", PHONE, ft.Icons.CALL_ROUNDED, "#00897B"),
        Link(
            "Map",
            "The Eiffel Tower, Paris",
            GOOGLE_MAP if page.web else MAP_URLS[page.platform],
            ft.Icons.PLACE_ROUNDED,
            "#E65100",
        ),
    ]
    closable: dict[ft.LaunchMode, bool] = {}  # filled after page.add(): it asks the client

    def web_action(url: str) -> ft.OpenUrl | None:
        """In a browser, an OpenUrl action: the client opens the tab inside the click."""
        # Browsers open a new tab only while they handle a click, which is over by the time a
        # call from Python arrives (Safari ignores it). Phones and desktop don't mind.
        return ft.OpenUrl(url) if page.web else None

    def log(text: str, color: str = MUTED):
        """Show the last call and how it went in the bar at the bottom."""
        status.value, status.color = text, color
        page.update()

    async def launch(url: str, mode: ft.LaunchMode):
        """Open `url` in `mode` and log the call and how it went."""
        call = f"launch_url({short(url)}, {mode.name})"
        log(f"{call}…")
        try:
            await launcher.launch_url(
                url, mode=mode, browser_configuration=ft.BrowserConfiguration(show_title=True)
            )
        except RuntimeError as error:  # the client couldn't open it
            log(f"{call} failed: {error}", RED)
        else:
            log(f"{call} ✓", GREEN)

    async def close_soon():
        """Close the in-app view from Python a few seconds after it opened."""
        await asyncio.sleep(CLOSE_AFTER_SECONDS)
        await launcher.close_in_app_web_view()
        log("close_in_app_web_view() ✓ back in the app", GREEN)

    async def open_web_page():
        """Open flet.dev in the picked mode, or in a new tab in a browser."""
        if page.web:  # the click's OpenUrl action has opened it already
            log(f"OpenUrl({WEB_PAGE}) ✓ new tab", GREEN)
            return
        mode = ft.LaunchMode[modes.value]
        if auto_close.value:
            page.run_task(close_soon)
        await launch(WEB_PAGE, mode)

    async def handle_link_click(e: ft.Event[ft.ListTile]):
        """Hand a link to the app that handles it: mail, phone or maps."""
        link: Link = e.control.data
        if page.web:  # the click's OpenUrl action has opened it already
            log(f"OpenUrl({short(link.url)}) ✓", GREEN)
        else:
            await launch(link.url, ft.LaunchMode.EXTERNAL_APPLICATION)

    def update_auto_close():
        """Offer closing from Python only for modes the platform can close."""
        auto_close.disabled = not closable.get(ft.LaunchMode[modes.value], False)
        auto_close.value = auto_close.value and not auto_close.disabled
        page.update()

    async def check(urls: list[str]):
        """Ask can_launch_url() about each URL and list the answers."""
        results.controls = [check_row(url, await launcher.can_launch_url(url)) for url in urls]
        log(f"can_launch_url() ✓ {len(urls)} answer{'s' if len(urls) > 1 else ''}", GREEN)

    async def check_every_link():
        """Check the web page, the three links and an app that may be missing."""
        await check([WEB_PAGE, *[link.url for link in links], WHATSAPP])

    async def check_typed_url():
        """Check the URL typed in the field."""
        if url_field.value.strip():
            await check([url_field.value.strip()])

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                width=440,  # phone-shaped, centered in a wide window
                expand=True,
                spacing=0,
                controls=[
                    ft.ListView(
                        expand=True,
                        spacing=12,
                        padding=ft.Padding.symmetric(horizontal=20, vertical=8),
                        controls=[
                            ft.Text("Links", size=30, weight=ft.FontWeight.W_800),
                            ft.Text(
                                "Open a URL in the app or in the browser", size=16, color=MUTED
                            ),
                            # The web page: pick where it opens.
                            ft.Container(
                                padding=ft.Padding.only(left=8, right=8, bottom=16),
                                border_radius=20,
                                bgcolor=ft.Colors.GREY_100,
                                content=ft.Column(
                                    spacing=4,
                                    controls=[
                                        ft.ListTile(
                                            leading=icon_tile(ft.Icons.WEB_ROUNDED, "#6750A4"),
                                            title=ft.Text("flet.dev", weight=ft.FontWeight.W_700),
                                            subtitle="A web page: where should it open?",
                                        ),
                                        modes := ft.RadioGroup(
                                            value=ft.LaunchMode.PLATFORM_DEFAULT.name,
                                            on_change=update_auto_close,
                                            content=(
                                                mode_radios := ft.Column(
                                                    spacing=0,
                                                    controls=[
                                                        ft.Radio(value=mode.name, label=label)
                                                        for mode, label in MODES.items()
                                                    ],
                                                )
                                            ),
                                        ),
                                        auto_close := ft.Switch(
                                            label=f"Close it from Python after {CLOSE_AFTER_SECONDS} s",
                                            disabled=True,
                                        ),
                                        ft.FilledButton(
                                            "Open flet.dev",
                                            icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
                                            action=web_action(WEB_PAGE),
                                            on_click=open_web_page,
                                        ),
                                    ],
                                ),
                            ),
                            # Links other apps handle.
                            section_title("Hand it to the system"),
                            *[
                                ft.ListTile(
                                    leading=icon_tile(link.icon, link.color),
                                    title=ft.Text(link.title, weight=ft.FontWeight.W_700),
                                    subtitle=link.subtitle,
                                    trailing=ft.Icons.OPEN_IN_NEW_ROUNDED,
                                    bgcolor=ft.Colors.GREY_100,
                                    shape=ft.RoundedRectangleBorder(radius=20),
                                    data=link,
                                    action=web_action(link.url),
                                    on_click=handle_link_click,
                                )
                                for link in links
                            ],
                            # Ask before opening.
                            section_title("Can this be opened?"),
                            ft.Text(
                                WEB_CHECK_NOTE if page.web else CHECK_NOTES[page.platform],
                                size=14,
                                color=MUTED,
                            ),
                            ft.FilledTonalButton(
                                "Check every link",
                                icon=ft.Icons.FACT_CHECK_ROUNDED,
                                on_click=check_every_link,
                            ),
                            ft.Row(
                                controls=[
                                    url_field := ft.TextField(
                                        value="sms:+15550123",
                                        label="Any URL",
                                        dense=True,
                                        expand=True,
                                        autocorrect=False,
                                        keyboard_type=ft.KeyboardType.URL,
                                        on_submit=check_typed_url,
                                    ),
                                    ft.IconButton(
                                        ft.Icons.SEARCH_ROUNDED,
                                        tooltip="Check this URL",
                                        on_click=check_typed_url,
                                    ),
                                ]
                            ),
                            results := ft.Column(spacing=6),
                        ],
                    ),
                    # The last call and how it went.
                    ft.Container(
                        margin=ft.Margin.symmetric(horizontal=12, vertical=8),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        border_radius=16,
                        bgcolor="#FFF0F5",
                        content=ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=ACCENT),
                                status := ft.Text(
                                    "Ready",
                                    size=13,
                                    font_family="monospace",
                                    color=MUTED,
                                    expand=True,
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )
    )

    # Ask the client which modes this platform offers, and which of them it can close.
    for radio in mode_radios.controls:
        mode = ft.LaunchMode[radio.value]
        closable[mode] = await launcher.supports_close_for_launch_mode(mode)
        if not await launcher.supports_launch_mode(mode):
            radio.disabled = True
            radio.label += " (not here)"
    modes.value = next(radio.value for radio in mode_radios.controls if not radio.disabled)
    update_auto_close()


if __name__ == "__main__":
    ft.run(main)
