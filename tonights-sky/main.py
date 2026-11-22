import asyncio
from datetime import UTC, datetime, tzinfo

import flet as ft
import flet.canvas as cv
import flet_geolocator as ftg

from sky import CITIES, city_place, compass, device_place, hm, night_name, night_sky, utc_offset
from sky_map import (
    INK,
    MH,
    MUTED,
    MW,
    marker,
    moon_shapes,
    place_labels,
    sky_background,
    track_elements,
    track_path,
)

BG_TOP, BG_BOTTOM = "#060A1A", "#121B3C"
CARD, CARD_BORDER = "#121A36", "#222D55"
GOLD, WARN = "#FFC56E", "#FFB38A"
DEFAULT_CITY = "Lisbon"  # shown when the device can't say where it is
MY_LOCATION = "here"  # the dropdown option that asks the device


def card(content: ft.Control, padding: ft.PaddingValue, expand: bool = False) -> ft.Container:
    """A rounded card that starts hidden, a little low, and fades in when shown."""
    return ft.Container(
        content=content,
        padding=padding,
        expand=expand,
        bgcolor=CARD,
        border=ft.Border.all(1, CARD_BORDER),
        border_radius=20,
        opacity=0,
        offset=ft.Offset(0, 0.08),
        animate_opacity=ft.Animation(450, ft.AnimationCurve.EASE_OUT),
        animate_offset=ft.Animation(450, ft.AnimationCurve.EASE_OUT),
    )


def time_card(icon: ft.IconData, color: str, label: str, value: ft.Text) -> ft.Container:
    """A card with a small icon and caption above a big time."""
    return card(
        expand=True,
        padding=ft.Padding.all(12),
        content=ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    spacing=6,
                    controls=[
                        ft.Icon(icon, size=18, color=color),
                        ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=MUTED),
                    ],
                ),
                value,
            ],
        ),
    )


def big_time() -> ft.Text:
    """The big time on a time card."""
    return ft.Text("--:--", size=26, weight=ft.FontWeight.W_800, color=INK)


def caption(text: str) -> ft.Text:
    """A small gray all-caps heading."""
    return ft.Text(text, size=12, weight=ft.FontWeight.W_700, color=MUTED)


def body_row(
    body: dict,
    index: int,
    zone: tzinfo,
    selected: bool,
    on_click: ft.ControlEventHandler[ft.Container],
) -> ft.Container:
    """One body's line under the map: when it's up and how high it gets. Tap to pick it."""
    return ft.Container(
        data=index,
        on_click=on_click,
        padding=ft.Padding.symmetric(horizontal=8, vertical=5),
        border_radius=10,
        bgcolor="#24305E" if selected else None,
        content=ft.Row(
            spacing=10,
            controls=[
                ft.Container(width=10, height=10, border_radius=5, bgcolor=body["color"]),
                ft.Text(body["name"], size=16, weight=ft.FontWeight.W_800, color=INK, width=70),
                ft.Text(
                    f"{hm(body['start'], zone)}–{hm(body['end'], zone)}",
                    size=13,
                    color=MUTED,
                    expand=True,
                ),
                ft.Text(
                    f"peaks {body['peak_alt']:.0f}°, {compass(body['peak_az'])}",
                    size=14,
                    weight=ft.FontWeight.W_700,
                    color=INK,
                ),
            ],
        ),
    )


