import asyncio

import flet as ft

INBOX = [
    ("Alan", "Ping", ft.Colors.ORANGE),
    ("Linus", "Patch looks good", ft.Colors.GREEN),
    ("Guido", "Re: typing", ft.Colors.BLUE),
    ("Barbara", "See you Friday", ft.Colors.PURPLE),
    ("Ken", "Coffee?", ft.Colors.BROWN),
    ("Margaret", "Launch checklist", ft.Colors.RED),
    ("Dennis", "Re: pointers", ft.Colors.CYAN),
    ("Katherine", "Orbit numbers", ft.Colors.AMBER),
]
NEW_MESSAGES = [
    ("Flet", "1.1.2 is out: fixes for notifications and builds", ft.Colors.PINK),
    ("Ada", "Lunch at noon?", ft.Colors.INDIGO),
    ("Grace", "Slides attached", ft.Colors.TEAL),
]


def message_tile(sender, text, color, unread=False):
    """One inbox row: the sender's initial, name and message, with a dot if unread."""
    return ft.ListTile(
        leading=ft.CircleAvatar(
            content=ft.Text(sender[0]), bgcolor=color, color=ft.Colors.WHITE
        ),
        title=ft.Text(
            sender, weight=ft.FontWeight.W_700 if unread else ft.FontWeight.W_500
        ),
        subtitle=ft.Text(text),
        trailing=ft.Container(
            width=10, height=10, border_radius=5, bgcolor=ft.Colors.PINK
        )
        if unread
        else None,
    )


async def main(page: ft.Page):
    page.title = "Inbox"
    page.padding = 0

    # Pulling is a touch gesture: mouse drags and the mouse wheel don't start it.
    # So desktop and web also get a Refresh button.
    is_phone = not page.web and page.platform in (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.IOS,
    )
    received = 0

    async def fetch_message():
        """Pretends to fetch the next message from a server, which takes a moment."""
        nonlocal received
        await asyncio.sleep(1.4)
        sender, text, color = NEW_MESSAGES[received % len(NEW_MESSAGES)]
        received += 1
        return message_tile(sender, text, color, unread=True)

    async def handle_refresh(e: ft.Event[ft.RefreshIndicator]):
        """Runs on a pull (or a Refresh click); the spinner turns until it returns."""
        message = await fetch_message()
        inbox.controls.insert(0, message)

    async def handle_refresh_click(e: ft.Event[ft.IconButton]):
        """Starts a refresh from code: same spinner and handler as a pull."""
        await indicator.show()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    ft.Container(
                        padding=ft.Padding.only(left=16, right=8, top=8),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Inbox", size=30, weight=ft.FontWeight.W_800),
                                ft.IconButton(
                                    icon=ft.Icons.REFRESH,
                                    tooltip="Refresh",
                                    visible=not is_phone,
                                    on_click=handle_refresh_click,
                                ),
                            ],
                        ),
                    ),
                    ft.Container(
                        padding=ft.Padding.only(left=16, bottom=8),
                        content=ft.Text(
                            "Pull down for new messages"
                            if is_phone
                            else "Click Refresh for new messages",
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ),
                    indicator := ft.RefreshIndicator(
                        expand=True,
                        on_refresh=handle_refresh,
                        content=(
                            inbox := ft.ListView(
                                controls=[message_tile(*m) for m in INBOX]
                            )
                        ),
                    ),
                ],
            ),
        )
    )


if __name__ == "__main__":
    ft.run(main)
