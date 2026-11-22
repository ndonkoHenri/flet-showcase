import asyncio
import time

import flet as ft
import flet.canvas as cv
import numpy as np

COLS, ROWS = 28, 44  # the board, in cells
BG, DEAD, ALIVE = "#0B1120", "#1B2538", "#4ADE80"
INK, MUTED = "#F8FAFC", "#94A3B8"
EVERY_CELL = [(row, col) for row in range(ROWS) for col in range(COLS)]


def centered(rows: list[str]) -> np.ndarray:
    """A board with this pattern ("#" is a live cell) in the middle."""
    board = np.zeros((ROWS, COLS), dtype=np.uint8)
    top, left = (ROWS - len(rows)) // 2, (COLS - len(rows[0])) // 2
    board[top : top + len(rows), left : left + len(rows[0])] = [
        [char == "#" for char in row] for row in rows
    ]
    return board


PATTERNS = {
    "Glider": centered([".#.", "..#", "###"]),
    "Spaceship": centered([".#..#", "#....", "#...#", "####."]),
    "Pulsar": centered(
        [
            "..###...###..",
            ".............",
            "#....#.#....#",
            "#....#.#....#",
            "#....#.#....#",
            "..###...###..",
            ".............",
            "..###...###..",
            "#....#.#....#",
            "#....#.#....#",
            "#....#.#....#",
            ".............",
            "..###...###..",
        ]
    ),
    "R-pentomino": centered([".##", "##.", ".#."]),
}


def step(grid: np.ndarray) -> np.ndarray:
    """The next generation of a board where 1 is a live cell and 0 a dead one."""
    total = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            total += np.roll(grid, (dy, dx), (0, 1))
    n = total - grid  # live neighbors of each cell
    return (n == 3) | (grid & (n == 2))


def centers(cells: list[tuple[int, int]], view: dict[str, float]) -> list[tuple[float, float]]:
    """Canvas points at the middle of each (row, col)."""
    size, left, top = view["cell"], view["left"], view["top"]
    return [(left + (col + 0.5) * size, top + (row + 0.5) * size) for row, col in cells]


def cell_at(point: ft.Offset, view: dict[str, float]) -> tuple[int, int] | None:
    """The (row, col) under a point of the canvas, or None off the board."""
    if not view["cell"]:  # the canvas hasn't reported its size yet
        return None
    row = int((point.y - view["top"]) // view["cell"])
    col = int((point.x - view["left"]) // view["cell"])
    return (row, col) if 0 <= row < ROWS and 0 <= col < COLS else None


def draw_line(grid: np.ndarray, start: tuple[int, int], end: tuple[int, int], value: int):
    """Set every cell on the straight line from start to end, so a fast drag leaves no gaps."""
    count = max(abs(end[0] - start[0]), abs(end[1] - start[1])) + 1
    rows = np.linspace(start[0], end[0], count).round().astype(int)
    cols = np.linspace(start[1], end[1], count).round().astype(int)
    grid[rows, cols] = value


def square(color: str, size: float) -> ft.Paint:
    """Paint that draws each point as a square a little smaller than a cell."""
    return ft.Paint(color=color, stroke_width=size * 0.85, stroke_cap=ft.StrokeCap.SQUARE)


def number(color: str) -> ft.Text:
    """A big bold number, starting at 0."""
    return ft.Text("0", size=24, weight=ft.FontWeight.W_800, color=color)


def stat(label: str, value: ft.Text) -> ft.Column:
    """A small gray label over a big number."""
    return ft.Column(
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.END,
        controls=[ft.Text(label, size=13, color=MUTED), value],
    )


def button(
    label: str,
    icon: ft.IconData,
    on_click: ft.ControlEventHandler[ft.Button],
    kind: type[ft.Button] = ft.FilledTonalButton,
) -> ft.Button:
    """One of the big buttons under the board."""
    return kind(
        label,
        icon=icon,
        on_click=on_click,
        expand=True,
        height=52,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=6),
            text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_700),
        ),
    )


