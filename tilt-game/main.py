import asyncio
import random
import time

import flet as ft

ACCENT, INK, MUTED, GOLD = "#E00050", "#14121C", "#77778A", "#F5B700"
BW, BH, R = 360, 500, 22  # box size and ball radius
STARS = 4
K = 85.0  # how hard a tilt pushes the ball: px/s² per m/s² of tilt
KEY_TILT = 6.0  # the tilt one arrow key gives, in m/s²
ARROWS = {  # arrow key: the accelerometer reading it stands for (x, y)
    "Arrow Left": (KEY_TILT, 0),
    "Arrow Right": (-KEY_TILT, 0),
    "Arrow Up": (0, -KEY_TILT),
    "Arrow Down": (0, KEY_TILT),
}


def star_spots() -> list[tuple[float, float]]:
    """Random star centers, away from the walls, the ball's start and each other."""
    spots = []
    while len(spots) < STARS:
        x, y = random.uniform(R, BW - R), random.uniform(R, BH - R)
        others = spots + [(BW / 2, BH / 2)]
        if all((x - a) ** 2 + (y - b) ** 2 > 110**2 for a, b in others):
            spots.append((x, y))
    return spots


async def main(page: ft.Page):
    page.title = "Tilt to roll"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    phone = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)

    tilt = {"x": 0.0, "y": 0.0, "z": 9.81}  # the latest accelerometer reading
    held = set()  # arrow keys being held down
    state = {"online": True, "closed": False}

    readout = ft.Text(
        "x  0.00   y  0.00   z  9.81",
        size=17,
        weight=ft.FontWeight.W_600,
        font_family="monospace",
        color="#55556A",
    )
    if page.web:
        hint_text = "Tilt your phone, or hold the arrow keys"
    elif phone:
        hint_text = "Tilt the phone to roll the ball"
    else:
        hint_text = "Hold the arrow keys to tilt the box"
    hint = ft.Text(hint_text, size=16, color=MUTED, text_align=ft.TextAlign.CENTER)

    def handle_reading(e: ft.AccelerometerReadingEvent):
        tilt["x"], tilt["y"], tilt["z"] = e.x, e.y, e.z
        state["sensor_works"] = True

    def handle_sensor_error(e: ft.SensorErrorEvent):
        hint.value = "No motion sensor: use the arrow keys"
        page.update()

    # The accelerometer works on Android, iOS and the web; desktops have none.
    # Keep it in `state`: Flet drops a service once nothing refers to it.
    if phone or page.web:
        state["sensor"] = ft.Accelerometer(
            interval=ft.Duration(milliseconds=40),  # 25 readings a second
            on_reading=handle_reading,
            on_error=handle_sensor_error,
        )

    def handle_key_down(e: ft.KeyDownEvent):
        held.add(e.key)
        if e.key in ARROWS and not state.get("sensor_works"):
            hint.value = "No motion sensor: use the arrow keys"

    def handle_key_up(e: ft.KeyUpEvent):
        held.discard(e.key)

    stars = [
        ft.Container(
            width=44,
            height=44,
            alignment=ft.Alignment.CENTER,
            animate_scale=ft.Animation(300, ft.AnimationCurve.EASE_OUT_BACK),
            animate_opacity=300,
            content=ft.Icon(ft.Icons.STAR_ROUNDED, color=GOLD, size=40),
        )
        for _ in range(STARS)
    ]
    ball = ft.Container(
        width=2 * R,
        height=2 * R,
        border_radius=R,
        gradient=ft.RadialGradient(
            center=ft.Alignment(-0.35, -0.35),
            radius=0.9,
            colors=["#FF6FA3", ACCENT],
        ),
        shadow=ft.BoxShadow(blur_radius=12, color="#55E00050", offset=ft.Offset(0, 5)),
    )
    score = ft.Text(f"0 / {STARS}", size=26, weight=ft.FontWeight.W_800, color=ACCENT)
    clock = ft.Text("0.0 s", size=16, color=MUTED, font_family="monospace")
    best = ft.Text("", size=16, color=MUTED)
    game = {}  # the current round: ball position, speed, stars left, start time

    def new_round(e: ft.Event[ft.FilledButton] | None = None):
        """Put the ball in the middle and scatter fresh stars."""
        game.update(x=BW / 2, y=BH / 2, vx=0.0, vy=0.0, start=None)
        game["left"] = star_spots()
        for star, (sx, sy) in zip(stars, game["left"]):
            star.left, star.top = sx - 22, sy - 22
            star.scale, star.opacity = 1, 1
        game["spots"] = list(game["left"])
        game["done"] = False
        score.value, clock.value = f"0 / {STARS}", "0.0 s"
        play_again.visible = False

    def collect(spot: tuple[float, float]):
        """Pop the star at this spot and count it; finish the round on the last."""
        game["left"].remove(spot)
        star = stars[game["spots"].index(spot)]
        star.scale, star.opacity = 1.8, 0
        score.value = f"{STARS - len(game['left'])} / {STARS}"
        if not game["left"]:
            seconds = time.monotonic() - game["start"]
            game["done"] = True
            clock.value = f"{seconds:.1f} s"
            if "best" not in game or seconds < game["best"]:
                game["best"] = seconds
                best.value = f"Best: {seconds:.1f} s"
            play_again.visible = True

    def current_tilt() -> tuple[float, float]:
        """The accelerometer's x and y, plus the tilt of any arrow keys held down."""
        keys = [ARROWS[k] for k in held if k in ARROWS]
        return tilt["x"] + sum(k[0] for k in keys), tilt["y"] + sum(k[1] for k in keys)

    def step(dt: float):
        """Move the ball one frame: the tilt speeds it up, the walls bounce it."""
        ax, ay = current_tilt()
        g = game
        # The ball rolls toward the lower side: a phone tilted right reads a negative x.
        g["vx"] = (g["vx"] - ax * K * dt) * 0.996
        g["vy"] = (g["vy"] + ay * K * dt) * 0.996
        g["x"], g["y"] = g["x"] + g["vx"] * dt, g["y"] + g["vy"] * dt
        if g["start"] is None and abs(g["vx"]) + abs(g["vy"]) > 20:
            g["start"] = time.monotonic()  # the clock runs from the first roll
        if not R <= g["x"] <= BW - R:  # hit a side wall: stop there, bounce a little
            g["x"], g["vx"] = min(max(g["x"], R), BW - R), -g["vx"] * 0.3
        if not R <= g["y"] <= BH - R:
            g["y"], g["vy"] = min(max(g["y"], R), BH - R), -g["vy"] * 0.3
        ball.left, ball.top = g["x"] - R, g["y"] - R
        for sx, sy in list(g["left"]):
            if (g["x"] - sx) ** 2 + (g["y"] - sy) ** 2 < 42**2:
                collect((sx, sy))

    async def game_loop():
        """About 30 times a second: move the ball and redraw."""
        frame = 0
        last = time.monotonic()
        while not state["closed"]:
            await asyncio.sleep(1 / 30)
            now = time.monotonic()
            dt, last = min(now - last, 0.06), now
            if not state["online"]:  # nobody is looking (web tab closed)
                continue
            step(dt)
            frame += 1
            if game["start"] and not game["done"]:
                clock.value = f"{now - game['start']:.1f} s"
            if frame % 3 == 0:  # numbers that change 30 times a second are unreadable
                x, y = current_tilt()
                readout.value = f"x {x:5.2f}   y {y:5.2f}   z {tilt['z']:5.2f}"
            page.update()

    play_again = ft.FilledButton(
        "Play again",
        icon=ft.Icons.REPLAY_ROUNDED,
        visible=False,
        style=ft.ButtonStyle(bgcolor=ACCENT),
        on_click=new_round,
    )
    new_round()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.KeyboardListener(
                autofocus=True,  # receives the arrow keys without a click first
                on_key_down=handle_key_down,
                on_key_up=handle_key_up,
                content=ft.Column(
                    expand=True,
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=BW,
                            margin=ft.Margin.only(top=8),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=0,
                                        controls=[
                                            ft.Text(
                                                "Tilt to roll",
                                                size=30,
                                                color=INK,
                                                weight=ft.FontWeight.W_800,
                                            ),
                                            ft.Row([clock, best], spacing=12),
                                        ],
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(
                                            horizontal=14, vertical=8
                                        ),
                                        border_radius=20,
                                        bgcolor="#FFE6EF",
                                        content=ft.Row(
                                            tight=True,
                                            spacing=6,
                                            controls=[
                                                ft.Icon(
                                                    ft.Icons.STAR_ROUNDED,
                                                    color=ACCENT,
                                                    size=22,
                                                ),
                                                score,
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ),
                        ft.Container(
                            width=BW,
                            height=BH,
                            border_radius=28,
                            bgcolor="#F4F4F8",
                            border=ft.Border.all(3, "#E3E3EC"),
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            content=ft.Stack(
                                width=BW,
                                height=BH,
                                controls=[
                                    *stars,
                                    ball,
                                    ft.Container(  # covers the box, centers the button
                                        left=0,
                                        right=0,
                                        top=0,
                                        bottom=0,
                                        alignment=ft.Alignment.CENTER,
                                        content=play_again,
                                    ),
                                ],
                            ),
                        ),
                        ft.Container(
                            width=BW,
                            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                            border_radius=16,
                            bgcolor="#F4F4F8",
                            content=ft.Column(
                                spacing=2,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[readout, hint],
                            ),
                        ),
                    ],
                ),
            ),
        )
    )

    # The loop outlives a closed browser tab, so pause it while the user is away
    # and stop it when the session ends.
    page.on_disconnect = lambda e: state.update(online=False)
    page.on_connect = lambda e: state.update(online=True)
    page.on_close = lambda e: state.update(closed=True)
    page.run_task(game_loop)


if __name__ == "__main__":
    ft.run(main)
