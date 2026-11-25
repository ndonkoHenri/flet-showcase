import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import flet as ft

BG, CARD, EDGE = "#F5F3EE", "#FFFFFF", "#E7E2D8"
INK, MUTED, ACCENT, SCRIM = "#1C1B1F", "#7A756C", "#FF6B4A", "#16130F"
FAB_SIZE, CIRCLE, ROW_GAP, EDGE_GAP = 56, 50, 14, 20  # button sizes and gaps of the speed dial
POP = ft.Animation(280, ft.AnimationCurve.EASE_OUT_BACK)
RISE = ft.Animation(260, ft.AnimationCurve.EASE_OUT_CUBIC)
GROW = ft.Animation(380, ft.AnimationCurve.EASE_OUT_CUBIC)


@dataclass
class DialAction:
    """One labeled button of the speed dial."""

    key: str
    label: str
    icon: ft.IconData
    color: str


ACTIONS = [  # top to bottom: the last one sits right above the + button
    DialAction("text", "Text note", ft.Icons.NOTES_ROUNDED, "#6366F1"),
    DialAction("checklist", "Checklist", ft.Icons.CHECKLIST_ROUNDED, "#10B981"),
    DialAction("voice", "Voice memo", ft.Icons.MIC_ROUNDED, "#F59E0B"),
    DialAction("photo", "Photo", ft.Icons.PHOTO_CAMERA_ROUNDED, "#EC4899"),
]


def speed_dial(
    actions: list[DialAction], on_pick: Callable[[DialAction], Awaitable[None]]
) -> tuple[ft.Stack, Callable[[], Awaitable[None]]]:
    """A + button that fans out into labeled actions over a scrim.

    Returns a full-screen layer to put on top of a Stack, and a function that closes the dial.
    """
    state = {"open": False}

    def show_item(item: ft.Container, shown: bool):
        """Grows, raises and fades an action in, or shrinks, lowers and fades it out."""
        item.opacity = 1 if shown else 0
        item.scale = ft.Scale(scale=1 if shown else 0.4, alignment=ft.Alignment.CENTER_RIGHT)
        item.offset = ft.Offset(0, 0 if shown else 0.6)
        item.ignore_interactions = not shown

    async def set_open(opened: bool):
        """Fans the actions out one after another (nearest first), or folds them back."""
        if state["open"] == opened:
            return
        state["open"] = opened
        plus.rotate = 3 * math.pi / 4 if opened else 0  # 135 degrees: the + lands as an x
        scrim.opacity, scrim.ignore_interactions = (1, False) if opened else (0, True)
        for item in reversed(items) if opened else items:
            if state["open"] != opened:  # tapped again halfway: the newer call takes over
                return
            show_item(item, opened)
            layer.update()
            await asyncio.sleep(0.05 if opened else 0.035)

    async def toggle():
        """Opens the dial, or closes it when it's open."""
        await set_open(not state["open"])

    async def close():
        """Folds the dial back."""
        await set_open(False)

    async def handle_action_click(e: ft.Event[ft.Container]):
        if not state["open"]:  # a second tap while the dial folds back
            return
        await close()
        await on_pick(e.control.data)

    def action_item(action: DialAction) -> ft.Container:
        """A label pill and a round icon button, both picking `action`."""
        item = ft.Container(
            animate_opacity=ft.Animation(180),
            animate_scale=POP,
            animate_offset=RISE,
            content=ft.Row(
                tight=True,
                spacing=12,
                controls=[
                    ft.Container(
                        height=38,
                        bgcolor=CARD,
                        border_radius=19,
                        padding=ft.Padding.symmetric(horizontal=16),
                        alignment=ft.Alignment.CENTER,
                        data=action,
                        on_click=handle_action_click,
                        shadow=ft.BoxShadow(
                            blur_radius=16,
                            offset=ft.Offset(0, 4),
                            color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                        ),
                        content=ft.Text(
                            action.label, size=16, weight=ft.FontWeight.W_700, color=INK
                        ),
                    ),
                    ft.Container(
                        width=FAB_SIZE,  # centers the circle above the + button
                        alignment=ft.Alignment.CENTER,
                        content=ft.Container(
                            width=CIRCLE,
                            height=CIRCLE,
                            border_radius=CIRCLE / 2,
                            bgcolor=action.color,
                            alignment=ft.Alignment.CENTER,
                            data=action,
                            on_click=handle_action_click,
                            shadow=ft.BoxShadow(
                                blur_radius=14,
                                offset=ft.Offset(0, 5),
                                color=ft.Colors.with_opacity(0.35, action.color),
                            ),
                            content=ft.Icon(action.icon, size=24, color=ft.Colors.WHITE),
                        ),
                    ),
                ],
            ),
        )
        show_item(item, False)
        return item

    items = [action_item(action) for action in actions]
    layer = ft.Stack(
        left=0,
        right=0,
        top=0,
        bottom=0,
        controls=[
            scrim := ft.Container(
                left=0,
                right=0,
                top=0,
                bottom=0,
                bgcolor=ft.Colors.with_opacity(0.6, SCRIM),
                opacity=0,
                animate_opacity=ft.Animation(250),
                ignore_interactions=True,  # taps reach the screen below while the dial is closed
                on_click=close,
            ),
            ft.SafeArea(
                left=0,
                right=0,
                top=0,
                bottom=0,
                content=ft.Stack(
                    clip_behavior=ft.ClipBehavior.NONE,
                    controls=[
                        ft.Container(
                            right=EDGE_GAP,
                            bottom=16,
                            content=ft.Column(
                                spacing=ROW_GAP,
                                tight=True,
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                controls=[
                                    *items,
                                    ft.FloatingActionButton(
                                        content=(
                                            plus := ft.Icon(
                                                ft.Icons.ADD_ROUNDED,
                                                size=30,
                                                color=ft.Colors.WHITE,
                                                rotate=0,
                                                animate_rotation=ft.Animation(
                                                    320, ft.AnimationCurve.EASE_OUT_BACK
                                                ),
                                            )
                                        ),
                                        bgcolor=ACCENT,
                                        shape=ft.CircleBorder(),
                                        on_click=toggle,
                                    ),
                                ],
                            ),
                        )
                    ],
                ),
            ),
        ],
    )
    return layer, close


