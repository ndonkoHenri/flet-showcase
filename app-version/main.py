import platform
from datetime import datetime

import flet as ft

ACCENT = "#4F46E5"
CARD = "#F4F4F8"
MUTED = "#6B6B7B"
SEEN_KEY = "app_version.last_seen"  # the version whose notes were last dismissed

# Release notes per version: add the new version on top when you bump `version` in pyproject.toml.
WHATS_NEW = {
    "1.0.0": [
        "An About screen that reads its own version and build number",
        "Device details for each platform",
        "Copy diagnostics, ready to paste into a bug report",
    ]
}
STORES = {
    "com.android.vending": "Google Play",
    "com.android.shell": "adb install",
    "com.apple": "App Store",
    "com.apple.testflight": "TestFlight",
    "com.apple.simulator": "iOS Simulator",
}


def when(moment: datetime | None) -> str:
    """A local date and time, or an empty string when the platform doesn't report it."""
    return f"{moment.astimezone():%Y-%m-%d %H:%M}" if moment else ""


def app_rows(info: ft.PackageInfo) -> list[tuple[str, str]]:
    """The app's own details as (label, value) pairs."""
    store = info.installer_store
    rows = [
        ("App name", info.app_name),
        ("Package", info.package_name),
        ("Version", info.version),
        ("Build", info.build_number),
        ("Installed from", STORES.get(store, store) if store else "Not from a store"),
        ("Installed", when(info.install_time)),
        ("Updated", when(info.update_time)),
    ]
    if info.build_signature:  # Android only: the start of the signing key's SHA-256
        rows.append(("Signature", info.build_signature[:12] + "…"))
    return rows + [("Python", platform.python_version()), ("Flet", ft.__version__)]


def device_rows(device: ft.DeviceInfo | None) -> list[tuple[str, str]]:
    """The device's model and system as (label, value) pairs, as each platform reports them."""
    match device:
        case ft.AndroidDeviceInfo():
            release = f"Android {device.version.release} (API {device.version.sdk})"
            rows = [("Device", f"{device.manufacturer} {device.model}"), ("System", release)]
        case ft.IosDeviceInfo():
            system = f"{device.system_name} {device.system_version}"
            rows = [("Device", device.model_name), ("System", system)]
        case ft.MacOsDeviceInfo():
            version = f"{device.major_version}.{device.minor_version}.{device.patch_version}"
            rows = [("Device", device.model_name), ("System", f"macOS {version}")]
        case ft.WindowsDeviceInfo():
            system = f"{device.product_name} {device.display_version}"
            rows = [("System", system), ("CPU cores", str(device.number_of_cores))]
        case ft.LinuxDeviceInfo():
            rows = [("System", device.pretty_name)]
        case ft.WebDeviceInfo():
            browser = device.browser_name.name.replace("_", " ").title()
            rows = [("Browser", browser), ("System", device.platform or "")]
        case _:
            return []
    if isinstance(device, (ft.AndroidDeviceInfo, ft.IosDeviceInfo)):
        rows.append(("Physical device", "Yes" if device.is_physical_device else "No"))
    if device.locales:
        locale = device.locales[0]
        rows.append(
            ("Language", "-".join(filter(None, [locale.language_code, locale.country_code])))
        )
    return rows


def info_row(label: str, value: str) -> ft.Row:
    """A label on the left and its value on the right."""
    return ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Text(label, size=15, color=MUTED),
            ft.Text(
                value or "—",
                size=15,
                weight=ft.FontWeight.W_600,
                expand=True,
                text_align=ft.TextAlign.RIGHT,
                selectable=True,
            ),
        ],
    )


def note_row(note: str) -> ft.Row:
    """One release note with a check mark."""
    return ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=20, color=ACCENT),
            ft.Text(note, size=15, expand=True),
        ],
    )


def card(title: str, content: ft.Control) -> ft.Container:
    """A rounded gray card with a small title on top."""
    heading = ft.Text(title, size=13, weight=ft.FontWeight.W_800, color=MUTED)
    return ft.Container(
        padding=18,
        border_radius=22,
        bgcolor=CARD,
        content=ft.Column(spacing=12, controls=[heading, content]),
    )


