import flet as ft

PHOTOS = {  # file in assets/: (title, photographer)
    "fjord.jpg": ("Road along the fjord", "Danny Froese"),
    "lake.jpg": ("Clouds in a mountain lake", "Ales Krivec"),
    "aurora.jpg": ("Polar lights", "Vincent Guth"),
    "dunes.jpg": ("Desert dunes", "Joe Mania"),
    "waterfall.jpg": ("Mossy waterfall", "Jacek Smoter"),
    "forest.jpg": ("Misty forest", "Jon Flobrant"),
    "coast.jpg": ("Nā Pali Coast", "Josh Austin"),
    "snow.jpg": ("Frozen forest", "invisiblepower"),
}


def photo_page(name: str) -> ft.View:
    """The photo full width, under the same Hero tag, with its title."""
    title, author = PHOTOS[name]
    return ft.View(
        route=f"/photo/{name}",
        padding=0,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        appbar=ft.AppBar(title=ft.Text(title)),
        controls=[
            ft.Hero(tag=name, content=ft.Image(src=name, fit=ft.BoxFit.FIT_WIDTH)),
            ft.Container(
                padding=20,
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Text(title, size=28, weight=ft.FontWeight.W_800),
                        ft.Text(
                            f"Photo by {author}, CC0, via Wikimedia Commons",
                            size=15,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text("Go back and it flies home to the grid.", size=17),
                    ],
                ),
            ),
        ],
    )


def main(page: ft.Page):
    page.title = "Gallery"
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL)

    async def open_photo(e: ft.Event[ft.Container]):
        await page.push_route(f"/photo/{e.control.data}")

    def tile(name: str) -> ft.Hero:
        """A square photo in the grid; the Hero tag pairs it with the big one."""
        return ft.Hero(
            tag=name,
            content=ft.Container(
                data=name,
                border_radius=16,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                on_click=open_photo,
                content=ft.Image(src=name, fit=ft.BoxFit.COVER),
            ),
        )

    gallery = ft.View(
        route="/",
        appbar=ft.AppBar(title=ft.Text("Gallery", weight=ft.FontWeight.W_800)),
        controls=[
            ft.GridView(
                expand=True,
                max_extent=220,  # 2 columns on a phone, more on wider windows
                spacing=12,
                run_spacing=12,
                padding=6,
                controls=[tile(name) for name in PHOTOS],
            )
        ],
    )

    def handle_route_change(e: ft.RouteChangeEvent | None = None):
        page.views.clear()
        page.views.append(gallery)
        if page.route.startswith("/photo/"):
            name = page.route.removeprefix("/photo/")
            if name in PHOTOS:
                page.views.append(photo_page(name))
        page.update()

    async def handle_view_pop(e: ft.ViewPopEvent):
        page.views.pop()  # the back arrow, Android's back button or gesture
        await page.push_route(page.views[-1].route)

    page.on_route_change = handle_route_change
    page.on_view_pop = handle_view_pop
    handle_route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