def card(*controls: ft.Control, new: bool = False, padding: float = 14) -> ft.Container:
    """A rounded note card; a new one gets an accent border."""
    return ft.Container(
        bgcolor=CARD,
        border_radius=20,
        border=ft.Border.all(2, ACCENT) if new else ft.Border.all(1, EDGE),
        padding=padding,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        margin=ft.Margin.only(bottom=12),
        content=ft.Column(
            spacing=6, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=list(controls)
        ),
    )


def heading(text: str, new: bool) -> ft.Control:
    """A note's title, with a NEW badge on the notes made with the speed dial."""
    title = ft.Text(text, size=17, weight=ft.FontWeight.W_800, color=INK, expand=new)
    if not new:
        return title
    badge = ft.Container(
        bgcolor=ACCENT,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        content=ft.Text("NEW", size=11, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
    )
    return ft.Row(controls=[title, badge])


def meta(text: str) -> ft.Text:
    """A note's gray second line."""
    return ft.Text(text, size=13, color=MUTED)


def check_row(text: str, done: bool = False) -> ft.Row:
    """One checklist line, crossed out once it's done."""
    return ft.Row(
        spacing=8,
        controls=[
            ft.Icon(
                ft.Icons.CHECK_BOX_ROUNDED if done else ft.Icons.CHECK_BOX_OUTLINE_BLANK_ROUNDED,
                size=20,
                color="#10B981" if done else MUTED,
            ),
            ft.Text(
                text,
                size=15,
                color=MUTED if done else INK,
                expand=True,
                style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if done else None,
            ),
        ],
    )


def text_note(name: str, body: str, new: bool = False) -> ft.Container:
    """A note of a few lines of text."""
    return card(
        heading(name, new),
        ft.Text(body, size=15, color=MUTED, max_lines=4, overflow=ft.TextOverflow.ELLIPSIS),
        new=new,
    )


def checklist_note(name: str, lines: list[str], done: int = 0, new: bool = False) -> ft.Container:
    """A checklist whose first `done` lines are ticked off."""
    return card(
        heading(name, new), *[check_row(line, i < done) for i, line in enumerate(lines)], new=new
    )


def voice_note(name: str, length: str, new: bool = False) -> ft.Container:
    """A voice memo: a play button and a waveform."""
    heights = [10, 18, 26, 14, 30, 22, 12, 24, 16, 28, 10, 20, 14]
    return card(
        ft.Row(
            spacing=8,
            controls=[
                ft.Container(
                    width=34,
                    height=34,
                    border_radius=17,
                    bgcolor="#FEF3C7",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=22, color="#F59E0B"),
                ),
                ft.Row(
                    expand=True,
                    spacing=3,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(width=3, height=h, border_radius=2, bgcolor="#F59E0B")
                        for h in heights
                    ],
                ),
            ],
        ),
        heading(name, new),
        meta(f"Voice · {length}"),
        new=new,
    )


