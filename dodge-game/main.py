import asyncio
import random
import time

import flet as ft

BOARD_W = 360  # the play area's width; its height fills the screen
LANES = 3
LANE_W = BOARD_W / LANES
PLAYER_W, PLAYER_H, PLAYER_BOTTOM = 70, 26, 36
BLOCK_W, BLOCK_H = LANE_W - 20, 34
START_SPEED, SPEED_UP, MAX_SPEED = 240, 10, 720  # fall speed in px/s, its growth per second, cap
WAVE_GAP = 250  # px between two rows of blocks
BEST_KEY = "dodge.best"

BG, GRID, MUTED, PINK, WHITE = "#0B0A14", "#1C1A2E", "#8D8AA8", "#FF2E88", "#F4F4FF"
COLORS = ["#FF2E88", "#FFB800", "#00E5FF", "#7CFF4F", "#B266FF"]
PLAYER_GLOW = ft.BoxShadow(blur_radius=22, spread_radius=1, color="#AA00E5FF")
CRASH_GLOW = ft.BoxShadow(blur_radius=30, color="#FFFF2E88")
HIT_GLOW = ft.BoxShadow(blur_radius=40, color=ft.Colors.WHITE)
AWAY = (ft.AppLifecycleState.INACTIVE, ft.AppLifecycleState.HIDE, ft.AppLifecycleState.PAUSE)


def lane_left(lane: int, width: float) -> float:
    """The left edge that centers something this wide in a lane."""
    return LANE_W * lane + (LANE_W - width) / 2


def new_wave(seconds: float) -> list[ft.Container]:
    """A row of falling blocks: one block at first, two more and more often, never three."""
    count = 2 if random.random() < min(0.3 + seconds / 60, 0.8) else 1
    color = random.choice(COLORS)
    return [
        ft.Container(
            left=lane_left(lane, BLOCK_W),
            top=-BLOCK_H,
            width=BLOCK_W,
            height=BLOCK_H,
            border_radius=8,
            bgcolor=color,
            shadow=ft.BoxShadow(blur_radius=18, color="#88" + color[1:]),
        )
        for lane in random.sample(range(LANES), count)
    ]


def find_hit(player: ft.Container, blocks: list[ft.Control]) -> ft.Container | None:
    """The block that overlaps the player, if any."""
    for block in blocks:
        if (
            block.top + BLOCK_H > player.top
            and block.top < player.top + PLAYER_H
            and block.left < player.left + PLAYER_W
            and block.left + BLOCK_W > player.left
        ):
            return block
    return None


def label(text: str) -> ft.Text:
    """A small gray caption over a title or a number."""
    return ft.Text(text, size=13, weight=ft.FontWeight.W_800, color=MUTED)


