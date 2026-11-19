import asyncio
import http.client
import json
import math
import time
import urllib.request
from dataclasses import dataclass

import flet as ft
import flet_map as ftm

FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{magnitude}_{window}.geojson"
WINDOWS = {"hour": "this hour", "day": "today", "week": "this week"}  # ends the title
INK, MUTED, LINE, SELECTED, RED = "#14131C", "#6B6A78", "#ECEBF2", "#FFF1E6", "#DC2626"
ALERT_COLORS = {"green": "#16A34A", "yellow": "#CA8A04", "orange": "#EA580C", "red": RED}
WORLD, CLOSE = 0.55, 4.5  # map zoom for the whole world / for one quake
ROW_HEIGHT = 60  # every list row is this tall, so the list can scroll to row n
TAP_SLOP = 12  # how far (in pixels) outside a circle a tap still picks it
LL = ftm.MapLatitudeLongitude
WORLD_CENTER = LL(15, 10)


@dataclass
class Quake:
    magnitude: float
    place: str
    time: int  # milliseconds since 1970, UTC
    spot: ftm.MapLatitudeLongitude
    depth: float  # km
    felt: int | None  # "Did you feel it?" reports sent to the USGS
    alert: str | None  # PAGER alert level: green, yellow, orange or red
    url: str  # the quake's page on the USGS website


def load_feed(magnitude: str, window: str) -> list[Quake]:
    """Download one USGS feed, strongest first; blocking, so call it with asyncio.to_thread."""
    with urllib.request.urlopen(FEED.format(magnitude=magnitude, window=window), timeout=15) as r:
        feed = json.load(r)
    quakes = []
    for q in feed["features"]:  # USGS GeoJSON
        p = q["properties"]
        if p["mag"] is None:
            continue
        lon, lat, depth = q["geometry"]["coordinates"]
        quakes.append(
            Quake(
                magnitude=p["mag"],
                place=p["place"] or "Unknown place",
                time=p["time"],
                spot=LL(lat, lon),
                depth=depth,
                felt=p["felt"],
                alert=p["alert"],
                url=p["url"],
            )
        )
    return sorted(quakes, key=lambda quake: quake.magnitude, reverse=True)


async def fetch(magnitude: str, window: str) -> list[Quake] | None:
    """load_feed without freezing the app; None when offline or the feed is down."""
    try:
        return await asyncio.to_thread(load_feed, magnitude, window)
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        return None


def color_for(magnitude: float) -> str:
    """Red, orange or yellow: the stronger the quake, the redder."""
    return RED if magnitude >= 4.5 else "#F97316" if magnitude >= 3.5 else "#F59E0B"


def radius(quake: Quake) -> float:
    """The circle's radius in pixels: stronger quakes get much bigger circles."""
    return quake.magnitude**2 / 2