def photo_note(src: str, name: str, info: str, new: bool = False) -> ft.Container:
    """A photo with a caption under it."""
    return card(
        ft.Image(src=src, height=120, fit=ft.BoxFit.COVER),
        ft.Container(
            padding=ft.Padding.only(left=14, right=14, top=4, bottom=12),
            content=ft.Column(spacing=2, controls=[heading(name, new), meta(info)]),
        ),
        new=new,
        padding=0,
    )


def notes_column(*notes: ft.Container) -> ft.Column:
    """One of the two columns of notes."""
    return ft.Column(
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=list(notes),
    )


NEW_NOTES = {  # what each action adds, in turn: the note maker and its samples
    "text": (
        text_note,
        [
            ("Gift ideas", "A scarf for Mom, a puzzle for Leo, and tickets to the lake concert."),
            ("Quote", "Simple things should be simple, complex things should be possible."),
        ],
    ),
    "checklist": (
        checklist_note,
        [
            ("Packing list", ["Passport", "Charger", "Sunscreen"]),
            ("Movie night", ["Popcorn", "Blanket", "Pick a film"]),
        ],
    ),
    "voice": (voice_note, [("Voice memo", "0:12"), ("Song idea", "0:48")]),
    "photo": (  # photos from Wikimedia Commons, CC0 (see the README)
        photo_note,
        [
            ("aurora.jpg", "Northern lights", "Just now · 1 photo"),
            ("forest.jpg", "Misty forest", "Just now · 1 photo"),
        ],
    ),
}


