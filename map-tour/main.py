import asyncio
import math
from collections.abc import Awaitable, Callable

import flet as ft
import flet_map as ftm

ACCENT, INK, MUTED, LINE, PALE = "#E00050", "#14131C", "#6B6A78", "#ECEBF2", "#FFE6EF"
STOPS = [
    ("Eiffel Tower", ftm.MapLatitudeLongitude(48.8584, 2.2945)),
    ("Arc de Triomphe", ftm.MapLatitudeLongitude(48.8738, 2.2950)),
    ("Louvre", ftm.MapLatitudeLongitude(48.8606, 2.3376)),
    ("Notre-Dame", ftm.MapLatitudeLongitude(48.8530, 2.3499)),
]
LAST = len(STOPS) - 1
CENTER = ftm.MapLatitudeLongitude(48.8634, 2.3222)  # the middle of all the stops
OVERVIEW, LEG, CLOSE = 12.8, 13.2, 15.0  # map zoom: all stops / one leg of the walk / one stop
STEPS = 10  # each leg of the route line grows in this many steps
PAUSE = 1.2  # seconds Play waits at each stop


def km(a: ftm.MapLatitudeLongitude, b: ftm.MapLatitudeLongitude) -> float:
    """The straight-line distance between two points on Earth (haversine formula)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.latitude, a.longitude, b.latitude, b.longitude))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 12742 * math.asin(math.sqrt(h))  # 12742 km: the Earth's diameter


def between(
    a: ftm.MapLatitudeLongitude, b: ftm.MapLatitudeLongitude, t: float
) -> ftm.MapLatitudeLongitude:
    """The point t of the way from a to b (0 is a, 1 is b)."""
    return ftm.MapLatitudeLongitude(
        a.latitude + (b.latitude - a.latitude) * t, a.longitude + (b.longitude - a.longitude) * t
    )


def route_km(last: int) -> float:
    """How long the route is from the first stop to stop number `last`."""
    return sum(km(STOPS[i - 1][1], STOPS[i][1]) for i in range(1, last + 1))


def route_points(stop: int, t: float) -> list[ftm.MapLatitudeLongitude]:
    """The route through the stops before `stop`, then t of the way on to `stop`."""
    spots = [spot for _, spot in STOPS[:stop]]
    return spots + [between(spots[-1], STOPS[stop][1], t)]


def pin(index: int, on_click: ft.ControlEventHandler[ft.Container]) -> ftm.Marker:
    """A stop's numbered pin, hidden until the walk reaches it."""
    return ftm.Marker(
        coordinates=STOPS[index][1],
        width=38,
        height=38,
        visible=False,
        content=ft.Container(
            data=index,
            on_click=on_click,
            border_radius=19,
            bgcolor=ACCENT,
            border=ft.Border.all(3, ft.Colors.WHITE),
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=8, color="#55000000", offset=ft.Offset(0, 2)),
            scale=0,  # grows to 1 when it shows: the pin pops in
            animate_scale=ft.Animation(450, ft.AnimationCurve.EASE_OUT_BACK),
            content=ft.Text(
                str(index + 1), size=16, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE
            ),
        ),
    )


def stop_row(
    index: int, visited: bool, focused: bool, on_click: ft.ControlEventHandler[ft.Container]
) -> ft.Container:
    """A row of the stop list: its number, its name and how far it is from the stop before."""
    name, spot = STOPS[index]
    return ft.Container(
        data=index,
        on_click=on_click,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=12,
        bgcolor=PALE if focused else None,
        content=ft.Row(
            spacing=12,
            controls=[
                ft.Container(
                    width=28,
                    height=28,
                    border_radius=14,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ACCENT if visited else LINE,
                    content=ft.Text(
                        str(index + 1),
                        size=13,
                        weight=ft.FontWeight.W_800,
                        color=ft.Colors.WHITE if visited else MUTED,
                    ),
                ),
                ft.Text(
                    name,
                    expand=True,
                    size=15,
                    weight=ft.FontWeight.W_700 if visited else ft.FontWeight.W_500,
                    color=INK if visited else MUTED,
                ),
                ft.Text(
                    "start" if index == 0 else f"+{km(STOPS[index - 1][1], spot):.1f} km",
                    size=13,
                    color=MUTED,
                ),
            ],
        ),
    )


