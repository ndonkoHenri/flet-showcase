import asyncio

import flet as ft
import flet_notifications as ftn

TASK_ID = 42
SNOOZE_SECONDS = 10


async def main(page: ft.Page):
    page.title = "Tasks"

    task = ft.ListTile(
        leading=ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, size=30),
        title=ft.Text("Review pull request #42", size=19, weight=ft.FontWeight.W_600),
        subtitle=ft.Text("Due today", size=15),
    )

    def mark_task_done():
        """Shows the task as done: a green check, crossed out."""
        task.leading = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=30)
        task.title.style = ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)
        task.subtitle.value = "Done from the notification"

    async def snooze_task():
        """Shows the notification again after `SNOOZE_SECONDS`."""
        task.subtitle.value = f"Snoozed for {SNOOZE_SECONDS} seconds"
        page.update()
        await asyncio.sleep(SNOOZE_SECONDS)
        await send_notification()

    async def handle_action(e: ftn.NotificationActionEvent):
        """Called when someone taps a notification button; `e.action_id` says which."""
        events.controls.insert(
            0,
            ft.Text(
                f'on_action: "{e.action_id}" (payload {e.payload})',
                font_family="monospace",
            ),
        )
        if e.action_id == "done":
            mark_task_done()
        elif e.action_id == "snooze":
            await snooze_task()
        page.update()

    notifications = ftn.Notifications(on_action=handle_action)

    async def send_notification(e: ft.Event[ft.FilledButton] = None):
        """Shows the task's notification with its Snooze and Mark done buttons."""
        snooze = ftn.NotificationAction(id="snooze", title="Snooze")
        done = ftn.NotificationAction(id="done", title="Mark done")
        await notifications.show(
            id=2,
            title="Review pull request #42",
            body="Due today. Mark it done from here.",
            payload=f"task:{TASK_ID}",
            actions=[snooze, done],
            # Android shows notifications in channels; a high-importance one pops up.
            options=ftn.NotificationOptions(
                android=ftn.AndroidOptions(
                    channel=ftn.NotificationChannel(
                        id="tasks", name="Tasks", importance=ftn.AndroidImportance.HIGH
                    )
                )
            ),
        )

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                spacing=18,
                controls=[
                    ft.Text("Tasks", size=30, weight=ft.FontWeight.W_800),
                    ft.Container(
                        border_radius=16,
                        bgcolor=ft.Colors.SURFACE_CONTAINER,
                        content=task,
                    ),
                    ft.FilledButton(
                        "Send notification",
                        icon=ft.Icons.NOTIFICATIONS,
                        on_click=send_notification,
                    ),
                    ft.Text("Events", size=18, weight=ft.FontWeight.W_700),
                    events := ft.Column(spacing=6),
                ],
            ),
        )
    )
    await notifications.request_permissions()


if __name__ == "__main__":
    ft.run(main)
