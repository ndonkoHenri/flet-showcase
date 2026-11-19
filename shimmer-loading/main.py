import asyncio
from datetime import datetime

import flet as ft

HERO = ("coast.jpg", "The quiet coast", "A weekend on Kauai's Nā Pali Coast")
ARTICLES = [  # (photo in assets/, title, details)
    ("fjord.jpg", "Fjords, slowly", "8 min read · Travel"),
    ("aurora.jpg", "Chasing polar lights", "6 min read · Nature"),
    ("dunes.jpg", "Summer in the dunes", "4 min read · Travel"),
    ("forest.jpg", "Rest days matter", "3 min read · Life"),
    ("waterfall.jpg", "Where the moss grows", "5 min read · Nature"),
    ("lake.jpg", "Cloud watching", "7 min read · Life"),
]
GRAY = ft.Colors.GREY_300
DIRECTIONS = {  # where the light sweeps to: the icon of its button
    ft.ShimmerDirection.LTR: ft.Icons.ARROW_FORWARD,
    ft.ShimmerDirection.RTL: ft.Icons.ARROW_BACK,
    ft.ShimmerDirection.TTB: ft.Icons.ARROW_DOWNWARD,
    ft.ShimmerDirection.BTT: ft.Icons.ARROW_UPWARD,
}
SPEEDS = {"Slow": 2500, "Normal": 1500, "Fast": 800}  # one sweep, in milliseconds
LOAD_SECONDS = 2.0  # pretend download time of the feed
CARD_GAP_SECONDS = 0.35  # pause between two cards appearing


def bar(width: int, height: int = 14) -> ft.Container:
    """A rounded gray bar standing in for a line of text."""
    return ft.Container(width=width, height=height, bgcolor=GRAY, border_radius=height / 2)


def skeleton(placeholder: ft.Control) -> ft.Shimmer:
    """Sweeps a light across gray placeholder shapes."""
    return ft.Shimmer(base_color=GRAY, highlight_color=ft.Colors.GREY_100, content=placeholder)


def hero_skeleton() -> ft.Shimmer:
    """The gray stand-in for the top story."""
    return skeleton(ft.Container(height=190, border_radius=24, bgcolor=GRAY))


def row_skeleton() -> ft.Shimmer:
    """The gray stand-in for an article: a square photo and three lines."""
    return skeleton(
        ft.Container(
            height=96,
            content=ft.Row(
                spacing=14,
                controls=[
                    ft.Container(width=86, height=86, border_radius=18, bgcolor=GRAY),
                    ft.Column(
                        spacing=10,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[bar(190, 18), bar(140), bar(100)],
                    ),
                ],
            ),
        )
    )


def hero_card() -> ft.Container:
    """The top story: its photo, darkened at the bottom so the white title reads well."""
    photo, title, details = HERO
    return ft.Container(
        height=190,
        border_radius=24,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        image=ft.DecorationImage(src=photo, fit=ft.BoxFit.COVER),
        content=ft.Container(
            padding=18,
            alignment=ft.Alignment.BOTTOM_LEFT,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_CENTER,
                end=ft.Alignment.BOTTOM_CENTER,
                colors=[ft.Colors.TRANSPARENT, ft.Colors.with_opacity(0.55, ft.Colors.BLACK)],
            ),
            content=ft.Column(
                spacing=2,
                tight=True,
                controls=[
                    ft.Text(title, size=26, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                    ft.Text(details, size=16, color=ft.Colors.WHITE),
                ],
            ),
        ),
    )


def row_card(
    article: tuple[str, str, str], saved: bool, on_bookmark: ft.ControlEventHandler[ft.IconButton]
) -> ft.Container:
    """An article: its photo, title, details and a bookmark button."""
    photo, title, details = article
    return ft.Container(
        height=96,
        content=ft.Row(
            spacing=14,
            controls=[
                ft.Container(
                    width=86,
                    height=86,
                    border_radius=18,
                    image=ft.DecorationImage(src=photo, fit=ft.BoxFit.COVER),
                ),
                ft.Column(
                    spacing=4,
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Text(title, size=19, weight=ft.FontWeight.W_700),
                        ft.Text(details, size=15, color=ft.Colors.GREY_600),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.BOOKMARK_BORDER_ROUNDED,
                    selected_icon=ft.Icons.BOOKMARK_ROUNDED,
                    selected=saved,
                    icon_color=ft.Colors.GREY_500,
                    selected_icon_color=ft.Colors.BLUE_700,
                    tooltip="Save for later",
                    data=title,
                    on_click=on_bookmark,
                ),
            ],
        ),
    )


