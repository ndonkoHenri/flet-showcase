# Notification action buttons

A notification with **Snooze** and **Mark done** buttons. Tapping a button calls a Python function
([`on_action`](https://flet.dev/docs/services/notifications#flet_notifications.Notifications.on_action)),
which learns which button was tapped ([`e.action_id`](https://flet.dev/docs/services/notifications/types/notificationactionevent#flet_notifications.NotificationActionEvent.action_id))
and which task it belongs to ([`e.payload`](https://flet.dev/docs/services/notifications/types/notificationevent#flet_notifications.NotificationEvent.payload)):

- **Mark done** crosses the task out in the app.
- **Snooze** shows the notification again 10 seconds later.

| Android |
| :---: |
| <img src="../.media/notification-actions/android.gif" width="240" alt="Tapping Mark done in an Android notification marks the task done in the app"> |

The same code runs on iOS, macOS and Windows. On Linux and the web, the buttons appear where the system supports them.

## Run it

With [uv](https://docs.astral.sh/uv/):

```bash
uv run flet run           # desktop
uv run flet run --web     # browser
```

On your phone, [debug](https://flet.dev/docs/cli/flet-debug) the app on a connected device or emulator, or
[build](https://flet.dev/docs/publish) an installable package:

```bash
uv run flet debug android   # run it on a connected Android device or emulator
uv run flet debug ios       # run it on a connected iPhone or simulator

uv run flet build apk       # Android package
uv run flet build ipa       # iOS package
```

## Learn more

- [Notifications docs](https://flet.dev/docs/services/notifications)
- [`NotificationAction`](https://flet.dev/docs/services/notifications/types/notificationaction): every option a button has, such as
  [`foreground`](https://flet.dev/docs/services/notifications/types/notificationaction#flet_notifications.NotificationAction.foreground) (open the app or stay in the background),
  [`cancel_notification`](https://flet.dev/docs/services/notifications/types/notificationaction#flet_notifications.NotificationAction.cancel_notification), [`destructive`](https://flet.dev/docs/services/notifications/types/notificationaction#flet_notifications.NotificationAction.destructive),
  [`require_authentication`](https://flet.dev/docs/services/notifications/types/notificationaction#flet_notifications.NotificationAction.require_authentication) and [`input`](https://flet.dev/docs/services/notifications/types/notificationaction#flet_notifications.NotificationAction.input) (inline reply)
