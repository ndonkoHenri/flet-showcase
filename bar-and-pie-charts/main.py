import asyncio

import flet as ft
import flet_charts as fch

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CHANNELS = {
    "Store": ft.Colors.INDIGO_400,
    "Partners": ft.Colors.PINK_400,
    "App": ft.Colors.TEAL_400,
    "Phone": ft.Colors.AMBER_500,
}
# Sales in thousands of dollars from Monday to Sunday, and each channel's share in percent.
REGIONS = {
    "North": {
        "color": ft.Colors.INDIGO_500,
        "sales": [42, 55, 48, 63, 71, 88, 60],
        "share": [45, 25, 18, 12],
    },
    "South": {
        "color": ft.Colors.PINK_500,
        "sales": [30, 38, 61, 52, 79, 95, 84],
        "share": [28, 40, 20, 12],
    },
    "Online": {
        "color": ft.Colors.TEAL_500,
        "sales": [70, 64, 72, 58, 66, 52, 49],
        "share": [15, 22, 48, 15],
    },
}
RADIUS = 56  # a pie slice's radius; the highlighted slice gets 12 more
WHITE_BOLD = ft.TextStyle(size=15, color=ft.Colors.WHITE, weight=ft.FontWeight.W_800)
# Moving the mouse off the chart, or tapping beside the bars or slices, clears the highlight.
CLEAR_EVENTS = {fch.ChartEventType.POINTER_EXIT, fch.ChartEventType.TAP_UP}


def touched(index: int | None, event_type: fch.ChartEventType, current: int | None) -> int | None:
    """The bar or slice to highlight after a chart event (None for no highlight)."""
    if index is not None and index >= 0:
        return index
    return None if event_type in CLEAR_EVENTS else current


def tab(name: str, on_click: ft.ControlEventHandler[ft.Container]) -> ft.Container:
    """A region tab; show() colours the selected one."""
    return ft.Container(
        content=ft.Text(name, size=16, weight=ft.FontWeight.W_700),
        data=name,
        on_click=on_click,
        expand=True,
        height=44,
        border_radius=22,
        alignment=ft.Alignment.CENTER,
        animate=ft.Animation(duration=250, curve=ft.AnimationCurve.EASE_OUT),
    )


def day_bar() -> fch.BarChartRod:
    """A day's bar, starting at zero so it grows when the first numbers come in."""
    return fch.BarChartRod(
        to_y=0,
        width=24,
        border_radius=ft.BorderRadius.only(top_left=8, top_right=8),
        # The grey track behind the bar also makes the whole column easy to tap.
        bg_to_y=100,
        bgcolor=ft.Colors.GREY_100,
    )


def legend_row(name: str, color: ft.ColorValue, share: int, selected: bool) -> ft.Row:
    """A channel's colour dot, name and share, in bold when its slice is highlighted."""
    weight = ft.FontWeight.W_800 if selected else ft.FontWeight.NORMAL
    return ft.Row(
        spacing=10,
        controls=[
            ft.Container(width=14, height=14, border_radius=7, bgcolor=color),
            ft.Text(name, size=15, expand=True, color=ft.Colors.GREY_800, weight=weight),
            ft.Text(f"{share}%", size=15, color=ft.Colors.GREY_600, weight=weight),
        ],
    )