def main(page: ft.Page):
    page.title = "Speed dial"
    page.padding = 0
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ACCENT)

    added = dict.fromkeys(NEW_NOTES, 0)  # notes added per kind, to take turns with the samples

    def show_count():
        """Shows how many notes there are."""
        count.value = f"{len(left_column.controls) + len(right_column.controls)} notes"
        page.update()

    async def add_note(action: DialAction):
        """Grows a new note of the action's kind in at the top of the column with fewer notes."""
        maker, samples = NEW_NOTES[action.key]
        sample = samples[added[action.key] % len(samples)]
        added[action.key] += 1
        column = min(left_column, right_column, key=lambda c: len(c.controls))
        # An empty slot first, then its note: animate_size grows the slot to the note's height.
        slot = ft.Container(
            opacity=0, scale=0.9, animate_size=GROW, animate_opacity=GROW, animate_scale=POP
        )
        column.controls.insert(0, slot)
        page.update()
        await asyncio.sleep(0.05)
        slot.content = maker(*sample, new=True)
        slot.opacity, slot.scale = 1, 1
        show_count()

        async def handle_undo(e: ft.Event[ft.SnackBar]):
            slot.opacity, slot.scale = 0, 0.9
            page.update()
            await asyncio.sleep(0.2)
            slot.content = None  # the empty slot shrinks away
            page.update()
            await asyncio.sleep(0.4)
            column.controls.remove(slot)
            show_count()

        page.show_dialog(
            ft.SnackBar(
                ft.Text(f"{action.label} added"),
                action="Undo",
                on_action=handle_undo,
                behavior=ft.SnackBarBehavior.FLOATING,
                # beside the + button, not over it
                margin=ft.Margin.only(left=16, right=EDGE_GAP + FAB_SIZE + 16, bottom=16),
                persist=False,
            )
        )

    dial, close_dial = speed_dial(ACTIONS, on_pick=add_note)

    async def handle_keyboard_event(e: ft.KeyboardEvent):
        if e.key == "Escape":
            await close_dial()

    page.on_keyboard_event = handle_keyboard_event

    page.add(
        ft.Stack(
            expand=True,
            controls=[
                ft.SafeArea(
                    left=0,
                    right=0,
                    top=0,
                    bottom=0,
                    content=ft.Container(
                        alignment=ft.Alignment.TOP_CENTER,
                        padding=ft.Padding.only(left=16, right=16, top=6),
                        content=ft.Column(
                            max_width=480,  # fills a phone, stays phone-shaped on wide windows
                            spacing=14,
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Column(
                                            expand=True,
                                            spacing=0,
                                            controls=[
                                                ft.Text(
                                                    "My notes",
                                                    size=30,
                                                    weight=ft.FontWeight.W_900,
                                                    color=INK,
                                                ),
                                                count := ft.Text(size=15, color=MUTED),
                                            ],
                                        ),
                                        ft.Container(
                                            width=46,
                                            height=46,
                                            border_radius=23,
                                            alignment=ft.Alignment.CENTER,
                                            gradient=ft.LinearGradient(
                                                colors=[ACCENT, "#F59E0B"],
                                                begin=ft.Alignment.TOP_LEFT,
                                                end=ft.Alignment.BOTTOM_RIGHT,
                                            ),
                                            content=ft.Text(
                                                "AK",
                                                size=16,
                                                weight=ft.FontWeight.W_800,
                                                color=ft.Colors.WHITE,
                                            ),
                                        ),
                                    ]
                                ),
                                ft.Column(
                                    expand=True,
                                    scroll=ft.ScrollMode.HIDDEN,
                                    controls=[
                                        ft.Row(
                                            spacing=12,
                                            vertical_alignment=ft.CrossAxisAlignment.START,
                                            controls=[
                                                left_column := notes_column(
                                                    photo_note(
                                                        "fjord.jpg",
                                                        "Fjord trip",
                                                        "Mar 12 · 6 photos",
                                                    ),
                                                    text_note(
                                                        "Book ideas",
                                                        "A lighthouse keeper who collects lost "
                                                        "letters, and the one that was meant for her.",
                                                    ),
                                                    checklist_note(
                                                        "Weekend",
                                                        [
                                                            "Farmers market",
                                                            "Call grandma",
                                                            "Fix the bike",
                                                        ],
                                                        done=1,
                                                    ),
                                                ),
                                                right_column := notes_column(
                                                    checklist_note(
                                                        "Groceries",
                                                        ["Oat milk", "Lemons", "Basil"],
                                                        done=1,
                                                    ),
                                                    voice_note("Interview notes", "2:14"),
                                                    photo_note(
                                                        "lake.jpg",
                                                        "Mountain lake",
                                                        "Jun 3 · 9 photos",
                                                    ),
                                                ),
                                            ],
                                        ),
                                        # room to scroll the last notes above the + button
                                        ft.Container(height=90),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ),
                dial,
            ],
        )
    )
    show_count()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
