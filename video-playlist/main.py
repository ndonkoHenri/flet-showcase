from dataclasses import dataclass

import flet as ft
import flet_video as ftv

ACCENT = "#E00050"


@dataclass
class Clip:
    """A video in the playlist, with what the list shows about it."""

    title: str
    kind: str  # what it is and how long, e.g. "Trailer · 0:33"
    credit: str
    url: str
    color: str
    intro_end: int  # seconds; "Skip intro" seeks here


# Open movies by the Blender Foundation (CC BY 3.0), streamed from download.blender.org.
CLIPS = [
    Clip(
        "Big Buck Bunny",
        "Trailer · 0:33",
        "Blender Foundation, 2008",
        "https://download.blender.org/peach/trailer/trailer_480p.mov",
        "#7CB342",
        intro_end=7,
    ),
    Clip(
        "Sintel",
        "Trailer · 0:52",
        "Blender Foundation, 2010",
        "https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4",
        "#F4511E",
        intro_end=11,
    ),
]


def playlist_row(
    index: int, playing: bool, on_click: ft.ControlEventHandler[ft.Container]
) -> ft.Container:
    """A row of the playlist; the playing video gets a frame and a "NOW" label."""
    clip = CLIPS[index]
    return ft.Container(
        data=index,
        on_click=on_click,
        padding=12,
        border_radius=18,
        bgcolor="#FFF0F5" if playing else ft.Colors.GREY_100,
        border=ft.Border.all(2, ACCENT if playing else ft.Colors.TRANSPARENT),
        content=ft.Row(
            spacing=14,
            controls=[
                ft.Container(
                    width=96,
                    height=60,
                    border_radius=12,
                    bgcolor=clip.color,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(
                        ft.Icons.EQUALIZER_ROUNDED if playing else ft.Icons.PLAY_ARROW_ROUNDED,
                        color=ft.Colors.WHITE,
                        size=30,
                    ),
                ),
                ft.Column(
                    spacing=2,
                    expand=True,
                    controls=[
                        ft.Text(clip.title, size=18, weight=ft.FontWeight.W_700),
                        ft.Text(clip.kind, size=14, color=ft.Colors.GREY_700),
                        ft.Text(clip.credit, size=13, color=ft.Colors.GREY_500),
                    ],
                ),
                ft.Text(
                    "NOW" if playing else f"{index + 1}",
                    size=13,
                    weight=ft.FontWeight.W_800,
                    color=ACCENT if playing else ft.Colors.GREY_500,
                ),
            ],
        ),
    )


async def main(page: ft.Page):
    page.title = "Video playlist"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ft.Colors.WHITE
    page.padding = 0
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    playing = 0  # index of the video the player is on

    def show_track(index: int):
        """Show the playing video's details and highlight its row in the playlist."""
        nonlocal playing
        playing = index
        clip = CLIPS[index]
        now_title.value = clip.title
        now_credit.value = f"{clip.credit}  ·  CC BY 3.0"
        counter.value = f"{index + 1} / {len(CLIPS)}"
        rows.controls = [playlist_row(i, i == index, handle_row_click) for i in range(len(CLIPS))]
        page.update()

    def handle_track_change(e: ft.Event[ftv.Video]):
        # Fires for every switch: a tapped row, the player's own skip buttons, the end of a video.
        show_track(e.data)

    async def handle_row_click(e: ft.Event[ft.Container]):
        await video.jump_to(e.control.data)

    async def handle_skip_click(e: ft.Event[ft.FilledButton]):
        await video.seek(ft.Duration(seconds=CLIPS[playing].intro_end))

    async def handle_restart_click(e: ft.Event[ft.OutlinedButton]):
        await video.seek(ft.Duration(seconds=0))

    def handle_loop_click(e: ft.Event[ft.IconButton]):
        e.control.selected = not e.control.selected
        video.playlist_mode = ftv.PlaylistMode.LOOP if e.control.selected else ftv.PlaylistMode.NONE

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                max_width=480,  # fills a phone, stays phone-shaped on wide windows
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.only(left=20, right=8, top=6, bottom=10),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("Watch", size=30, weight=ft.FontWeight.W_800),
                                    ft.IconButton(
                                        icon=ft.Icons.REPEAT_ROUNDED,
                                        selected_icon=ft.Icons.REPEAT_ON_ROUNDED,
                                        selected=False,
                                        selected_icon_color=ACCENT,
                                        icon_size=28,
                                        tooltip="Loop the playlist",
                                        on_click=handle_loop_click,
                                    ),
                                ],
                            ),
                        ),
                        video := ftv.Video(
                            playlist=[ftv.VideoMedia(clip.url) for clip in CLIPS],
                            playlist_mode=ftv.PlaylistMode.NONE,
                            autoplay=True,
                            aspect_ratio=16 / 9,
                            on_track_change=handle_track_change,
                        ),
                        ft.Container(
                            expand=True,
                            padding=ft.Padding.only(left=20, right=20, top=18),
                            content=ft.Column(
                                expand=True,
                                spacing=12,
                                scroll=ft.ScrollMode.AUTO,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            now_title := ft.Text(
                                                size=28, weight=ft.FontWeight.W_800
                                            ),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(
                                                    horizontal=12, vertical=6
                                                ),
                                                border_radius=20,
                                                bgcolor=ACCENT,
                                                content=(
                                                    counter := ft.Text(
                                                        size=14,
                                                        weight=ft.FontWeight.W_700,
                                                        color=ft.Colors.WHITE,
                                                    )
                                                ),
                                            ),
                                        ],
                                    ),
                                    now_credit := ft.Text(size=15, color=ft.Colors.GREY_600),
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.FilledButton(
                                                "Skip intro",
                                                icon=ft.Icons.FAST_FORWARD_ROUNDED,
                                                bgcolor=ACCENT,
                                                on_click=handle_skip_click,
                                            ),
                                            ft.OutlinedButton(
                                                "Start over",
                                                icon=ft.Icons.REPLAY_ROUNDED,
                                                on_click=handle_restart_click,
                                            ),
                                        ],
                                    ),
                                    ft.Divider(height=10, color=ft.Colors.GREY_200),
                                    ft.Text("Playlist", size=20, weight=ft.FontWeight.W_700),
                                    rows := ft.Column(spacing=10),
                                    ft.Text(
                                        "Open movies by the Blender Foundation, "
                                        "streamed from download.blender.org.",
                                        size=15,
                                        color=ft.Colors.GREY_600,
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        )
    )

    show_track(0)


if __name__ == "__main__":
    ft.run(main)
