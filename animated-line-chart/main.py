import asyncio

import flet as ft
import flet_charts as fch

MONTHS = "JFMAMJJASOND"
THIS_YEAR = [3.2, 4.1, 3.8, 5.6, 6.1, 5.4, 7.2, 8.0, 7.6, 9.4, 10.8, 12.4]
LAST_YEAR = [2.5, 2.9, 3.1, 3.4, 3.2, 4.0, 4.3, 4.1, 4.8, 5.2, 5.9, 6.4]
ACCENT = ft.Colors.INDIGO_500


def money(value: float) -> str:
    """Thousands of dollars, as shown in the app: 3.2 -> $3.2k."""
    return f"${value:.1f}k"


def tip(text: str) -> fch.LineChartDataPointTooltip:
    """A point's tooltip, in white so it reads on the coloured tooltip box."""
    return fch.LineChartDataPointTooltip(
        text=text,
        text_style=ft.TextStyle(color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
    )


def stat(label: str, value: ft.Text) -> ft.Container:
    """A small grey card with a label above a value."""
    return ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(vertical=10, horizontal=14),
        border_radius=16,
        bgcolor=ft.Colors.GREY_100,
        content=ft.Column([ft.Text(label, color=ft.Colors.GREY_600), value], spacing=2),
    )


def main(page: ft.Page):
    page.title = "Revenue"
    page.bgcolor = ft.Colors.WHITE
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    line = fch.LineChartData(
        curved=True,
        prevent_curve_over_shooting=True,
        color=ACCENT,
        stroke_width=5,
        rounded_stroke_cap=True,
        point=fch.ChartCirclePoint(
            radius=4, color=ft.Colors.WHITE, stroke_color=ACCENT, stroke_width=3
        ),
        below_line_gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_CENTER,
            end=ft.Alignment.BOTTOM_CENTER,
            colors=[
                ft.Colors.with_opacity(0.35, ACCENT),
                ft.Colors.with_opacity(0.0, ACCENT),
            ],
        ),
    )
    last_year = fch.LineChartData(
        points=[
            fch.LineChartDataPoint(i, v, tooltip=tip(f"2025: {money(v)}"))
            for i, v in enumerate(LAST_YEAR)
        ],
        curved=True,
        color=ft.Colors.GREY_400,
        stroke_width=3,
        dash_pattern=[8, 6],
        point=False,
    )
    chart = fch.LineChart(
        expand=True,
        data_series=[line],
        min_x=0,
        max_x=11,
        min_y=0,
        max_y=14,
        animation=ft.Animation(duration=420, curve=ft.AnimationCurve.EASE_OUT_CUBIC),
        horizontal_grid_lines=fch.ChartGridLines(interval=4, color=ft.Colors.GREY_200),
        tooltip=fch.LineChartTooltip(bgcolor=ACCENT, border_radius=12),
        left_axis=fch.ChartAxis(
            label_size=44,
            labels=[
                fch.ChartAxisLabel(value=v, label=ft.Text(f"${v}k"))
                for v in (0, 4, 8, 12)
            ],
        ),
        bottom_axis=fch.ChartAxis(
            label_size=30,
            labels=[
                fch.ChartAxisLabel(value=i, label=ft.Text(m))
                for i, m in enumerate(MONTHS)
            ],
        ),
    )

    playing = False

    def update_stats():
        """Refresh the total, growth and the three cards from the points so far."""
        values = [p.y for p in line.points]
        total.value = money(sum(values)) if values else money(0)
        growth.value = (
            f"+{(values[-1] / values[0] - 1) * 100:.0f}% since Jan"
            if len(values) > 1
            else ""
        )
        months.value = f"{len(values)} / 12"
        best.value = money(max(values)) if values else "-"
        average.value = money(sum(values) / len(values)) if values else "-"
        add_button.disabled = play_button.disabled = playing or len(values) == 12

    async def add_month():
        """Add next month's sales as a new point (hover or tap it for its value)."""
        month = len(line.points)
        if month == 12:  # a quick double click on the last month
            return
        amount = THIS_YEAR[month]
        # A new point appears at once; only points that move are animated. So it starts
        # on the last point and then moves to its value: the line grows instead of jumping.
        start = line.points[-1] if line.points else None
        point = fch.LineChartDataPoint(
            start.x if start else month,
            start.y if start else amount,
            tooltip=tip(money(amount)),
        )
        line.points.append(point)
        chart.update()
        await asyncio.sleep(0.05)
        point.x, point.y = month, amount
        update_stats()
        page.update()

    async def handle_add_click(e: ft.Event[ft.FilledButton]):
        await add_month()

    async def handle_play_click(e: ft.Event[ft.OutlinedButton]):
        nonlocal playing
        playing = True  # keeps both buttons disabled until the year is complete
        update_stats()
        page.update()
        while len(line.points) < 12:
            await add_month()
            await asyncio.sleep(0.5)
        playing = False
        update_stats()
        page.update()

    def handle_compare_change(e: ft.Event[ft.Switch]):
        chart.data_series = [last_year, line] if e.control.value else [line]
        page.update()

    def handle_reset_click(e: ft.Event[ft.IconButton]):
        line.points.clear()
        update_stats()
        page.update()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                max_width=520,  # keeps the phone-like layout in a wide desktop window
                padding=10,
                content=ft.Column(
                    expand=True,
                    spacing=12,
                    controls=[
                        ft.Text("Revenue", size=30, weight=ft.FontWeight.W_800),
                        ft.Text("Monthly, this year", color=ft.Colors.GREY_600),
                        ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                total := ft.Text(size=40, weight=ft.FontWeight.W_800),
                                growth := ft.Text(
                                    color=ft.Colors.GREEN_700, weight=ft.FontWeight.BOLD
                                ),
                            ],
                        ),
                        ft.Container(
                            expand=True,
                            border_radius=24,
                            bgcolor=ft.Colors.with_opacity(0.04, ACCENT),
                            padding=ft.Padding.only(
                                left=8, right=20, top=28, bottom=10
                            ),
                            content=chart,
                        ),
                        ft.Switch(
                            label="Compare with 2025 (dashed)",
                            on_change=handle_compare_change,
                        ),
                        ft.Row(
                            spacing=10,
                            controls=[
                                stat("Months", months := ft.Text(size=18)),
                                stat("Best", best := ft.Text(size=18)),
                                stat("Average", average := ft.Text(size=18)),
                            ],
                        ),
                        ft.Row(
                            wrap=True,
                            controls=[
                                add_button := ft.FilledButton(
                                    "Add month",
                                    icon=ft.Icons.ADD,
                                    on_click=handle_add_click,
                                ),
                                play_button := ft.OutlinedButton(
                                    "Play",
                                    icon=ft.Icons.PLAY_ARROW,
                                    on_click=handle_play_click,
                                ),
                                ft.IconButton(
                                    ft.Icons.RESTART_ALT,
                                    tooltip="Reset",
                                    on_click=handle_reset_click,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        )
    )
    update_stats()
    page.update()


if __name__ == "__main__":
    ft.run(main)