def ago(ms: int) -> str:
    """How long ago a USGS time was, in words."""
    minutes = int((time.time() - ms / 1000) // 60)
    if minutes < 60:
        return f"{max(minutes, 0)} min ago"
    if minutes < 48 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // (24 * 60)} days ago"


def when(ms: int) -> str:
    """A USGS time as a date and a UTC time, the same for everyone wherever the app runs."""
    return time.strftime("%b %d, %H:%M UTC", time.gmtime(ms / 1000)) + f"  ·  {ago(ms)}"


def pixel(spot: ftm.MapLatitudeLongitude, zoom: float) -> tuple[float, float]:
    """Where a point lies on the whole world map at this zoom, in pixels (Web Mercator)."""
    size = 256 * 2**zoom
    x = (spot.longitude + 180) / 360 * size
    y = (1 - math.asinh(math.tan(math.radians(spot.latitude))) / math.pi) / 2 * size
    return x, y


def circle(quake: Quake) -> ftm.CircleMarker:
    """The quake's circle on the map."""
    return ftm.CircleMarker(
        radius=radius(quake),
        coordinates=quake.spot,
        color=color_for(quake.magnitude),
        border_color=ft.Colors.WHITE,
        border_stroke_width=1.5,
    )


def badge(magnitude: float, text: ft.Text | None = None) -> ft.Container:
    """A colored box with the magnitude in it (or with `text`, to change later)."""
    return ft.Container(
        width=50,
        height=42,
        border_radius=12,
        bgcolor=color_for(magnitude),
        alignment=ft.Alignment.CENTER,
        content=text
        or ft.Text(f"{magnitude:.1f}", size=18, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
    )


def quake_row(
    index: int, quake: Quake, on_click: ft.ControlEventHandler[ft.Container]
) -> ft.Container:
    """A list row: magnitude, place and how long ago."""
    return ft.Container(
        data=index,
        margin=ft.Margin.only(bottom=2),
        padding=ft.Padding.symmetric(horizontal=12, vertical=7),
        border_radius=14,
        bgcolor=ft.Colors.WHITE,
        animate=ft.Animation(250),
        on_click=on_click,
        content=ft.Row(
            spacing=12,
            controls=[
                badge(quake.magnitude),
                ft.Column(
                    spacing=0,
                    expand=True,
                    tight=True,
                    controls=[
                        ft.Text(
                            quake.place,
                            size=15,
                            weight=ft.FontWeight.W_700,
                            color=INK,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(ago(quake.time), size=13, color=MUTED),
                    ],
                ),
            ],
        ),
    )


def stat(label: str, value: ft.Text) -> ft.Column:
    """A small caption above a value."""
    return ft.Column(
        spacing=0,
        expand=True,
        controls=[ft.Text(label, size=11, weight=ft.FontWeight.W_800, color=MUTED), value],
    )


async def main(page: ft.Page):
    page.title = "Earthquakes today"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme = ft.Theme(color_scheme_seed=RED)  # red-tinted buttons and spinner
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    phone = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
    state = {"quakes": [], "shown": None}  # shown: the (magnitude, window) on screen

    def set_busy(busy: bool):
        """Lock the buttons and spin while a feed downloads."""
        for control in (window_picker, magnitude_picker, refresh_button):
            control.disabled = busy
        refresh_button.visible, spinner.visible = not busy, busy
        page.update()

    def show_message(icon: ft.IconData, text: str, retry: bool):
        """Show a message instead of the list (offline, or no quakes)."""
        message_icon.icon, message_text.value = icon, text
        retry_button.visible = retry
        message.visible, quake_list.visible = True, False

    def clear_selection():
        """Unhighlight the row, hide the ring and the details."""
        for row in quake_list.controls:
            row.bgcolor = ft.Colors.WHITE
        ring.visible = details.visible = False

    async def select(index: int, scroll_list: bool = False):
        """Highlight the quake's row, show its details, ring it and fly the map there."""
        quake = state["quakes"][index]
        for row in quake_list.controls:
            row.bgcolor = SELECTED if row.data == index else ft.Colors.WHITE
        ring.coordinates, ring.visible = quake.spot, True
        details_badge.bgcolor = color_for(quake.magnitude)
        details_magnitude.value = f"{quake.magnitude:.1f}"
        details_place.value = quake.place
        details_time.value = when(quake.time)
        details_depth.value = f"{quake.depth:.0f} km"
        details_felt.value = f"{quake.felt:,}" if quake.felt else "None"
        details_alert.value = (quake.alert or "none").capitalize()
        details_alert.color = ALERT_COLORS.get(quake.alert, MUTED)
        usgs_link.url = quake.url
        details.visible = True
        page.update()
        if scroll_list:  # picked on the map: bring its row into view too
            page.run_task(quake_list.scroll_to, offset=index * ROW_HEIGHT, duration=400)
        await the_map.move_to(quake.spot, zoom=CLOSE, cancel_ongoing_animations=True)

    async def pop_in(quakes: list[Quake]):
        """Draw the circles in 6 quick batches, weakest first, so the strongest land on top."""
        weakest_first = quakes[::-1]
        batch = len(weakest_first) // 6 + 1
        for start in range(0, len(weakest_first), batch):
            dots.circles.extend(circle(q) for q in weakest_first[start : start + batch])
            page.update()
            await asyncio.sleep(0.2)

    async def load():
        """Download the chosen feed and show it: the circles, the list and the count."""
        magnitude, window = magnitude_picker.selected[0], window_picker.selected[0]
        set_busy(True)
        quakes = await fetch(magnitude, window)
        if quakes is None:
            count.value, count.color = "Can't reach the USGS.", RED
            if state["shown"]:  # keep the last list, and the buttons that match it
                shown_magnitude, shown_window = state["shown"]
                magnitude_picker.selected = [shown_magnitude]
                window_picker.selected = [shown_window]
                count.value += " Showing the last list."
            else:
                show_message(
                    ft.Icons.WIFI_OFF,
                    "Couldn't load the USGS feed.\nCheck the connection and try again.",
                    retry=True,
                )
            set_busy(False)
            return

        state.update(quakes=quakes, shown=(magnitude, window))
        clear_selection()
        title.value = f"Earthquakes {WINDOWS[window]}"
        subtitle.value = f"Magnitude {magnitude} and up, worldwide"
        count.value = f"{len(quakes)} quake{'' if len(quakes) == 1 else 's'}  ·  strongest first"
        count.color = MUTED
        quake_list.controls = [quake_row(i, q, handle_row_click) for i, q in enumerate(quakes)]
        message.visible, quake_list.visible = False, True
        if not quakes:
            show_message(
                ft.Icons.CHECK_CIRCLE_OUTLINE,
                f"No quakes of magnitude {magnitude}+ {WINDOWS[window]}.\n"
                "Try a longer time window.",
                retry=False,
            )
        dots.circles = []
        page.update()
        page.run_task(the_map.move_to, WORLD_CENTER, zoom=WORLD, cancel_ongoing_animations=True)
        await pop_in(quakes)
        set_busy(False)

    async def handle_row_click(e: ft.Event[ft.Container]):
        await select(e.control.data)

    async def handle_map_tap(e: ftm.MapTapEvent):
        """Pick the quake whose circle is under the finger (or the mouse), if any."""
        quakes = state["quakes"]
        if not quakes:
            return
        zoom = (await the_map.get_camera()).zoom
        lon = (e.coordinates.longitude + 180) % 360 - 180  # the map repeats sideways
        tap_x, tap_y = pixel(LL(e.coordinates.latitude, lon), zoom)

        def distance(index: int) -> float:
            x, y = pixel(quakes[index].spot, zoom)
            return math.hypot(x - tap_x, y - tap_y)

        nearest = min(range(len(quakes)), key=distance)
        if distance(nearest) <= radius(quakes[nearest]) + TAP_SLOP:
            await select(nearest, scroll_list=True)

    async def handle_world_click(e: ft.Event[ft.IconButton]):
        clear_selection()
        page.update()
        await the_map.move_to(WORLD_CENTER, zoom=WORLD, cancel_ongoing_animations=True)

    async def handle_filter_change(e: ft.Event[ft.SegmentedButton]):
        await load()

    async def handle_refresh_click(e: ft.Event[ft.IconButton] | ft.Event[ft.Button]):
        await load()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                width=None if phone else 440,  # phone-shaped on wide windows
                padding=ft.Padding.only(left=14, right=14, top=8),
                content=ft.Column(
                    expand=True,
                    spacing=10,
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Column(
                                    spacing=0,
                                    expand=True,  # leaves room for the button
                                    tight=True,
                                    controls=[
                                        ft.Text(
                                            "LIVE FROM USGS",
                                            size=12,
                                            weight=ft.FontWeight.W_800,
                                            color=RED,
                                        ),
                                        title := ft.Text(
                                            "Earthquakes today",
                                            size=25,
                                            weight=ft.FontWeight.W_900,
                                            color=INK,
                                        ),
                                        subtitle := ft.Text(
                                            "Magnitude 2.5 and up, worldwide", size=15, color=MUTED
                                        ),
                                    ],
                                ),
                                ft.Container(
                                    width=48,
                                    height=48,
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Stack(
                                        alignment=ft.Alignment.CENTER,
                                        controls=[
                                            refresh_button := ft.IconButton(
                                                ft.Icons.REFRESH,
                                                icon_color=RED,
                                                bgcolor="#FFE9E9",
                                                tooltip="Refresh",
                                                on_click=handle_refresh_click,
                                            ),
                                            spinner := ft.ProgressRing(
                                                width=26, height=26, color=RED, visible=False
                                            ),
                                        ],
                                    ),
                                ),
                            ]
                        ),
                        ft.Row(
                            spacing=8,
                            controls=[
                                window_picker := ft.SegmentedButton(
                                    expand=True,
                                    show_selected_icon=False,
                                    selected=["day"],
                                    on_change=handle_filter_change,
                                    segments=[
                                        ft.Segment(value="hour", label="Hour"),
                                        ft.Segment(value="day", label="Day"),
                                        ft.Segment(value="week", label="Week"),
                                    ],
                                ),
                                magnitude_picker := ft.SegmentedButton(
                                    show_selected_icon=False,
                                    selected=["2.5"],
                                    on_change=handle_filter_change,
                                    segments=[
                                        ft.Segment(value="2.5", label="2.5+"),
                                        ft.Segment(value="4.5", label="4.5+"),
                                    ],
                                ),
                            ],
                        ),
                        ft.Container(
                            height=300,
                            border_radius=20,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            border=ft.Border.all(1, LINE),
                            content=ft.Stack(
                                expand=True,
                                controls=[
                                    the_map := ftm.Map(
                                        left=0,
                                        top=0,
                                        right=0,
                                        bottom=0,
                                        initial_center=WORLD_CENTER,
                                        initial_zoom=WORLD,
                                        bgcolor="#AAD3DF",
                                        animation_duration=ft.Duration(milliseconds=1300),
                                        # Drag and zoom, but keep north up.
                                        interaction_configuration=ftm.InteractionConfiguration(
                                            flags=ftm.InteractionFlag.ALL
                                            & ~ftm.InteractionFlag.ROTATE
                                        ),
                                        on_tap=handle_map_tap,
                                        layers=[
                                            ftm.TileLayer(
                                                url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                                                user_agent_package_name="com.example.earthquakes_today",
                                            ),
                                            dots := ftm.CircleLayer(circles=[]),
                                            ftm.MarkerLayer(
                                                markers=[
                                                    ring := ftm.Marker(
                                                        coordinates=WORLD_CENTER,
                                                        width=56,
                                                        height=56,
                                                        visible=False,
                                                        content=ft.Container(
                                                            border_radius=28,
                                                            border=ft.Border.all(4, INK),
                                                            bgcolor=ft.Colors.with_opacity(
                                                                0.15, INK
                                                            ),
                                                        ),
                                                    )
                                                ]
                                            ),
                                            ftm.SimpleAttribution(
                                                text="OpenStreetMap contributors",
                                                text_style=ft.TextStyle(size=10, color=INK),
                                                alignment=ft.Alignment.BOTTOM_RIGHT,
                                                bgcolor=ft.Colors.with_opacity(
                                                    0.85, ft.Colors.WHITE
                                                ),
                                            ),
                                        ],
                                    ),
                                    ft.IconButton(
                                        ft.Icons.ZOOM_OUT_MAP,
                                        top=8,
                                        right=8,
                                        icon_color=INK,
                                        bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.WHITE),
                                        tooltip="Whole world",
                                        on_click=handle_world_click,
                                    ),
                                ],
                            ),
                        ),
                        details := ft.Container(
                            visible=False,
                            padding=12,
                            border_radius=16,
                            bgcolor=SELECTED,
                            content=ft.Column(
                                spacing=8,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=12,
                                        controls=[
                                            details_badge := badge(
                                                0,
                                                details_magnitude := ft.Text(
                                                    size=18,
                                                    weight=ft.FontWeight.W_900,
                                                    color=ft.Colors.WHITE,
                                                ),
                                            ),
                                            ft.Column(
                                                spacing=0,
                                                expand=True,
                                                tight=True,
                                                controls=[
                                                    details_place := ft.Text(
                                                        size=15,
                                                        weight=ft.FontWeight.W_700,
                                                        color=INK,
                                                        max_lines=2,
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                    ),
                                                    details_time := ft.Text(size=13, color=MUTED),
                                                ],
                                            ),
                                            ft.IconButton(
                                                ft.Icons.CLOSE,
                                                icon_color=MUTED,
                                                tooltip="Close",
                                                on_click=handle_world_click,
                                            ),
                                        ],
                                    ),
                                    ft.Row(
                                        controls=[
                                            stat(
                                                "DEPTH",
                                                details_depth := ft.Text(
                                                    size=15, weight=ft.FontWeight.W_700, color=INK
                                                ),
                                            ),
                                            stat(
                                                "FELT REPORTS",
                                                details_felt := ft.Text(
                                                    size=15, weight=ft.FontWeight.W_700, color=INK
                                                ),
                                            ),
                                            stat(
                                                "ALERT",
                                                details_alert := ft.Text(
                                                    size=15, weight=ft.FontWeight.W_700
                                                ),
                                            ),
                                            usgs_link := ft.TextButton(
                                                "USGS page",
                                                icon=ft.Icons.OPEN_IN_NEW,
                                                style=ft.ButtonStyle(color=INK),
                                            ),
                                        ]
                                    ),
                                ],
                            ),
                        ),
                        count := ft.Text(
                            "Loading the USGS feed...",
                            size=14,
                            weight=ft.FontWeight.W_700,
                            color=MUTED,
                        ),
                        quake_list := ft.ListView(expand=True, item_extent=ROW_HEIGHT),
                        message := ft.Container(
                            visible=False,
                            expand=True,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Column(
                                tight=True,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    message_icon := ft.Icon(
                                        ft.Icons.WIFI_OFF, size=40, color=MUTED
                                    ),
                                    message_text := ft.Text(
                                        size=16, color=MUTED, text_align=ft.TextAlign.CENTER
                                    ),
                                    retry_button := ft.Button(
                                        "Try again", on_click=handle_refresh_click
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        )
    )

    await load()


if __name__ == "__main__":
    ft.run(main)