async def main(page: ft.Page):
    page.title = "Paris in a day"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme = ft.Theme(color_scheme_seed=ACCENT, color_scheme=ft.ColorScheme(primary=ACCENT))
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    phone = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
    # reached: the last stop on the route (-1 before the first); focus: the stop shown, if any;
    # busy: a walk is running (buttons locked); playing: Play goes on to the next stop.
    tour = {"reached": -1, "focus": None, "busy": False, "playing": False}

    def refresh():
        """Show the tour's state: the card, the stop list and which buttons work."""
        reached, focus, busy = tour["reached"], tour["focus"], tour["busy"]
        if focus is not None:
            title.value, subtitle.value = STOPS[focus][0], f"Stop {focus + 1} of {len(STOPS)}"
        elif reached == -1:
            title.value = f"{len(STOPS)} stops across Paris"
            subtitle.value = "Play the tour, or tap a stop"
        elif reached == LAST:
            title.value = "Route ready"
            subtitle.value = f"All {len(STOPS)} stops, as the crow flies"
        else:
            title.value = "The route so far"
            subtitle.value = f"{reached + 1} of {len(STOPS)} stops"
        distance.value = f"{route_km(reached):.1f} km"
        stop_list.controls = [
            stop_row(i, i <= reached, i == focus, handle_stop_click) for i in range(len(STOPS))
        ]
        stop_list.disabled = overview_button.disabled = busy
        previous_button.disabled = reset_button.disabled = busy or reached == -1
        next_button.disabled = busy or reached == LAST
        play_button.disabled = busy and not tour["playing"]  # while Play runs, it is Pause
        if tour["playing"]:
            play_button.content, play_button.icon = "Pause", ft.Icons.PAUSE
        elif reached == LAST:
            play_button.content, play_button.icon = "Play again", ft.Icons.REPLAY
        else:
            play_button.content, play_button.icon = "Play the tour", ft.Icons.PLAY_ARROW
        page.update()

    async def fly(spot: ftm.MapLatitudeLongitude, zoom: float):
        """Move the map to a spot, smoothly."""
        await the_map.move_to(spot, zoom=zoom, cancel_ongoing_animations=True)

    async def show_overview():
        """Zoom out to all the stops."""
        tour["focus"] = None
        refresh()
        await fly(CENTER, OVERVIEW)

    async def draw_leg(stop: int, forward: bool):
        """Grow the route line from the stop before `stop` up to it, or shrink it back."""
        for k in range(1, STEPS + 1):
            route.coordinates = route_points(stop, k / STEPS if forward else 1 - k / STEPS)
            page.update()
            await asyncio.sleep(0.07)

    async def show_pin(stop: int):
        """Pop a stop's pin in."""
        marker = pins.markers[stop]
        marker.visible = True
        page.update()
        await asyncio.sleep(0.05)  # on screen at scale 0 first, so the scale change animates
        marker.content.scale = 1
        page.update()

    def hide_pin(stop: int):
        """Take a stop's pin off the map, ready to pop in again."""
        marker = pins.markers[stop]
        marker.visible, marker.content.scale = False, 0

    async def step_forward():
        """Walk on to the next stop: the line grows, the map follows, and its pin pops in."""
        stop = tour["reached"] + 1
        spot = STOPS[stop][1]
        if stop == 0:
            route.coordinates, route.visible = [spot], True
            await fly(spot, CLOSE)
        else:  # fly to the middle of the leg while the line grows along it
            middle = between(STOPS[stop - 1][1], spot, 0.5)
            await asyncio.gather(fly(middle, LEG), draw_leg(stop, forward=True))
        tour["reached"] = tour["focus"] = stop
        refresh()
        await show_pin(stop)
        if stop == LAST:  # the walk is over: show the whole route
            await asyncio.sleep(PAUSE)
            await show_overview()

    async def step_back():
        """Undo the last stop: its pin goes and the line shrinks back to the stop before."""
        stop = tour["reached"]
        hide_pin(stop)
        if stop == 0:
            route.visible = False
            tour["reached"] = -1
            await show_overview()
            return
        middle = between(STOPS[stop - 1][1], STOPS[stop][1], 0.5)
        await asyncio.gather(fly(middle, LEG), draw_leg(stop, forward=False))
        tour["reached"] = tour["focus"] = stop - 1
        refresh()

    async def walk_to(stop: int):
        """Walk on, stop by stop, until `stop` is on the route."""
        while tour["reached"] < stop:
            await step_forward()

    async def reset():
        """Back to the start: no pins, no route, all of Paris."""
        for stop in range(len(STOPS)):
            hide_pin(stop)
        route.visible = False
        tour["reached"] = -1
        await show_overview()

    async def play():
        """Walk through the stops that are left, pausing at each, until the end or Pause."""
        if tour["reached"] == LAST:
            await reset()
            await asyncio.sleep(0.8)  # let the map settle before the first flight
        while tour["playing"] and tour["reached"] < LAST:
            await step_forward()
            if tour["playing"] and tour["reached"] < LAST:
                await asyncio.sleep(PAUSE)
        tour["playing"] = False

    async def run(action: Callable[[], Awaitable[None]]):
        """Run one walk at a time, with the buttons locked meanwhile."""
        if tour["busy"]:
            return
        tour["busy"] = True
        refresh()
        try:
            await action()
        finally:
            tour["busy"] = False
            refresh()

    async def handle_play_click(e: ft.Event[ft.FilledButton]):
        if tour["playing"]:
            tour["playing"] = False  # Play stops once it reaches the stop it is walking to
            refresh()
        elif not tour["busy"]:
            tour["playing"] = True
            await run(play)

    async def handle_next_click(e: ft.Event[ft.IconButton] | None = None):
        if tour["reached"] < LAST:
            await run(step_forward)

    async def handle_previous_click(e: ft.Event[ft.IconButton] | None = None):
        if tour["reached"] >= 0:
            await run(step_back)

    async def handle_reset_click(e: ft.Event[ft.IconButton]):
        await run(reset)

    async def handle_stop_click(e: ft.Event[ft.Container]):
        """A pin or a list row: fly to a stop on the route, or walk on to a later one."""
        stop = e.control.data
        if tour["busy"]:
            return
        if stop <= tour["reached"]:
            tour["focus"] = stop
            refresh()
            await fly(STOPS[stop][1], CLOSE)
        else:
            await run(lambda: walk_to(stop))

    async def handle_attribution_click(e: ft.Event[ftm.SimpleAttribution]):
        await ft.UrlLauncher().launch_url("https://www.openstreetmap.org/copyright")

    async def handle_keyboard_event(e: ft.KeyboardEvent):
        if e.key == "Arrow Right":
            await handle_next_click()
        elif e.key == "Arrow Left":
            await handle_previous_click()

    page.on_keyboard_event = handle_keyboard_event
    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                width=None if phone else 440,  # phone-shaped on wide windows
                padding=ft.Padding.only(left=14, right=14, top=8, bottom=10),
                content=ft.Column(
                    expand=True,
                    spacing=12,
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Column(
                                    spacing=0,
                                    expand=True,
                                    tight=True,
                                    controls=[
                                        ft.Text(
                                            "Paris in a day",
                                            size=26,
                                            weight=ft.FontWeight.W_900,
                                            color=INK,
                                        ),
                                        ft.Text("flet-map + OpenStreetMap", size=15, color=MUTED),
                                    ],
                                ),
                                overview_button := ft.IconButton(
                                    ft.Icons.ZOOM_OUT_MAP,
                                    icon_color=ACCENT,
                                    bgcolor=PALE,
                                    tooltip="Whole route",
                                    on_click=show_overview,
                                ),
                            ]
                        ),
                        ft.Container(
                            expand=True,
                            border_radius=20,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            border=ft.Border.all(1, LINE),
                            content=(
                                the_map := ftm.Map(
                                    expand=True,
                                    initial_center=CENTER,
                                    initial_zoom=OVERVIEW,
                                    bgcolor="#F2EFE9",  # the color of land on OSM tiles
                                    animation_duration=ft.Duration(milliseconds=800),
                                    # Drag and zoom, but keep north up.
                                    interaction_configuration=ftm.InteractionConfiguration(
                                        flags=ftm.InteractionFlag.ALL & ~ftm.InteractionFlag.ROTATE
                                    ),
                                    layers=[
                                        ftm.TileLayer(
                                            url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                                            user_agent_package_name="com.example.map_tour",
                                        ),
                                        ftm.PolylineLayer(
                                            polylines=[
                                                route := ftm.PolylineMarker(
                                                    coordinates=[STOPS[0][1]],
                                                    visible=False,
                                                    color=ACCENT,
                                                    stroke_width=6,
                                                    border_color=ft.Colors.WHITE,
                                                    border_stroke_width=3,
                                                )
                                            ]
                                        ),
                                        pins := ftm.MarkerLayer(
                                            markers=[
                                                pin(i, handle_stop_click) for i in range(len(STOPS))
                                            ]
                                        ),
                                        ftm.SimpleAttribution(
                                            text="OpenStreetMap contributors",
                                            text_style=ft.TextStyle(size=11, color=INK),
                                            bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
                                            on_click=handle_attribution_click,
                                        ),
                                    ],
                                )
                            ),
                        ),
                        ft.Row(
                            controls=[
                                ft.Column(
                                    spacing=0,
                                    expand=True,
                                    tight=True,
                                    controls=[
                                        title := ft.Text(
                                            size=20, weight=ft.FontWeight.W_800, color=INK
                                        ),
                                        subtitle := ft.Text(size=14, color=MUTED),
                                    ],
                                ),
                                ft.Column(
                                    spacing=0,
                                    tight=True,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    controls=[
                                        ft.Text(
                                            "ROUTE",
                                            size=11,
                                            weight=ft.FontWeight.W_800,
                                            color=MUTED,
                                        ),
                                        distance := ft.Text(
                                            size=20, weight=ft.FontWeight.W_800, color=ACCENT
                                        ),
                                    ],
                                ),
                            ]
                        ),
                        stop_list := ft.Column(spacing=2),
                        ft.Row(
                            controls=[
                                previous_button := ft.IconButton(
                                    ft.Icons.ARROW_BACK,
                                    tooltip="Previous stop",
                                    on_click=handle_previous_click,
                                ),
                                play_button := ft.FilledButton(
                                    "Play the tour",
                                    icon=ft.Icons.PLAY_ARROW,
                                    expand=True,
                                    height=46,
                                    on_click=handle_play_click,
                                ),
                                next_button := ft.IconButton(
                                    ft.Icons.ARROW_FORWARD,
                                    tooltip="Next stop",
                                    on_click=handle_next_click,
                                ),
                                reset_button := ft.IconButton(
                                    ft.Icons.RESTART_ALT,
                                    tooltip="Start over",
                                    on_click=handle_reset_click,
                                ),
                            ]
                        ),
                    ],
                ),
            ),
        )
    )

    refresh()


if __name__ == "__main__":
    ft.run(main)