async def main(page: ft.Page):
    page.title = "Dodge"
    page.padding = 0
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    if page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
        how_to = "Drag sideways to dodge the falling blocks."
    else:  # ft.PagePlatform.MACOS, WINDOWS, LINUX, or a browser on a computer
        how_to = "Drag with the mouse, or press ← →, to dodge the falling blocks. Space pauses."

    # Keep the services in variables: Flet drops a service once nothing refers to it.
    prefs = ft.SharedPreferences()  # keeps the best score between launches
    haptics = ft.HapticFeedback()  # a buzz on crash on phones; does nothing elsewhere

    game = {"state": "ready", "best": 0, "board_h": 600.0, "closed": False}

    def show_card(title: str, info: str, action: str, icon: ft.IconData):
        """Fade in the card over the board, with a message and one button."""
        card_title.value, card_info.value = title, info
        card_score.value, card_score.visible = str(game["score"]), True
        card_button.content, card_button.icon = action, icon
        cover.opacity, cover.scale, cover.ignore_interactions = 1, 1, False

    def hide_card():
        """Fade the card out and let drags through to the board."""
        cover.opacity, cover.scale, cover.ignore_interactions = 0, 0.8, True

    def new_game():
        """Clear the board, put the player in the middle lane and start falling."""
        blocks.controls.clear()
        player.left = lane_left(1, PLAYER_W)
        player.bgcolor, player.shadow = WHITE, PLAYER_GLOW
        game.update(state="playing", score=0, seconds=0.0, speed=START_SPEED, fallen=WAVE_GAP)
        score.value, speed.value = "0", "SPEED 1.0×"
        hide_card()
        pause_button.disabled, pause_button.icon = False, ft.Icons.PAUSE_ROUNDED
        page.update()

    def pause():
        """Stop the game where it is and offer to resume."""
        game["state"] = "paused"
        pause_button.icon = ft.Icons.PLAY_ARROW_ROUNDED
        falling = f"{game['seconds']:.1f} s in, falling at {game['speed'] / START_SPEED:.1f}×"
        show_card("PAUSED", falling, "Resume", ft.Icons.PLAY_ARROW_ROUNDED)
        page.update()

    def resume():
        """Hide the card and carry on falling."""
        game["state"] = "playing"
        pause_button.icon = ft.Icons.PAUSE_ROUNDED
        hide_card()
        page.update()

    def handle_play(e: ft.Event[ft.FilledButton] | ft.Event[ft.IconButton] | None = None):
        """The main action: pause or resume a game, or start a new one."""
        if game["state"] == "playing":
            pause()
        elif game["state"] == "paused":
            resume()
        else:
            new_game()

    def step(dt: float):
        """Move one frame: blocks fall by speed × time, the dodged ones score, new rows come in."""
        game["seconds"] += dt
        game["speed"] = min(START_SPEED + SPEED_UP * game["seconds"], MAX_SPEED)
        drop = game["speed"] * dt
        line = player.top + PLAYER_H  # a block that falls past this line is dodged
        for block in blocks.controls:
            if block.top <= line < block.top + drop:
                game["score"] += 1
            block.top += drop
        game["fallen"] += drop
        if game["fallen"] >= WAVE_GAP:  # the last row has fallen far enough: add the next one
            game["fallen"] -= WAVE_GAP
            for block in new_wave(game["seconds"]):
                block.top += game["fallen"]  # it would have fallen that much since it was due
                blocks.controls.append(block)
        blocks.controls = [b for b in blocks.controls if b.top < game["board_h"]]
        score.value = str(game["score"])
        speed.value = f"SPEED {game['speed'] / START_SPEED:.1f}×"

    async def game_over(hit: ft.Container):
        """Light up the crash, save a new best score, then show the card."""
        game["state"] = "over"
        hit.bgcolor, hit.shadow = ft.Colors.WHITE, HIT_GLOW
        player.bgcolor, player.shadow = PINK, CRASH_GLOW
        pause_button.disabled = True
        page.update()
        await haptics.heavy_impact()
        new_best = game["score"] > game["best"]
        if new_best:
            game["best"] = game["score"]
            best.value = f"BEST {game['best']}"
            await prefs.set(BEST_KEY, game["best"])
        await asyncio.sleep(0.35)  # let the crash show before the card covers it
        if game["state"] == "over":  # not restarted in the meantime
            dodged = f"Dodged {game['score']} blocks in {game['seconds']:.1f} s"
            record = "New best!" if new_best else f"Best: {game['best']}"
            show_card("GAME OVER", f"{dodged}\n{record}", "Play again", ft.Icons.REPLAY_ROUNDED)
            page.update()

    async def game_loop():
        """About 30 times a second while a game runs: move, check for a hit, redraw."""
        last = time.monotonic()
        while not game["closed"]:
            await asyncio.sleep(1 / 30)
            now = time.monotonic()
            dt, last = min(now - last, 0.1), now  # a late frame doesn't teleport the blocks
            if game["state"] != "playing":
                continue
            step(dt)
            if hit := find_hit(player, blocks.controls):
                await game_over(hit)
            else:
                page.update()

    def handle_drag_start(e: ft.DragStartEvent[ft.GestureDetector]):
        if game["state"] == "ready":  # the first drag starts the first game
            new_game()

    def handle_drag(e: ft.DragUpdateEvent[ft.GestureDetector]):
        if game["state"] == "playing":  # follow the finger (the loop redraws)
            x = e.local_position.x - PLAYER_W / 2
            player.left = min(max(x, 0), BOARD_W - PLAYER_W)

    def handle_key_down(e: ft.KeyDownEvent):
        if e.key in ("Arrow Left", "Arrow Right") and game["state"] == "playing":
            lane = round((player.left - lane_left(0, PLAYER_W)) / LANE_W)  # the nearest lane
            lane += 1 if e.key == "Arrow Right" else -1
            player.left = lane_left(min(max(lane, 0), LANES - 1), PLAYER_W)
        elif e.key in (" ", "Enter"):
            handle_play()

    def handle_board_size(e: ft.LayoutSizeChangeEvent[ft.Container]):
        game["board_h"] = e.height
        player.top = e.height - PLAYER_BOTTOM - PLAYER_H
        page.update()

    def handle_disconnect(e: ft.Event[ft.Page]):
        if game["state"] == "playing":  # the browser tab was closed
            pause()

    def handle_lifecycle(e: ft.AppLifecycleStateChangeEvent):
        if e.state in AWAY and game["state"] == "playing":  # app hidden or window left
            pause()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.KeyboardListener(
                autofocus=True,  # receives the arrow keys without a click first
                on_key_down=handle_key_down,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            width=BOARD_W,
                            margin=ft.Margin.only(top=8),
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Column(
                                    spacing=0,
                                    controls=[
                                        ft.Text(
                                            "FLET ARCADE",
                                            size=13,
                                            weight=ft.FontWeight.W_800,
                                            color=PINK,
                                        ),
                                        ft.Text(
                                            "Dodge",
                                            size=30,
                                            weight=ft.FontWeight.W_900,
                                            color=WHITE,
                                        ),
                                        speed := label("SPEED 1.0×"),
                                    ],
                                ),
                                ft.Row(
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                    controls=[
                                        ft.Column(
                                            spacing=0,
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            controls=[
                                                label("SCORE"),
                                                score := ft.Text(
                                                    "0",
                                                    size=44,
                                                    weight=ft.FontWeight.W_900,
                                                    color=WHITE,
                                                ),
                                                best := label("BEST 0"),
                                            ],
                                        ),
                                        pause_button := ft.IconButton(
                                            ft.Icons.PAUSE_ROUNDED,
                                            disabled=True,
                                            on_click=handle_play,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ft.Container(
                            width=BOARD_W,
                            expand=True,
                            margin=ft.Margin.only(top=8),
                            border=ft.Border.only(top=ft.BorderSide(1, GRID)),
                            on_size_change=handle_board_size,
                            content=ft.GestureDetector(
                                mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
                                on_horizontal_drag_start=handle_drag_start,
                                on_horizontal_drag_update=handle_drag,
                                content=ft.Stack(
                                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                                    controls=[
                                        *[  # the lines between the lanes
                                            ft.Container(
                                                left=LANE_W * i,
                                                top=0,
                                                bottom=0,
                                                width=1,
                                                bgcolor=GRID,
                                            )
                                            for i in range(1, LANES)
                                        ],
                                        blocks := ft.Stack(left=0, top=0, right=0, bottom=0),
                                        player := ft.Container(
                                            left=lane_left(1, PLAYER_W),
                                            top=game["board_h"] - PLAYER_BOTTOM - PLAYER_H,
                                            width=PLAYER_W,
                                            height=PLAYER_H,
                                            border_radius=9,
                                            bgcolor=WHITE,
                                            shadow=PLAYER_GLOW,
                                        ),
                                        cover := ft.Container(  # covers the board, centers the card
                                            left=0,
                                            top=0,
                                            right=0,
                                            bottom=0,
                                            alignment=ft.Alignment.CENTER,
                                            animate_opacity=300,
                                            animate_scale=ft.Animation(
                                                450, ft.AnimationCurve.EASE_OUT_BACK
                                            ),
                                            content=ft.Container(
                                                width=BOARD_W - 48,
                                                padding=ft.Padding.symmetric(
                                                    horizontal=20, vertical=22
                                                ),
                                                border_radius=28,
                                                bgcolor="#EE171528",
                                                border=ft.Border.all(2, PINK),
                                                shadow=ft.BoxShadow(
                                                    blur_radius=40, color="#66FF2E88"
                                                ),
                                                content=ft.Column(
                                                    tight=True,
                                                    spacing=8,
                                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                    controls=[
                                                        card_title := ft.Text(
                                                            "READY?",
                                                            size=34,
                                                            weight=ft.FontWeight.W_900,
                                                            color=PINK,
                                                        ),
                                                        card_score := ft.Text(
                                                            "0",
                                                            size=64,
                                                            weight=ft.FontWeight.W_900,
                                                            color=WHITE,
                                                            visible=False,
                                                        ),
                                                        card_info := ft.Text(
                                                            how_to,
                                                            size=15,
                                                            color="#B9B6D3",
                                                            text_align=ft.TextAlign.CENTER,
                                                        ),
                                                        card_button := ft.FilledButton(
                                                            "Start",
                                                            icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                                            style=ft.ButtonStyle(
                                                                bgcolor=PINK, color=WHITE
                                                            ),
                                                            on_click=handle_play,
                                                        ),
                                                    ],
                                                ),
                                            ),
                                        ),
                                    ],
                                ),
                            ),
                        ),
                    ],
                ),
            ),
        )
    )

    game["best"] = await prefs.get(BEST_KEY) or 0
    best.value = f"BEST {game['best']}"
    page.update()

    # The loop outlives a closed browser tab: pause the game while the user is away,
    # and stop the loop when the session ends.
    page.on_app_lifecycle_state_change = handle_lifecycle
    page.on_disconnect = handle_disconnect
    page.on_close = lambda e: game.update(closed=True)
    page.run_task(game_loop)


if __name__ == "__main__":
    ft.run(main)