def slot(content: ft.Control) -> ft.AnimatedSwitcher:
    """A place in the feed that fades from one content to the next."""
    return ft.AnimatedSwitcher(
        content=content,
        duration=500,
        reverse_duration=250,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
    )


async def main(page: ft.Page):
    page.title = "Today"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ft.Colors.WHITE
    page.padding = 0
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # Pulling is a touch gesture: mouse drags and the mouse wheel don't start it.
    # So desktop and web also get a Refresh button.
    is_phone = not page.web and page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
    loading = False
    saved = set()  # titles of the bookmarked articles

    def style(shimmer: ft.Shimmer) -> ft.Shimmer:
        """Gives a skeleton the sweep direction and speed picked at the bottom."""
        shimmer.direction = ft.ShimmerDirection(direction_picker.selected[0])
        shimmer.period = SPEEDS[speed_picker.selected[0]]
        return shimmer

    async def load():
        """Shows the skeletons, then swaps in each card as if it had just downloaded."""
        nonlocal loading
        loading = True
        status.value = "Loading…"
        refresh_button.disabled = True
        hero.content = style(hero_skeleton())
        for row in rows:
            row.content = style(row_skeleton())
        page.update()

        await asyncio.sleep(LOAD_SECONDS)
        hero.content = hero_card()
        page.update()
        for row, article in zip(rows, ARTICLES):
            await asyncio.sleep(CARD_GAP_SECONDS)
            row.content = row_card(article, article[1] in saved, handle_bookmark_click)
            page.update()

        loading = False
        status.value = f"Updated {datetime.now():%H:%M}"
        refresh_button.disabled = False
        page.update()

    async def handle_refresh(e: ft.Event[ft.RefreshIndicator]):
        """Runs on a pull (or a Refresh click); the spinner turns until the feed is in."""
        if not loading:
            await load()

    async def handle_refresh_click(e: ft.Event[ft.IconButton]):
        """Starts a refresh from code: same spinner and handler as a pull."""
        await indicator.show()

    async def handle_sweep_change(e: ft.Event[ft.SegmentedButton]):
        """Restyles the skeletons on screen, or reloads the feed to show the new sweep."""
        if not loading:
            await load()
            return
        for place in [hero, *rows]:
            if isinstance(place.content, ft.Shimmer):  # its card hasn't arrived yet
                style(place.content)
        page.update()

    def handle_bookmark_click(e: ft.Event[ft.IconButton]):
        """Saves an article for later, or unsaves it; reloads keep the choice."""
        e.control.selected = not e.control.selected
        if e.control.selected:
            saved.add(e.control.data)
        else:
            saved.discard(e.control.data)

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                max_width=480,  # keeps the phone-like layout in a wide desktop window
                padding=ft.Padding.only(left=20, right=20, top=12, bottom=8),
                content=ft.Column(
                    expand=True,
                    spacing=12,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Today", size=30, weight=ft.FontWeight.W_800),
                                ft.Row(
                                    spacing=4,
                                    controls=[
                                        status := ft.Text(size=16, color=ft.Colors.GREY_600),
                                        refresh_button := ft.IconButton(
                                            icon=ft.Icons.REFRESH,
                                            tooltip="Refresh",
                                            visible=not is_phone,
                                            on_click=handle_refresh_click,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        indicator := ft.RefreshIndicator(
                            expand=True,
                            on_refresh=handle_refresh,
                            content=ft.ListView(
                                spacing=14,
                                controls=[
                                    hero := slot(hero_skeleton()),
                                    ft.Text("For you", size=22, weight=ft.FontWeight.W_800),
                                    *(rows := [slot(row_skeleton()) for _ in ARTICLES]),
                                ],
                            ),
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Sweep", weight=ft.FontWeight.W_600),
                                direction_picker := ft.SegmentedButton(
                                    selected=[ft.ShimmerDirection.LTR.value],
                                    show_selected_icon=False,
                                    on_change=handle_sweep_change,
                                    segments=[
                                        ft.Segment(value=direction.value, icon=icon)
                                        for direction, icon in DIRECTIONS.items()
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Speed", weight=ft.FontWeight.W_600),
                                speed_picker := ft.SegmentedButton(
                                    selected=["Normal"],
                                    show_selected_icon=False,
                                    on_change=handle_sweep_change,
                                    segments=[ft.Segment(value=s, label=s) for s in SPEEDS],
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        )
    )
    await load()


if __name__ == "__main__":
    ft.run(main)
