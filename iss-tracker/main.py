import asyncio
import http.client
import json
import time

import flet as ft
import flet_map as ftm

API = "/v1/satellites/25544"  # 25544 is the ISS's catalog number
ACCENT, INK, MUTED, RED = "#4F46E5", "#14131C", "#6B6A78", "#DC2626"
CLOSE, WORLD = 7.0, 1.5  # map zoom when following the station / showing the trail
LL = ftm.MapLatitudeLongitude

# One kept-alive HTTPS connection: a new TLS handshake for every request can take
# seconds, which would make the station jump instead of moving every second.
connection = http.client.HTTPSConnection("api.wheretheiss.at", timeout=8)


def get_iss(path: str = "") -> dict | list:
    """Ask wheretheiss.at; blocking, so call it with asyncio.to_thread."""
    connection.request("GET", API + path, headers={"User-Agent": "flet-iss-tracker"})
    response = connection.getresponse()
    body = response.read()
    if response.status != 200:  # e.g. 429 when asked too often
        raise OSError(f"HTTP {response.status}")
    return json.loads(body)


async def fetch(path: str = "") -> dict | list | None:
    """get_iss without freezing the app; None when offline or the API is busy."""
    for _ in range(2):  # the server may have closed the idle connection: retry once
        try:
            return await asyncio.to_thread(get_iss, path)
        except (OSError, ValueError, http.client.HTTPException):
            connection.close()  # reconnects on the next request
    return None


def stat(label: str, value: ft.Text) -> ft.Column:
    """A small caption above a value."""
    return ft.Column(
        spacing=0,
        expand=True,
        controls=[
            ft.Text(label, size=12, weight=ft.FontWeight.W_800, color=MUTED),
            value,
        ],
    )


def floating_card(top: bool, controls: list[ft.Control]) -> ft.Container:
    """A white card pinned to the top or the bottom of the screen, over the map."""
    return ft.Container(
        left=0,
        right=0,
        top=0 if top else None,
        bottom=None if top else 0,
        content=ft.SafeArea(
            avoid_intrusions_top=top,
            avoid_intrusions_bottom=not top,
            content=ft.Container(
                margin=ft.Margin.only(
                    left=12, right=12, top=8 if top else 0, bottom=0 if top else 24
                ),
                padding=ft.Padding.symmetric(horizontal=18, vertical=12),
                bgcolor=ft.Colors.WHITE,
                border_radius=24,
                shadow=ft.BoxShadow(blur_radius=18, color="#33000000"),
                content=ft.Column(controls, spacing=0 if top else 10, tight=True),
            ),
        ),
    )