async def main(page: ft.Page):
    page.title = "About"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ACCENT, color_scheme=ft.ColorScheme(primary=ACCENT))
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    prefs = ft.SharedPreferences()  # kept in a variable, so Flet doesn't drop the service

    def show_whats_new(visible: bool):
        """Open or close the what's-new card."""
        whats_new.visible = visible
        whats_new_button.visible = not visible
        page.update()

    async def mark_seen():
        """Remember that this version's notes were read, and close them."""
        await prefs.set(SEEN_KEY, info.version)
        show_whats_new(False)

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.ListView(
                width=420,  # phone-shaped, centered in a wide window
                expand=True,
                spacing=16,
                padding=ft.Padding.only(left=20, right=20, top=12, bottom=20),
                controls=[
                    ft.Column(
                        spacing=6,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=84,
                                height=84,
                                border_radius=24,
                                bgcolor=ACCENT,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(
                                    ft.Icons.ROCKET_LAUNCH_ROUNDED, size=44, color=ft.Colors.WHITE
                                ),
                            ),
                            app_name := ft.Text("About", size=28, weight=ft.FontWeight.W_800),
                            version_text := ft.Text("Reading the app's details…", color=MUTED),
                            whats_new_button := ft.TextButton(
                                "What's new",
                                icon=ft.Icons.NEW_RELEASES_OUTLINED,
                                visible=False,
                                on_click=lambda: show_whats_new(True),
                            ),
                        ],
                    ),
                    whats_new := ft.Container(
                        visible=False,
                        padding=18,
                        border_radius=22,
                        bgcolor=ft.Colors.INDIGO_50,
                        content=ft.Column(
                            spacing=10,
                            controls=[
                                whats_new_title := ft.Text(size=18, weight=ft.FontWeight.W_800),
                                notes := ft.Column(spacing=8),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.END,
                                    controls=[ft.FilledButton("Got it", on_click=mark_seen)],
                                ),
                            ],
                        ),
                    ),
                    card("APP", app_list := ft.Column(spacing=10)),
                    card("DEVICE", device_list := ft.Column(spacing=10)),
                    copy_button := ft.FilledButton(
                        "Copy diagnostics",
                        icon=ft.Icons.CONTENT_COPY_ROUNDED,
                        disabled=True,
                        height=48,
                        # The copy itself is a client action, so it happens during the tap
                        # (browsers allow clipboard writes only then); this just confirms it.
                        on_click=lambda: page.show_dialog(ft.SnackBar("Diagnostics copied")),
                    ),
                    ft.Text(
                        "With flet run, these are the details of the Flet app that runs your "
                        "code. An app made with flet build shows its own.",
                        size=13,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        )
    )

    info = await page.get_package_info()
    device = await page.get_device_info()
    about_app = app_rows(info)
    about_device = [("Platform", page.platform.value), *device_rows(device)]
    app_name.value = info.app_name or "About"
    build = f" (build {info.build_number})" if info.build_number else ""
    version_text.value = f"Version {info.version}{build}"
    app_list.controls = [info_row(label, value) for label, value in about_app]
    device_list.controls = [info_row(label, value) for label, value in about_device]

    diagnostics = [f"{info.app_name} diagnostics, {datetime.now():%Y-%m-%d %H:%M}"]
    diagnostics += [f"{label}: {value or '-'}" for label, value in about_app + about_device]
    copy_button.action = ft.CopyToClipboard("\n".join(diagnostics))
    copy_button.disabled = False

    whats_new_title.value = f"What's new in {info.version}"
    news = WHATS_NEW.get(info.version) or [
        "No notes for this version. With flet run, it's the version of the Flet app running this code."
    ]
    notes.controls = [note_row(note) for note in news]
    # Show the notes once per version, like apps do after an update.
    show_whats_new(await prefs.get(SEEN_KEY) != info.version)


if __name__ == "__main__":
    ft.run(main)
