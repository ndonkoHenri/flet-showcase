import flet as ft
import flet.canvas as cv

PALETTE = [
    ft.Colors.INDIGO_500,
    ft.Colors.PINK_500,
    ft.Colors.AMBER_600,
    ft.Colors.TEAL_500,
    ft.Colors.DEEP_PURPLE_500,
]
SIZES = [4, 9, 18]  # brush widths, in logical pixels
INK, MUTED = ft.Colors.GREY_900, ft.Colors.GREY_600


def pen(color: str, width: float) -> ft.Paint:
    """A brush of the given color and width, with round ends and corners."""
    return ft.Paint(
        color=color,
        stroke_width=width,
        style=ft.PaintingStyle.STROKE,
        stroke_cap=ft.StrokeCap.ROUND,
        stroke_join=ft.StrokeJoin.ROUND,
    )


def color_button(color: str, on_click) -> ft.Container:
    """A round swatch that picks `color`."""
    return ft.Container(
        width=40,
        height=40,
        border_radius=20,
        bgcolor=color,
        data=color,
        animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        on_click=on_click,
    )


def size_button(width: int, on_click) -> ft.Container:
    """A round button showing a dot as wide as the brush it picks."""
    return ft.Container(
        width=44,
        height=44,
        border_radius=22,
        data=width,
        alignment=ft.Alignment.CENTER,
        on_click=on_click,
        content=ft.Container(width=width, height=width, border_radius=width / 2),
    )


def main(page: ft.Page):
    page.title = "Sketch"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    color, width = PALETTE[0], SIZES[1]

    def show_brush():
        """Highlight the picked color and size, and paint the size dots in that color."""
        for button in colors.controls:
            picked = button.data == color
            button.scale = 1.2 if picked else 1
            button.border = ft.Border.all(3, INK if picked else ft.Colors.WHITE)
        for button in sizes.controls:
            button.bgcolor = ft.Colors.GREY_300 if button.data == width else None
            button.content.bgcolor = color
        page.update()

    def show_drawing():
        """Update the point count, the hint and the buttons after the drawing changed."""
        lines = canvas.shapes
        total = sum(len(line.points) for line in lines)
        info.value = f"{len(lines)} lines · {total} points"
        hint.visible = not lines
        undo_button.disabled = recolor_button.disabled = clear_button.disabled = not lines
        page.update()

    def handle_color(e: ft.Event[ft.Container]):
        nonlocal color
        color = e.control.data
        show_brush()

    def handle_size(e: ft.Event[ft.Container]):
        nonlocal width
        width = e.control.data
        show_brush()

    def handle_pan_start(e: ft.DragStartEvent[ft.GestureDetector]):
        line = cv.Points(
            points=[e.local_position], point_mode=cv.PointMode.POLYGON, paint=pen(color, width)
        )
        canvas.shapes.append(line)
        show_drawing()

    def handle_pan_update(e: ft.DragUpdateEvent[ft.GestureDetector]):
        canvas.shapes[-1].points.append(e.local_position)
        show_drawing()

    def handle_pan_end(e: ft.DragEndEvent[ft.GestureDetector]):
        # drag_interval skips moves between updates: end the line where the finger lifted.
        canvas.shapes[-1].points.append(e.local_position)
        show_drawing()

    def handle_tap_up(e: ft.TapEvent[ft.GestureDetector]):
        # A tap draws a dot: in POINTS mode, a round brush paints each point as a circle.
        dot = cv.Points(
            points=[e.local_position], point_mode=cv.PointMode.POINTS, paint=pen(color, width)
        )
        canvas.shapes.append(dot)
        show_drawing()

    def handle_undo(e: ft.Event[ft.IconButton] | None = None):
        if canvas.shapes:
            canvas.shapes.pop()
            show_drawing()

    def handle_recolor(e: ft.Event[ft.IconButton]):
        for line in canvas.shapes:
            line.paint = pen(color, line.paint.stroke_width)
        page.update()

    def handle_clear(e: ft.Event[ft.IconButton]):
        canvas.shapes.clear()
        show_drawing()

    def handle_keyboard_event(e: ft.KeyboardEvent):
        if e.key == "Z" and (e.ctrl or e.meta):  # Ctrl+Z, or Cmd+Z on a Mac
            handle_undo()

    page.on_keyboard_event = handle_keyboard_event

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                width=420,
                padding=ft.Padding.only(left=16, right=16, top=12, bottom=16),
                content=ft.Column(
                    expand=True,
                    spacing=12,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Sketch", size=30, weight=ft.FontWeight.W_800, color=INK),
                                info := ft.Text("0 lines · 0 points", size=15, color=MUTED),
                            ],
                        ),
                        ft.Container(
                            expand=True,
                            border_radius=28,
                            bgcolor=ft.Colors.GREY_50,
                            border=ft.Border.all(1, ft.Colors.GREY_200),
                            # Lines drawn near the edge would spill over the rounded corners.
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            content=(
                                canvas := cv.Canvas(
                                    expand=True,
                                    content=ft.GestureDetector(
                                        mouse_cursor=ft.MouseCursor.PRECISE,
                                        drag_interval=10,  # ms between line updates
                                        on_pan_start=handle_pan_start,
                                        on_pan_update=handle_pan_update,
                                        on_pan_end=handle_pan_end,
                                        on_tap_up=handle_tap_up,
                                        content=ft.Container(
                                            alignment=ft.Alignment.CENTER,
                                            content=(
                                                hint := ft.Text(
                                                    "Draw here", size=18, color=ft.Colors.GREY_400
                                                )
                                            ),
                                        ),
                                    ),
                                )
                            ),
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                            border_radius=30,
                            bgcolor=ft.Colors.GREY_100,
                            content=ft.Column(
                                spacing=6,
                                controls=[
                                    colors := ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[color_button(c, handle_color) for c in PALETTE],
                                    ),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            sizes := ft.Row(
                                                spacing=4,
                                                controls=[
                                                    size_button(s, handle_size) for s in SIZES
                                                ],
                                            ),
                                            ft.Row(
                                                spacing=0,
                                                controls=[
                                                    undo_button := ft.IconButton(
                                                        ft.Icons.UNDO_ROUNDED,
                                                        tooltip="Undo",
                                                        disabled=True,
                                                        on_click=handle_undo,
                                                    ),
                                                    recolor_button := ft.IconButton(
                                                        ft.Icons.FORMAT_COLOR_FILL_ROUNDED,
                                                        tooltip="Recolor every line",
                                                        disabled=True,
                                                        on_click=handle_recolor,
                                                    ),
                                                    clear_button := ft.IconButton(
                                                        ft.Icons.DELETE_OUTLINE_ROUNDED,
                                                        tooltip="Clear",
                                                        disabled=True,
                                                        on_click=handle_clear,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        )
    )

    show_brush()  # the first color and size


if __name__ == "__main__":
    ft.run(main)