async def main(page: ft.Page):
    page.title = "Tonight's sky"
    page.padding = 0
    page.bgcolor = BG_TOP
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        # Light status bar icons over the night sky on phones.
        system_overlay_style=ft.SystemOverlayStyle(
            status_bar_icon_brightness=ft.Brightness.LIGHT, status_bar_brightness=ft.Brightness.DARK
        )
    )

    # flet-geolocator answers on Android, iOS, macOS, Windows and in browsers, not on Linux.
    can_locate = page.web or page.platform in (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.IOS,
        ft.PagePlatform.MACOS,
        ft.PagePlatform.WINDOWS,
    )
    geo = ftg.Geolocator(
        configuration=ftg.GeolocatorConfiguration(accuracy=ftg.GeolocatorPositionAccuracy.HIGH)
    )
    # place: name, lat, lon, zone and zone_label ("Lisbon time"); sky: the night drawn, once it's
    # all in; days: nights after tonight; selected: index of the picked body.
    view = {"place": None, "days": 0, "sky": None, "selected": None, "generation": 0}

    def draw_tracks():
        """Draw every body's path and dot; with one picked, dim the others."""
        bodies, selected = view["sky"]["bodies"], view["selected"]

        def faded(i: int) -> bool:
            """Whether body i steps back because another one is picked."""
            return selected is not None and i != selected

        # Every path first, then every dot, so no path runs over a dot.
        tracks.shapes = [track_path(b, dim=faded(i)) for i, b in enumerate(bodies)]
        tracks.shapes += [shape for i, b in enumerate(bodies) for shape in marker(b, faded(i))]
        zone = view["place"]["zone"]
        rows.controls = [
            body_row(b, i, zone, i == selected, handle_row_click) for i, b in enumerate(bodies)
        ]
        if selected is None:
            detail.value = (
                "Tap a row to follow its path. The dot is where it's highest: altitude is how far "
                "above the horizon, azimuth the direction from north toward east."
            )
        else:
            b = bodies[selected]
            detail.value = (
                f"{b['name']} is highest at {hm(b['peak_time'], zone)}: {b['peak_alt']:.0f}° above "
                f"the horizon, toward the {compass(b['peak_az'])} (azimuth {b['peak_az']:.0f}°)."
            )
        page.update()

    def handle_row_click(e: ft.Event[ft.Container]):
        if view["sky"] is None:  # still drawing in
            return
        view["selected"] = None if view["selected"] == e.control.data else e.control.data
        draw_tracks()

    async def show_sky():
        """Work out the night for the place and day shown, then reveal it card by card."""
        view["generation"] += 1
        generation = view["generation"]  # a newer call (another city, another night) stops this one
        view["sky"], view["selected"] = None, None
        place, days = view["place"], view["days"]

        async def pause(seconds: float) -> bool:
            """Wait, then tell whether this is still the night to show."""
            await asyncio.sleep(seconds)
            return generation == view["generation"]

        for c in cards:
            c.opacity, c.offset = 0, ft.Offset(0, 0.08)
        night_label.value = night_name(days)
        status.value, spinner.visible = "Reading the sky…", True
        page.update()

        sky = await asyncio.to_thread(night_sky, place["lat"], place["lon"], days)
        if generation != view["generation"]:
            return
        zone = place["zone"]
        when = sky["sunset"] or datetime.now(UTC)
        times_in = (
            f"{place['zone_label']} ({utc_offset(zone, when)})" if place["zone_label"] else "UTC"
        )
        spinner.visible = False
        status.value = f"Night of {sky['date']:%A %d %B} · {times_in}"
        sunset.value, dark.value = hm(sky["sunset"], zone), hm(sky["dusk"], zone)
        sunrise.value = hm(sky["sunrise"], zone)
        moon.shapes = moon_shapes(sky["moon_lit"], sky["waxing"], place["lat"] < 0)
        moon_phase.value = sky["phase"]
        moon_lit.value = f"{sky['moon_lit'] * 100:.0f}% of its face is lit"
        dark_window.value = (
            f"{hm(sky['dusk'], zone)} – {hm(sky['dawn'], zone)}" if sky["dusk"] else ""
        )
        tracks.shapes, rows.controls, detail.value = [], [], ""
        page.update()

        for c in cards:
            if not await pause(0.25):
                return
            c.opacity, c.offset = 1, ft.Offset(0, 0)
            page.update()
        if not sky["bodies"]:
            detail.value = (
                "The sky doesn't get dark enough tonight to see the planets."
                if sky["dusk"] is None
                else "No planets high enough after dark tonight."
            )
            page.update()
            return

        # One body after the other: its path draws in, then its dot, name and row show up.
        place_labels(sky["bodies"])
        for i, b in enumerate(sky["bodies"]):
            path = track_path(b, upto=0)
            tracks.shapes.append(path)
            for k in range(1, 9):  # in 8 steps
                if not await pause(0.04):
                    return
                path.elements = track_elements(b, upto=round(len(b["track"]) * k / 8))
                tracks.update()
            tracks.shapes += marker(b)
            rows.controls.append(body_row(b, i, zone, False, handle_row_click))
            page.update()
        view["sky"] = sky
        draw_tracks()

    async def show_place(place: dict, from_gps: bool):
        """Name the place in the header, with where it is, and show its sky."""
        view["place"] = place
        lat, lon = place["lat"], place["lon"]
        place_icon.icon = ft.Icons.MY_LOCATION_ROUNDED if from_gps else ft.Icons.PLACE_ROUNDED
        place_text.value = (
            f"{place['name']} · {abs(lat):.2f}° {'N' if lat >= 0 else 'S'}, "
            f"{abs(lon):.2f}° {'E' if lon >= 0 else 'W'}"
        )
        await show_sky()

    async def show_city(name: str, note: str = ""):
        """Show the sky over a listed city, with a note saying why, if it wasn't picked."""
        where.value = name
        warning.value, warning.visible = note, bool(note)
        await show_place(city_place(name), from_gps=False)

    async def find_position() -> ftg.GeolocatorPosition | None:
        """A fresh position, else the last one the device knew (browsers keep none)."""
        try:
            return await asyncio.wait_for(geo.get_current_position(), 15)
        except TimeoutError:
            return None if page.web else await geo.get_last_known_position()

    async def show_my_location():
        """Show the sky where the device is, or the default city and why not."""
        where.value = MY_LOCATION
        warning.visible = False
        place_text.value, status.value, spinner.visible = "Finding you…", "", True
        page.update()
        problem = None
        try:
            if not await geo.is_location_service_enabled():
                problem = "Location is turned off on this device"
            else:
                permission = await geo.get_permission_status()
                if permission == ftg.GeolocatorPermissionStatus.DENIED:  # not asked yet
                    permission = await geo.request_permission()
                if permission in (
                    ftg.GeolocatorPermissionStatus.DENIED,
                    ftg.GeolocatorPermissionStatus.DENIED_FOREVER,
                ):
                    problem = "Location isn't allowed for this app"
                elif (position := await find_position()) is None:
                    problem = "No position came in"
        except RuntimeError:  # e.g. no location service on this computer
            problem = "This device can't tell where it is"
        if where.value != MY_LOCATION:  # a city was picked meanwhile
            return
        if problem:
            await show_city(DEFAULT_CITY, f"{problem}, so this is {DEFAULT_CITY}. Pick your city.")
        else:
            await show_place(device_place(position.latitude, position.longitude), from_gps=True)

    async def handle_where_select(e: ft.Event[ft.Dropdown]):
        view["days"] = 0
        if e.control.value == MY_LOCATION:
            await show_my_location()
        else:
            await show_city(e.control.value)

    async def handle_night_click(e: ft.Event[ft.IconButton]):
        if view["place"] is None:  # still finding the device
            return
        view["days"] += e.control.data  # -1 or +1
        await show_sky()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_CENTER,
                    end=ft.Alignment.BOTTOM_CENTER,
                    colors=[BG_TOP, BG_BOTTOM],
                ),
                alignment=ft.Alignment.TOP_CENTER,
                padding=ft.Padding.only(left=16, right=16, top=6, bottom=8),
                content=ft.Column(
                    max_width=420,  # fills a phone, stays phone-shaped on wide windows
                    spacing=10,
                    scroll=ft.ScrollMode.HIDDEN,
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(
                                            "Tonight's sky",
                                            size=28,
                                            weight=ft.FontWeight.W_900,
                                            color=INK,
                                        ),
                                        ft.Row(
                                            spacing=4,
                                            controls=[
                                                place_icon := ft.Icon(
                                                    ft.Icons.PLACE_ROUNDED, size=16, color=GOLD
                                                ),
                                                place_text := ft.Text("", size=15, color=MUTED),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Container(
                                    width=46,
                                    height=46,
                                    border_radius=23,
                                    bgcolor="#1C2650",
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.NIGHTLIGHT_ROUND, color=GOLD, size=24),
                                ),
                            ]
                        ),
                        ft.Row(  # in a Row, expand fills the width
                            controls=[
                                where := ft.Dropdown(
                                    label="Where",
                                    expand=True,
                                    dense=True,
                                    filled=True,
                                    fill_color=CARD,
                                    border_color=CARD_BORDER,
                                    border_radius=14,
                                    menu_height=380,
                                    menu_style=ft.MenuStyle(bgcolor=CARD),
                                    leading_icon=ft.Icons.TRAVEL_EXPLORE_ROUNDED,
                                    on_select=handle_where_select,
                                    options=(
                                        [ft.DropdownOption(key=MY_LOCATION, text="My location")]
                                        if can_locate
                                        else []
                                    )
                                    + [ft.DropdownOption(key=name, text=name) for name in CITIES],
                                )
                            ]
                        ),
                        warning := ft.Text("", size=14, color=WARN, visible=False),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.IconButton(
                                    ft.Icons.CHEVRON_LEFT_ROUNDED,
                                    data=-1,
                                    icon_color=INK,
                                    tooltip="Night before",
                                    on_click=handle_night_click,
                                ),
                                night_label := ft.Text(
                                    "Tonight", size=17, weight=ft.FontWeight.W_800, color=INK
                                ),
                                ft.IconButton(
                                    ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                    data=1,
                                    icon_color=INK,
                                    tooltip="Night after",
                                    on_click=handle_night_click,
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=8,
                            controls=[
                                spinner := ft.ProgressRing(
                                    width=16, height=16, stroke_width=2, color=GOLD
                                ),
                                status := ft.Text("", size=14, color=MUTED, expand=True),
                            ],
                        ),
                        times_row := ft.Row(
                            spacing=10,
                            controls=[
                                time_card(
                                    ft.Icons.WB_TWILIGHT, GOLD, "Sunset", sunset := big_time()
                                ),
                                time_card(
                                    ft.Icons.DARK_MODE_OUTLINED,
                                    "#A9B4FF",
                                    "Dark",
                                    dark := big_time(),
                                ),
                                time_card(
                                    ft.Icons.WB_SUNNY_OUTLINED,
                                    GOLD,
                                    "Sunrise",
                                    sunrise := big_time(),
                                ),
                            ],
                        ),
                        moon_card := card(
                            padding=ft.Padding.only(left=10, right=16, top=6, bottom=6),
                            content=ft.Row(
                                spacing=12,
                                controls=[
                                    moon := cv.Canvas(width=84, height=84),
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            caption("MOON TONIGHT"),
                                            moon_phase := ft.Text(
                                                "", size=21, weight=ft.FontWeight.W_800, color=INK
                                            ),
                                            moon_lit := ft.Text("", size=15, color=MUTED),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        sky_card := card(
                            padding=ft.Padding.only(left=12, right=12, top=10, bottom=12),
                            content=ft.Column(
                                spacing=4,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            caption("MOON AND PLANETS AFTER DARK"),
                                            dark_window := ft.Text(
                                                "", size=13, weight=ft.FontWeight.W_700, color=MUTED
                                            ),
                                        ],
                                    ),
                                    # The stars stay put; only the paths on top are redrawn.
                                    ft.Stack(
                                        width=MW,
                                        height=MH,
                                        controls=[
                                            cv.Canvas(width=MW, height=MH, shapes=sky_background()),
                                            tracks := cv.Canvas(width=MW, height=MH),
                                        ],
                                    ),
                                    rows := ft.Column(spacing=2),
                                    detail := ft.Text("", size=13, color=MUTED),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        )
    )
    cards = [*times_row.controls, moon_card, sky_card]  # they fade in in this order

    if can_locate:
        await show_my_location()
    else:
        await show_city(DEFAULT_CITY)


if __name__ == "__main__":
    ft.run(main)
