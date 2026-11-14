import flet as ft

MAIL = [  # (sender, subject, preview, avatar color)
    ("Ada", "Lunch at noon?", "See you at the usual place.", ft.Colors.INDIGO_400),
    ("Grace", "Slides attached", "Final version for Friday.", ft.Colors.TEAL_500),
    ("Linus", "Patch looks good", "Merging after CI passes.", ft.Colors.GREEN_600),
    ("Margaret", "Launch checklist", "Two items left, both easy.", ft.Colors.RED_400),
    ("Guido", "Re: typing", "Let's talk generics.", ft.Colors.BLUE_500),
    ("Barbara", "See you Friday", "Bring the prototype!", ft.Colors.PURPLE_400),
    ("Ken", "Coffee?", "Tomorrow, 9:30?", ft.Colors.BROWN_400),
    ("Katherine", "Orbit numbers", "Checked twice, all good.", ft.Colors.AMBER_700),
    ("Dennis", "Re: pointers", "Here's the example.", ft.Colors.CYAN_600),
]


def swipe_background(color: str, icon: ft.IconData, text: str, left: bool):
    """What shows under an email while it's swiped: green archive, red delete."""
    return ft.Container(
        bgcolor=color,
        border_radius=18,
        padding=ft.Padding.symmetric(horizontal=24),
        alignment=ft.Alignment.CENTER_LEFT if left else ft.Alignment.CENTER_RIGHT,
        content=ft.Row(
            tight=True,
            controls=[
                ft.Icon(icon, color=ft.Colors.WHITE),
                ft.Text(text, size=16, weight=ft.FontWeight.W_700, color="white"),
            ],
        ),
    )


def main(page: ft.Page):
    page.title = "Inbox"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE

    count = ft.Text(size=16, color=ft.Colors.GREY_600)

    def show_count():
        """The header count, and the empty state when nothing is left."""
        n = len(inbox.controls)
        count.value = f"{n} message{'' if n == 1 else 's'}"
        empty.visible = n == 0
        inbox.visible = n > 0

    def handle_dismiss(e: ft.DismissibleDismissEvent):
        item = e.control
        index = inbox.controls.index(item)
        inbox.controls.remove(item)
        archived = e.direction == ft.DismissDirection.START_TO_END  # swiped right
        show_count()

        def handle_undo(e: ft.Event[ft.SnackBarAction]):
            inbox.controls.insert(index, email(*item.data))  # a fresh copy, unswiped
            show_count()
            page.update()

        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(
                    f"{'Archived' if archived else 'Deleted'}: {item.data[1]}", size=16
                ),
                action=ft.SnackBarAction(label="Undo", on_click=handle_undo),
                behavior=ft.SnackBarBehavior.FLOATING,
                bgcolor=ft.Colors.GREEN_700 if archived else ft.Colors.GREY_900,
            )
        )
        page.update()

    def email(sender: str, subject: str, preview: str, color: str) -> ft.Dismissible:
        """One email that can be swiped away, either way."""
        return ft.Dismissible(
            data=(sender, subject, preview, color),
            dismiss_direction=ft.DismissDirection.HORIZONTAL,
            on_dismiss=handle_dismiss,
            background=swipe_background(
                ft.Colors.GREEN_600, ft.Icons.ARCHIVE_ROUNDED, "Archive", left=True
            ),
            secondary_background=swipe_background(
                ft.Colors.RED_500, ft.Icons.DELETE_ROUNDED, "Delete", left=False
            ),
            content=ft.Container(
                height=84,
                border_radius=18,
                bgcolor=ft.Colors.GREY_50,
                padding=ft.Padding.symmetric(horizontal=14),
                content=ft.Row(
                    spacing=12,
                    controls=[
                        ft.CircleAvatar(
                            content=ft.Text(sender[0], size=18),
                            bgcolor=color,
                            color=ft.Colors.WHITE,
                            radius=24,
                        ),
                        ft.Column(
                            spacing=1,
                            expand=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Text(sender, size=17, weight=ft.FontWeight.W_700),
                                ft.Text(subject, size=16, weight=ft.FontWeight.W_600),
                                ft.Text(
                                    preview,
                                    size=15,
                                    color=ft.Colors.GREY_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        )

    def handle_refill_click(e: ft.Event[ft.TextButton]):
        """Put every email back, for another round of swiping."""
        inbox.controls = [email(*m) for m in MAIL]
        show_count()
        page.update()

    empty = ft.Container(  # shown when every email is gone
        visible=False,
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            tight=True,
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.INBOX_ROUNDED, size=64, color=ft.Colors.GREY_400),
                ft.Text("Inbox zero!", size=22, weight=ft.FontWeight.W_700),
                ft.TextButton("Bring them back", on_click=handle_refill_click),
            ],
        ),
    )
    inbox = ft.ListView(expand=True, spacing=8, controls=[email(*m) for m in MAIL])
    show_count()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                padding=ft.Padding.only(left=14, right=14, top=12),
                content=ft.Column(
                    expand=True,
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Text("Inbox", size=30, weight=ft.FontWeight.W_800),
                                count,
                            ],
                        ),
                        ft.Text(
                            "Swipe left to delete, right to archive",
                            size=15,
                            color=ft.Colors.GREY_500,
                        ),
                        inbox,
                        empty,
                    ],
                ),
            ),
        )
    )


if __name__ == "__main__":
    ft.run(main)