async def main(page: ft.Page):
    page.title = "ISS tracker"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE

    # The position now, and the last 30 minutes (20 points, 90 s apart) for the trail.
    now = await fetch()
    stamps = ",".join(str(int(time.time()) - 90 * k) for k in range(20, 0, -1))
    past = await fetch(f"/positions?units=kilometers&timestamps={stamps}") or []
    first = now["timestamp"] if now else 0
    state = {"follow": False, "flying_until": 0.0, "online": True, "closed": False}

    trail = ftm.PolylineLayer(polylines=[])
    station = ftm.Marker(
        coordinates=LL(0, 0),
        width=48,
        height=48,
        visible=False,
        content=ft.Container(
            border_radius=24,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(3, ACCENT),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.SATELLITE_ALT, color=ACCENT, size=26),
        ),
    )

    def add_point(lat: float, lon: float):
        """Grow the trail; where it crosses the 180° line, end it there and start anew."""
        line = trail.polylines[-1] if trail.polylines else None
        if line and abs(lon - line.coordinates[-1].longitude) <= 180:
            line.coordinates = line.coordinates + [LL(lat, lon)]
            return
        start = []
        if line:  # where the trail meets the 180° line
            prev = line.coordinates[-1]
            edge = 180 if prev.longitude > 0 else -180
            share = (edge - prev.longitude) / (lon + 2 * edge - prev.longitude)
            cross = prev.latitude + (lat - prev.latitude) * share
            line.coordinates = line.coordinates + [LL(cross, edge)]
            start = [LL(cross, -edge)]
        trail.polylines.append(
            ftm.PolylineMarker(
                coordinates=start + [LL(lat, lon)],
                color=ACCENT,
                stroke_width=5,
                border_color=ft.Colors.WHITE,
                border_stroke_width=2,
            )
        )

    unit = ft.TextStyle(size=15, weight=ft.FontWeight.W_700, color=MUTED)
    speed = ft.Text("--", size=24, weight=ft.FontWeight.W_900, color=INK, no_wrap=True)
    altitude = ft.Text(
        "--", size=24, weight=ft.FontWeight.W_900, color=INK, no_wrap=True
    )
    position = ft.Text("--", size=16, weight=ft.FontWeight.W_700, color=INK)
    flown = ft.Text("0 km", size=16, weight=ft.FontWeight.W_700, color=ACCENT)
    status = ft.Text(size=13, weight=ft.FontWeight.W_600, color=MUTED)

    def show(iss: dict):
        """Move the marker, grow the trail and update the numbers."""
        lat, lon = iss["latitude"], iss["longitude"]
        station.coordinates, station.visible = LL(lat, lon), True
        add_point(lat, lon)
        speed.value = f"{iss['velocity']:,.0f}"
        speed.spans = [ft.TextSpan(" km/h", unit)]
        altitude.value = f"{iss['altitude']:,.1f}"
        altitude.spans = [ft.TextSpan(" km", unit)]
        ns, ew = "N" if lat >= 0 else "S", "E" if lon >= 0 else "W"
        position.value = f"{abs(lat):.2f}° {ns}, {abs(lon):.2f}° {ew}"
        flown.value = f"{(iss['timestamp'] - first) * iss['velocity'] / 3600:,.0f} km"
        status.value, status.color = "Live from wheretheiss.at", MUTED

    def overview() -> ftm.MapLatitudeLongitude:
        """The middle of the trail, so all of it fits on screen."""
        points = [p for line in trail.polylines for p in line.coordinates]
        return points[len(points) // 2]

    async def handle_follow_change(e: ft.Event[ft.Switch]):
        state["follow"] = e.control.value
        if station.visible:
            state["flying_until"] = time.monotonic() + 1.7  # let this flight finish
            await my_map.move_to(
                station.coordinates if state["follow"] else overview(),
                zoom=CLOSE if state["follow"] else WORLD,
                animation_duration=ft.Duration(milliseconds=1600),
            )

    async def track():
        """Every second: ask where the station is, show it, and follow it if asked."""
        misses = 0
        while not state["closed"]:
            await asyncio.sleep(1)
            if not state["online"]:  # nobody is looking (web tab closed): don't ask
                continue
            iss = await fetch()
            misses = 0 if iss else misses + 1
            if iss:
                show(iss)
            elif misses >= 2:  # one slow answer is normal; say so when it keeps failing
                status.value, status.color = "No answer from wheretheiss.at...", RED
            page.update()
            if iss and state["follow"] and time.monotonic() > state["flying_until"]:
                page.run_task(  # glide along with the station, without waiting
                    my_map.move_to,
                    station.coordinates,
                    zoom=CLOSE,
                    animation_curve=ft.AnimationCurve.LINEAR,
                    animation_duration=ft.Duration(seconds=1),
                )

    for p in past:
        add_point(p["latitude"], p["longitude"])
    if now:
        show(now)
    else:
        status.value, status.color = "Can't reach wheretheiss.at. Retrying...", RED

    my_map = ftm.Map(
        expand=True,
        initial_center=overview() if trail.polylines else LL(20, 0),
        initial_zoom=WORLD,
        bgcolor="#AAD3DF",
        layers=[
            ftm.TileLayer(
                url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                user_agent_package_name="com.example.iss_tracker",
            ),
            trail,
            ftm.MarkerLayer(markers=[station]),
            ftm.SimpleAttribution(
                text="OpenStreetMap contributors",
                alignment=ft.Alignment.BOTTOM_CENTER,
                bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
                text_style=ft.TextStyle(size=11),
            ),
        ],
    )
    page.add(
        ft.Stack(
            expand=True,
            controls=[
                ft.Container(left=0, right=0, top=0, bottom=0, content=my_map),
                floating_card(
                    top=True,
                    controls=[
                        ft.Text(
                            "LIVE  ·  every second",
                            size=12,
                            color=RED,
                            weight=ft.FontWeight.W_800,
                        ),
                        ft.Text(
                            "Where is the ISS?",
                            size=26,
                            color=INK,
                            weight=ft.FontWeight.W_900,
                        ),
                    ],
                ),
                floating_card(
                    top=False,
                    controls=[
                        ft.Row([stat("SPEED", speed), stat("ALTITUDE", altitude)]),
                        ft.Row(
                            controls=[
                                stat("POSITION", position),
                                stat("FLOWN SINCE OPENED", flown),
                            ]
                        ),
                        ft.Divider(height=1, color="#ECEBF2"),
                        ft.Row(
                            controls=[
                                ft.Container(expand=True, content=status),
                                ft.Switch(
                                    label="Follow",
                                    active_color=ACCENT,
                                    on_change=handle_follow_change,
                                ),
                            ]
                        ),
                    ],
                ),
            ],
        )
    )

    # The loop outlives a closed browser tab, so pause it while the user is away
    # and stop it when the session ends.
    page.on_disconnect = lambda e: state.update(online=False)
    page.on_connect = lambda e: state.update(online=True)
    page.on_close = lambda e: state.update(closed=True)
    page.run_task(track)


if __name__ == "__main__":
    ft.run(main)
