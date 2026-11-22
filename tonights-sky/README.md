# Tonight's sky

When does the Sun set, how full is the Moon, and which planets can you see after dark? The app asks the device where
it is with [flet-geolocator](https://flet.dev/docs/services/geolocator), and [astropy](https://www.astropy.org), the
Python library astronomers use, works it all out on the device. A map of the sky shows where each planet goes from
dusk to dawn.

- **Where.** On start, the app checks
  [`is_location_service_enabled()`](https://flet.dev/docs/services/geolocator#flet_geolocator.Geolocator.is_location_service_enabled)
  and [`get_permission_status()`](https://flet.dev/docs/services/geolocator#flet_geolocator.Geolocator.get_permission_status),
  calls [`request_permission()`](https://flet.dev/docs/services/geolocator#flet_geolocator.Geolocator.request_permission)
  when it hasn't asked yet, then
  [`get_current_position()`](https://flet.dev/docs/services/geolocator#flet_geolocator.Geolocator.get_current_position).
  The [`configuration`](https://flet.dev/docs/services/geolocator#flet_geolocator.Geolocator.configuration)'s
  [`accuracy`](https://flet.dev/docs/services/geolocator/types/geolocatorconfiguration#flet_geolocator.GeolocatorConfiguration.accuracy)
  is [`HIGH`](https://flet.dev/docs/services/geolocator/types/geolocatorpositionaccuracy#flet_geolocator.GeolocatorPositionAccuracy.HIGH),
  so devices that only have GPS answer too. When no position comes within 15 seconds, the app takes
  [`get_last_known_position()`](https://flet.dev/docs/services/geolocator#flet_geolocator.Geolocator.get_last_known_position)
  (phones and computers keep one; browsers don't).
- **No location?** Location turned off, permission
  [`DENIED`](https://flet.dev/docs/services/geolocator/types/geolocatorpermissionstatus#flet_geolocator.GeolocatorPermissionStatus.DENIED)
  or [`DENIED_FOREVER`](https://flet.dev/docs/services/geolocator/types/geolocatorpermissionstatus#flet_geolocator.GeolocatorPermissionStatus.DENIED_FOREVER),
  or no position at all: the app shows Lisbon's sky and says why, in orange, under the place picker.
  The header always says which place you're looking at, with its coordinates.
- **Pick a place** in the [`Dropdown`](https://flet.dev/docs/controls/dropdown): 10 cities around the world, or
  **My location** to ask the device again
  ([`on_select`](https://flet.dev/docs/controls/dropdown#flet.Dropdown.on_select)). Times are in that place's own
  time zone, from Python's `zoneinfo`. A position near none of the cities uses the device's own time zone.
- **The night before or after:** the arrows step one night at a time.
- **The astronomy:** astropy samples the night every 10 minutes, from noon to noon. The Sun's altitude gives sunset,
  the time it gets dark (12° below the horizon) and sunrise. `get_body()` gives the Moon and the five planets you can
  see without a telescope, as altitude and azimuth in an `AltAz` frame. The Moon's phase comes from the angle
  between the Sun and the Moon. astropy uses its built-in ephemeris and the Earth-rotation tables in
  `astropy-iers-data`, so nothing is downloaded and it works offline. The work runs in a thread
  (`asyncio.to_thread`), so the app stays responsive.
- **The sky map** is two [`Canvas`](https://flet.dev/docs/controls/canvas) controls in a
  [`Stack`](https://flet.dev/docs/controls/stack): stars and altitude rings below, drawn once, and the paths above, each
  a [`Path`](https://flet.dev/docs/controls/canvas/path) that draws in step by step, with a
  [`Circle`](https://flet.dev/docs/controls/canvas/circle) (and a
  [`blur_image`](https://flet.dev/docs/types/paint#flet.Paint.blur_image) glow) where the body is highest. The zenith is
  in the middle, the horizon on the rim, north up and east on the left, as when you look up. The Moon's phase is a
  `Path` too: half a circle for its edge, half an ellipse for the line between day and night, flipped south of the
  equator.
- **Tap a row** ([`on_click`](https://flet.dev/docs/controls/container#flet.Container.on_click)) to fade the other
  paths and read when and where that body is highest. Tap it again to see them all.
- The cards fade and slide in with
  [`animate_opacity`](https://flet.dev/docs/controls/layoutcontrol#flet.LayoutControl.animate_opacity) and
  [`animate_offset`](https://flet.dev/docs/controls/layoutcontrol#flet.LayoutControl.animate_offset).

|                                                                         Android                                                                          |                                                                            iOS                                                                            |                                                                       Web                                                                        |
|:--------------------------------------------------------------------------------------------------------------------------------------------------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------:|
| <img src="../.media/tonights-sky/android.gif" width="240" alt="Lisbon's sky from the GPS, picking Saturn, then Cape Town tonight and tomorrow on Android"> | <img src="../.media/tonights-sky/ios.gif" width="240" alt="Lisbon's sky from the GPS, picking Saturn, then Cape Town tonight and tomorrow on an iPhone"> | <img src="../.media/tonights-sky/web.gif" width="240" alt="Lisbon's sky from the GPS, picking Saturn, then Cape Town tonight and tomorrow in a browser"> |

In the recordings, the Android emulator, the iOS simulator and the browser are set to Lisbon. Cape Town, south of the
equator, sees the planets in the north, and its Moon is lit on the other side.

The same code runs on macOS and Windows too, where the operating system's location service (mostly from Wi-Fi) says
where the computer is. flet-geolocator has no Linux support, so on Linux the app leaves out **My location** and
starts on Lisbon. In a browser, the browser asks for permission first.

The code is in three files:

- `main.py`: the Flet app, with its cards, the place picker and what each tap does.
- `sky.py`: the astronomy with astropy, the cities and the time formatting.
- `sky_map.py`: the sky map and the Moon, drawn as canvas shapes.

## Run it

With [uv](https://docs.astral.sh/uv/):

```bash
uv run flet run           # desktop
uv run flet run --web     # browser
```

To try it on a phone, [debug](https://flet.dev/docs/cli/flet-debug) it on a connected device or emulator:

```bash
uv run flet debug android   # Android device or emulator
uv run flet debug ios       # iPhone or iOS simulator
```

To share it, [build](https://flet.dev/docs/publish) a package for any platform (desktop apps build on their own OS):

```bash
uv run flet build apk             # Android
uv run flet build ipa             # iOS
uv run flet build ios-simulator   # iOS simulator
uv run flet build macos           # macOS app
uv run flet build windows         # Windows app
uv run flet build linux           # Linux app
```

On Android and iOS, `flet build` takes astropy, pyerfa and numpy from [pypi.flet.dev](https://pypi.flet.dev), which
has them built for phones (see
[binary packages](https://flet.dev/docs/reference/binary-packages-android-ios)). There's no static web build
(`flet build web`): it runs Python inside the browser with Pyodide, which ships astropy 7.2, not the 8.0 this app
pins. In a browser, serve it with `uv run flet run --web` (or deploy it as a server app).

`pyproject.toml` declares the location permissions the builds need: Android's fine and coarse location, the message
iOS and macOS show when they ask, and the macOS location entitlement.
It also adds `tzdata`, for the cities' time zones on systems without their own time zone files, such as Android
and Windows.

## Learn more

- [Geolocator docs](https://flet.dev/docs/services/geolocator)
- [GeolocatorConfiguration](https://flet.dev/docs/services/geolocator/types/geolocatorconfiguration)
- [GeolocatorPositionAccuracy](https://flet.dev/docs/services/geolocator/types/geolocatorpositionaccuracy)
- [GeolocatorPermissionStatus](https://flet.dev/docs/services/geolocator/types/geolocatorpermissionstatus)
- [GeolocatorPosition](https://flet.dev/docs/services/geolocator/types/geolocatorposition)
- [Canvas](https://flet.dev/docs/controls/canvas)
- [Path](https://flet.dev/docs/controls/canvas/path)
- [Dropdown](https://flet.dev/docs/controls/dropdown)
- [astropy coordinates](https://docs.astropy.org/en/stable/coordinates/index.html)