async def main(page: ft.Page):
    page.title = "Sales"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ft.Colors.WHITE
    page.padding = 0
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    region = "North"
    day = None  # the tapped or hovered day; None highlights the week's best day
    channel = None  # the tapped or hovered channel; None pops out no slice
    bars = [day_bar() for _ in DAYS]
    pieces = [
        fch.PieChartSection(value=25, color=color, radius=RADIUS, title_style=WHITE_BOLD)
        for color in CHANNELS.values()
    ]

    def show():
        """Draw the region's numbers, highlight the chosen day and channel, and update."""
        data = REGIONS[region]
        for t in tabs.controls:
            t.bgcolor = data["color"] if t.data == region else None
            t.content.color = ft.Colors.WHITE if t.data == region else ft.Colors.GREY_700

        best = data["sales"].index(max(data["sales"]))
        shown = best if day is None else day
        for i, (bar, amount) in enumerate(zip(bars, data["sales"])):
            bar.to_y = amount
            bar.color = data["color"] if i == shown else ft.Colors.with_opacity(0.45, data["color"])
            bar.tooltip = fch.BarChartRodTooltip(text=f"${amount}k", text_style=WHITE_BOLD)
        total.value = f"${sum(data['sales'])}k"
        detail.value = f"{'Best: ' if day is None else ''}{DAYS[shown]} ${data['sales'][shown]}k"

        for i, (piece, share) in enumerate(zip(pieces, data["share"])):
            piece.value = share
            piece.title = f"{share}%"
            piece.radius = RADIUS + 12 if i == channel else RADIUS
        legend.controls = [
            legend_row(name, color, share, i == channel)
            for i, ((name, color), share) in enumerate(zip(CHANNELS.items(), data["share"]))
        ]
        page.update()

    def show_region(step: int):
        """Switch to the next (1) or previous (-1) region."""
        nonlocal region
        names = list(REGIONS)
        region = names[(names.index(region) + step) % len(names)]
        show()

    def handle_tab_click(e: ft.Event[ft.Container]):
        nonlocal region
        region = e.control.data
        show()

    def handle_keyboard_event(e: ft.KeyboardEvent):
        if e.key == "Arrow Left":
            show_region(-1)
        elif e.key == "Arrow Right":
            show_region(1)

    def handle_bar_event(e: fch.BarChartEvent):
        nonlocal day
        if (new_day := touched(e.group_index, e.type, day)) != day:
            day = new_day
            show()

    def handle_pie_event(e: fch.PieChartEvent):
        nonlocal channel
        if (new_channel := touched(e.section_index, e.type, channel)) != channel:
            channel = new_channel
            show()

    page.on_keyboard_event = handle_keyboard_event
    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                max_width=520,  # keeps the phone-like layout in a wide desktop window
                padding=ft.Padding.only(left=20, right=20, top=12, bottom=16),
                content=ft.Column(
                    expand=True,
                    spacing=14,
                    controls=[
                        ft.Text("Weekly sales", size=30, weight=ft.FontWeight.W_800),
                        ft.Container(
                            padding=4,
                            border_radius=26,
                            bgcolor=ft.Colors.GREY_100,
                            content=(
                                tabs := ft.Row(
                                    spacing=4,
                                    controls=[tab(name, handle_tab_click) for name in REGIONS],
                                )
                            ),
                        ),
                        ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            spacing=12,
                            controls=[
                                total := ft.Text(size=40, weight=ft.FontWeight.W_800),
                                detail := ft.Text(size=16, color=ft.Colors.GREY_600),
                            ],
                        ),
                        ft.Container(
                            expand=True,
                            padding=ft.Padding.only(top=36),  # room for the tooltip of a tall bar
                            content=fch.BarChart(
                                expand=True,
                                max_y=100,
                                on_event=handle_bar_event,
                                groups=[
                                    fch.BarChartGroup(x=i, rods=[bar]) for i, bar in enumerate(bars)
                                ],
                                animation=ft.Animation(
                                    duration=600, curve=ft.AnimationCurve.EASE_OUT_BACK
                                ),
                                tooltip=fch.BarChartTooltip(
                                    bgcolor=ft.Colors.GREY_900,
                                    border_radius=10,
                                    fit_inside_vertically=True,
                                ),
                                bottom_axis=fch.ChartAxis(
                                    label_size=28,
                                    labels=[
                                        fch.ChartAxisLabel(
                                            value=i,
                                            label=ft.Text(d[0], size=15, color=ft.Colors.GREY_600),
                                        )
                                        for i, d in enumerate(DAYS)
                                    ],
                                ),
                            ),
                        ),
                        ft.Text("By channel", size=22, weight=ft.FontWeight.W_800),
                        ft.Container(
                            border_radius=24,
                            bgcolor=ft.Colors.GREY_50,
                            padding=16,
                            content=ft.Row(
                                spacing=16,
                                controls=[
                                    fch.PieChart(
                                        width=170,
                                        height=170,
                                        sections=pieces,
                                        sections_space=3,
                                        center_space_radius=28,
                                        start_degree_offset=-90,
                                        animation=ft.Animation(
                                            duration=600, curve=ft.AnimationCurve.EASE_OUT_CUBIC
                                        ),
                                        on_event=handle_pie_event,
                                    ),
                                    legend := ft.Column(spacing=10, expand=True),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        )
    )

    # Let the empty charts draw first, so the bars grow from zero instead of appearing.
    await asyncio.sleep(0.3)
    show()


if __name__ == "__main__":
    ft.run(main)
