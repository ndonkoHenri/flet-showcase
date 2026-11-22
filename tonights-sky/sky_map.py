"""The sky map and the Moon, drawn as Flet canvas shapes."""

import math
import random

import flet as ft
import flet.canvas as cv

INK, MUTED = "#F4F6FF", "#8C97C2"  # text colors, for the map's labels and the app's cards
MW, MH = 340, 270  # sky map size
CX, CY, R = MW / 2, MH / 2, 118  # its middle and the horizon's radius


def sky_xy(alt: float, az: float) -> tuple[float, float]:
    """Looking up: zenith in the middle, horizon on the rim, north up, east on the left."""
    r = R * (90 - alt) / 90
    a = math.radians(az)
    return CX - r * math.sin(a), CY - r * math.cos(a)


def sky_background() -> list[cv.Shape]:
    """The sky disc with a few stars, the 30° and 60° altitude rings and the compass points."""
    rng = random.Random(7)  # the same stars every time
    disc = ft.PaintRadialGradient(center=ft.Offset(CX, CY), radius=R, colors=["#1B2756", "#0C1430"])
    shapes = [cv.Circle(CX, CY, R, paint=ft.Paint(gradient=disc))]
    for _ in range(70):
        r, a = R * math.sqrt(rng.random()), rng.random() * 2 * math.pi
        star = ft.Paint(color=ft.Colors.with_opacity(rng.uniform(0.25, 0.8), ft.Colors.WHITE))
        x, y = CX + r * math.cos(a), CY + r * math.sin(a)
        shapes.append(cv.Circle(x, y, rng.uniform(0.5, 1.4), paint=star))
    for alt in (30, 60):
        ring = R * (90 - alt) / 90
        dashes = ft.Paint(
            color="#2E3B6E",
            style=ft.PaintingStyle.STROKE,
            stroke_width=1,
            stroke_dash_pattern=[4, 5],
        )
        shapes.append(cv.Circle(CX, CY, ring, paint=dashes))
        shapes.append(
            cv.Text(
                CX + 4,
                CY - ring - 2,
                f"{alt}°",
                alignment=ft.Alignment.BOTTOM_LEFT,
                style=ft.TextStyle(size=10, color="#5D6A9C"),
            )
        )
    rim = ft.Paint(color="#3A4A85", style=ft.PaintingStyle.STROKE, stroke_width=1.5)
    shapes.append(cv.Circle(CX, CY, R, paint=rim))
    for label, az in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        style = ft.TextStyle(size=13, weight=ft.FontWeight.W_800, color=MUTED)
        shapes.append(cv.Text(*sky_xy(-9, az), label, alignment=ft.Alignment.CENTER, style=style))
    return shapes


def place_labels(bodies: list[dict]):
    """Give each body its dot (at its highest) and a label spot clear of the ones before it."""
    taken = []  # boxes (left, top, right, bottom) of the labels and dots placed so far
    for b in bodies:
        x, y = b["dot"] = sky_xy(b["peak_alt"], b["peak_az"])
        w, h = 8.6 * len(b["name"]) + 4, 18
        beside = [(x + 10, y - h / 2), (x - 10 - w, y - h / 2)]
        if x >= CX + 70:  # near the right edge: try the left side first
            beside.reverse()
        spots = beside + [(x - w / 2, y - 9 - h), (x - w / 2, y + 9)]
        spots += [(sx, sy + dy) for dy in (14, -14, 26, -26) for sx, sy in beside]
        b["label_at"] = spots[0]
        for lx, ly in spots:
            box = (lx, ly, lx + w, ly + h)
            inside = 0 <= lx and lx + w <= MW and 0 <= ly and ly + h <= MH
            if inside and not any(
                box[0] < t[2] and t[0] < box[2] and box[1] < t[3] and t[1] < box[3] for t in taken
            ):
                b["label_at"] = (lx, ly)
                taken.append(box)
                break
        taken.append((x - 7, y - 7, x + 7, y + 7))


def track_elements(body: dict, upto: int | None = None) -> list[cv.Path.PathElement]:
    """The lines of the body's path across the sky after dark, its first `upto` samples."""
    elements, previous = [], None
    for i, alt, az in body["track"][:upto]:
        x, y = sky_xy(alt, az)
        # A gap in the samples (it set, then rose again) starts a new line.
        joined = previous is not None and i == previous + 1
        elements.append(cv.Path.LineTo(x, y) if joined else cv.Path.MoveTo(x, y))
        previous = i
    return elements


def track_path(body: dict, upto: int | None = None, dim: bool = False) -> cv.Path:
    """The body's path across the sky, faint when another body is picked."""
    return cv.Path(
        elements=track_elements(body, upto),
        paint=ft.Paint(
            color=ft.Colors.with_opacity(0.15 if dim else 0.75, body["color"]),
            style=ft.PaintingStyle.STROKE,
            stroke_width=2.5,
            stroke_cap=ft.StrokeCap.ROUND,
            stroke_join=ft.StrokeJoin.ROUND,
        ),
    )


def marker(body: dict, dim: bool = False) -> list[cv.Shape]:
    """A glowing dot where the body is highest, with its name."""
    x, y = body["dot"]
    opacity = 0.3 if dim else 1.0
    color = body["color"]
    glow = ft.Paint(color=ft.Colors.with_opacity(0.35 * opacity, color), blur_image=4)
    name_style = ft.TextStyle(
        size=14, weight=ft.FontWeight.W_800, color=ft.Colors.with_opacity(opacity, INK)
    )
    return [
        cv.Circle(x, y, 11, paint=glow),
        cv.Circle(x, y, 6, paint=ft.Paint(color=ft.Colors.with_opacity(opacity, color))),
        cv.Text(*body["label_at"], body["name"], style=name_style),
    ]


def moon_shapes(lit: float, waxing: bool, south: bool) -> list[cv.Shape]:
    """The Moon on its 84 px canvas: a dark disc with its lit part and a soft glow."""
    c, r = 42, 34  # middle and radius
    # Lit on the right when waxing, seen from the north; the other way round from the south.
    side = (1 if waxing else -1) * (-1 if south else 1)
    # The lit part: down the edge's half circle, then back up the line between day and night,
    # half an ellipse that is flat at a quarter Moon.
    down = [math.radians(t) for t in range(-90, 91, 6)]
    edge = [(c + side * r * math.cos(t), c + r * math.sin(t)) for t in down]
    width = side * (1 - 2 * lit) * r
    terminator = [(c + width * math.cos(t), c + r * math.sin(t)) for t in reversed(down)]
    glow = ft.PaintRadialGradient(
        center=ft.Offset(c, c),
        radius=r + 8,
        colors=["#50F3EFD9", "#00F3EFD9"],
        color_stops=[r / (r + 8), 1],
    )
    outline = ft.Paint(color="#33FFFFFF", style=ft.PaintingStyle.STROKE, stroke_width=1)
    return [
        cv.Circle(c, c, r + 8, paint=ft.Paint(gradient=glow)),
        cv.Circle(c, c, r, paint=ft.Paint(color="#1C2546")),
        cv.Path(
            elements=[cv.Path.MoveTo(c, c - r)]
            + [cv.Path.LineTo(x, y) for x, y in edge + terminator],
            paint=ft.Paint(color="#F3EFD9"),
        ),
        cv.Circle(c, c, r, paint=outline),
    ]