async def main(page: ft.Page):
    page.title = "Game of Life"
    page.padding = ft.Padding.symmetric(horizontal=16)
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.dark_theme = ft.Theme(color_scheme_seed=ALIVE)
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    if page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
        hint = "Tap or drag to draw cells"
    else:  # ft.PagePlatform.MACOS, WINDOWS, LINUX, or a browser on a computer
        hint = "Click or drag to draw cells"
        if not page.web:
            page.window.width, page.window.height = 420, 860  # phone-shaped

    grid = np.zeros((ROWS, COLS), dtype=np.uint8)
    state = {"gen": 0, "running": False, "online": True, "closed": False}
    view = {"cell": 0.0, "left": 0.0, "top": 0.0}  # cell size and board corner, in canvas px
    drag = {"value": 1, "last": None}  # what a drag draws (1) or erases (0), and its last cell

    def redraw():
        """Show the live cells, the counters and which buttons work now."""
        alive.points = centers(np.argwhere(grid).tolist(), view)
        generation.value = str(state["gen"])
        alive_count.value = str(int(grid.sum()))
        play_button.disabled = not grid.any()  # an empty board stays empty
        step_button.disabled = state["running"] or not grid.any()
        page.update()

    def set_running(running: bool):
        """Start or stop the generations, and switch the Play button."""
        state["running"] = running
        play_button.content = "Pause" if running else "Play"
        play_button.icon = ft.Icons.PAUSE_ROUNDED if running else ft.Icons.PLAY_ARROW_ROUNDED

    def new_board(cells: np.ndarray):
        """Start over from these cells, at generation 0."""
        grid[:] = cells
        state["gen"] = 0
        redraw()

    def handle_canvas_resize(e: cv.CanvasResizeEvent):
        # The board keeps its cells square and centered in whatever room the canvas gets.
        size = min(e.width / COLS, e.height / ROWS)
        view.update(cell=size, left=(e.width - COLS * size) / 2, top=(e.height - ROWS * size) / 2)
        board.points = centers(EVERY_CELL, view)
        board.paint, alive.paint = square(DEAD, size), square(ALIVE, size)
        redraw()

    def draw_to(point: ft.Offset):
        """Draw (or erase) the cells from the drag's last cell to the one under point."""
        if cell := cell_at(point, view):
            draw_line(grid, drag["last"] or cell, cell, drag["value"])
            redraw()
        drag["last"] = cell

    def handle_tap(e: ft.TapEvent):
        if cell := cell_at(e.local_position, view):
            grid[cell] = 1 - grid[cell]
            redraw()

    def handle_pan_down(e: ft.DragDownEvent):
        # A drag starts a few pixels after the finger comes down: remember where it did.
        drag["last"] = cell_at(e.local_position, view)

    def handle_pan_start(e: ft.DragStartEvent):
        cell = drag["last"] or cell_at(e.local_position, view)
        drag["value"] = 1 - grid[cell] if cell else 1  # draw on dead cells, erase from live ones
        draw_to(e.local_position)

    def handle_pan_update(e: ft.DragUpdateEvent):
        draw_to(e.local_position)

    def handle_step(e: ft.Event[ft.FilledTonalButton] | None = None):
        grid[:] = step(grid)
        state["gen"] += 1
        if not grid.any():  # everything died: nothing more will happen
            set_running(False)
        redraw()

    def handle_play_pause(e: ft.Event[ft.FilledButton]):
        set_running(not state["running"])
        redraw()

    def handle_seed(e: ft.Event[ft.FilledTonalButton]):
        new_board(np.random.default_rng().random((ROWS, COLS)) < 0.3)  # 30% of cells alive

    def handle_clear(e: ft.Event[ft.FilledTonalButton]):
        set_running(False)
        new_board(np.zeros_like(grid))

    def handle_pattern(e: ft.Event[ft.PopupMenuItem]):
        new_board(PATTERNS[e.control.data])

    def handle_speed_change(e: ft.Event[ft.Slider]):
        speed_text.value = f"{int(e.control.value)} / s"
        page.update()

    async def life_loop():
        """Make a new generation at the chosen speed while Play is on."""
        while not state["closed"]:
            next_frame = time.monotonic() + 1 / speed.value
            if state["running"] and state["online"]:  # paused while a web tab is closed
                handle_step()
            await asyncio.sleep(next_frame - time.monotonic())  # the rest of this frame

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                max_width=440,  # fills a phone, stays phone-shaped on wide windows
                expand=True,
                spacing=12,
                controls=[
                    ft.Row(
                        margin=ft.Margin.only(top=8),
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=0,
                                controls=[
                                    ft.Text(
                                        "Game of Life",
                                        size=28,
                                        weight=ft.FontWeight.W_800,
                                        color=INK,
                                    ),
                                    ft.Text(hint, size=15, color=MUTED),
                                ],
                            ),
                            ft.Row(
                                spacing=18,
                                controls=[
                                    stat("Generation", generation := number(ALIVE)),
                                    stat("Alive", alive_count := number(INK)),
                                ],
                            ),
                        ],
                    ),
                    cv.Canvas(
                        expand=True,
                        on_resize=handle_canvas_resize,
                        shapes=[
                            board := cv.Points(point_mode=cv.PointMode.POINTS),
                            alive := cv.Points(point_mode=cv.PointMode.POINTS),
                        ],
                        content=ft.GestureDetector(
                            mouse_cursor=ft.MouseCursor.PRECISE,
                            drag_interval=16,  # at most one update every 16 ms, about 60 a second
                            on_tap=handle_tap,
                            on_pan_down=handle_pan_down,
                            on_pan_start=handle_pan_start,
                            on_pan_update=handle_pan_update,
                        ),
                    ),
                    ft.Row(
                        spacing=4,
                        controls=[
                            ft.PopupMenuButton(
                                content=ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                                    border_radius=20,
                                    bgcolor=DEAD,
                                    content=ft.Row(
                                        tight=True,
                                        spacing=6,
                                        controls=[
                                            ft.Icon(ft.Icons.APPS_ROUNDED, size=18, color=INK),
                                            ft.Text("Patterns", weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                ),
                                items=[
                                    ft.PopupMenuItem(name, data=name, on_click=handle_pattern)
                                    for name in PATTERNS
                                ],
                            ),
                            ft.Icon(
                                ft.Icons.SPEED_ROUNDED, color=MUTED, margin=ft.Margin.only(left=8)
                            ),
                            speed := ft.Slider(
                                min=1,
                                max=30,
                                divisions=29,
                                value=10,
                                label="{value} per second",
                                expand=True,
                                on_change=handle_speed_change,
                            ),
                            speed_text := ft.Text(
                                "10 / s", width=44, color=MUTED, weight=ft.FontWeight.W_600
                            ),
                        ],
                    ),
                    ft.Row(
                        margin=ft.Margin.only(bottom=12),
                        spacing=8,
                        controls=[
                            play_button := button(
                                "Play",
                                ft.Icons.PLAY_ARROW_ROUNDED,
                                handle_play_pause,
                                ft.FilledButton,
                            ),
                            step_button := button("Step", ft.Icons.SKIP_NEXT_ROUNDED, handle_step),
                            button("Seed", ft.Icons.SHUFFLE_ROUNDED, handle_seed),
                            button("Clear", ft.Icons.CLEAR_ROUNDED, handle_clear),
                        ],
                    ),
                ],
            ),
        )
    )

    redraw()  # the empty board: Play and Step wait for cells

    # The loop outlives a closed browser tab, so pause it while the user is away
    # and stop it when the session ends.
    page.on_disconnect = lambda e: state.update(online=False)
    page.on_connect = lambda e: state.update(online=True)
    page.on_close = lambda e: state.update(closed=True)
    page.run_task(life_loop)


if __name__ == "__main__":
    ft.run(main)
