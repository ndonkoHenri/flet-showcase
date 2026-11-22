"""The astronomy and the cities: tonight's Sun, Moon and planets for a place, with astropy."""

import math
import os
from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STEP = 10  # minutes between two samples of the night

# Name in astropy, label, color: the Moon and the five planets you can see without a telescope.
BODIES = [
    ("moon", "Moon", "#E9E4CF"),
    ("mercury", "Mercury", "#B9C2D6"),
    ("venus", "Venus", "#FFE08A"),
    ("mars", "Mars", "#FF7657"),
    ("jupiter", "Jupiter", "#F5B97F"),
    ("saturn", "Saturn", "#7FD3FF"),
]
# City: latitude, longitude, time zone.
CITIES = {
    "Auckland": (-36.8485, 174.7633, "Pacific/Auckland"),
    "Buenos Aires": (-34.6037, -58.3816, "America/Argentina/Buenos_Aires"),
    "Cairo": (30.0444, 31.2357, "Africa/Cairo"),
    "Cape Town": (-33.9249, 18.4241, "Africa/Johannesburg"),
    "Dubai": (25.2048, 55.2708, "Asia/Dubai"),
    "Lagos": (6.5244, 3.3792, "Africa/Lagos"),
    "Lisbon": (38.7223, -9.1393, "Europe/Lisbon"),
    "London": (51.5072, -0.1276, "Europe/London"),
    "New York": (40.7128, -74.006, "America/New_York"),
    "Tokyo": (35.6762, 139.6503, "Asia/Tokyo"),
}

# Phones don't let an app write to its home folder, where astropy keeps its config and cache:
# point astropy at the app's own storage there.
if os.environ.get("FLET_APP_STORAGE_DATA"):
    for var, sub in (("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache")):
        path = os.path.join(os.environ["FLET_APP_STORAGE_DATA"], sub)
        os.makedirs(os.path.join(path, "astropy"), exist_ok=True)
        os.environ.setdefault(var, path)


def night_sky(lat: float, lon: float, days: int = 0) -> dict:
    """The night at (lat, lon), `days` after tonight: Sun times, Moon phase, bodies up after dark."""
    # Imported here, in a worker thread: astropy takes a few seconds to load on a phone.
    import astropy.units as u
    import numpy as np
    from astropy.coordinates import AltAz, EarthLocation, GeocentricTrueEcliptic, get_body
    from astropy.time import Time
    from astropy.utils import iers

    iers.conf.auto_download = False  # use the Earth-rotation tables astropy-iers-data bundles

    here = EarthLocation(lat=lat, lon=lon)  # degrees
    # The night belongs to the local solar day that started at noon: after midnight it's still tonight.
    now = Time.now() + days * u.day
    solar_day = (now + (lon / 15 - 12) * u.hour).to_datetime().date()
    noon = Time(f"{solar_day} 12:00") - lon / 15 * u.hour
    times = noon + np.arange(0, 24 * 60 + 1, STEP) * u.min  # noon to noon: the night in the middle
    night = AltAz(obstime=times, location=here)
    sun_alt = get_body("sun", times, here).transform_to(night).alt.deg

    def crossing(level: float, rising: bool, after: int = 0) -> tuple[int | None, datetime | None]:
        """When the Sun's altitude crosses `level` degrees, going up or down."""
        for i in range(after, len(times) - 1):
            a, b = sun_alt[i] - level, sun_alt[i + 1] - level
            if (a < 0 <= b) if rising else (a >= 0 > b):
                return i, (times[i] + (-a / (b - a)) * STEP * u.min).to_datetime(UTC)
        return None, None

    i_set, sunset = crossing(-0.833, rising=False)  # upper edge on the horizon, with refraction
    i_dusk, dusk = crossing(-12, rising=False)  # dark enough to see the planets
    _, dawn = crossing(-12, rising=True, after=i_dusk or 0)
    _, sunrise = crossing(-0.833, rising=True, after=i_set or 0)

    dark = sun_alt < -12
    dark_samples = np.flatnonzero(dark)
    bodies = []
    for name, label, color in BODIES:
        body = get_body(name, times, here).transform_to(night)
        alt, az = body.alt.deg, body.az.deg
        up = np.flatnonzero(dark & (alt > 0))  # above the horizon, after dark
        if len(up) == 0 or alt[up].max() < 10:  # skip bodies that stay low in the haze
            continue
        top = up[np.argmax(alt[up])]
        bodies.append(
            {
                "name": label,
                "color": color,
                "track": [(int(i), float(alt[i]), float(az[i])) for i in up],
                # Up from dark (or its rise) until dawn (or its set).
                "start": dusk if up[0] == dark_samples[0] else times[up[0]].to_datetime(UTC),
                "end": dawn if up[-1] == dark_samples[-1] else times[up[-1]].to_datetime(UTC),
                "peak_alt": float(alt[top]),
                "peak_az": float(az[top]),
                "peak_time": times[top].to_datetime(UTC),
            }
        )
    bodies.sort(key=lambda b: b["start"])  # evening first, dawn last

    # The Moon's phase at dusk (or now, where it never gets dark), from the Sun-Moon angle.
    t = Time(dusk) if dusk else now
    sun, moon = get_body("sun", t), get_body("moon", t)
    elongation = sun.separation(moon).rad
    phase_angle = math.atan2(
        sun.distance.au * math.sin(elongation),
        moon.distance.au - sun.distance.au * math.cos(elongation),
    )
    lit = (1 + math.cos(phase_angle)) / 2
    ecliptic = GeocentricTrueEcliptic(equinox=t)
    ahead = (moon.transform_to(ecliptic).lon.deg - sun.transform_to(ecliptic).lon.deg) % 360
    waxing = ahead < 180  # 0 at new moon, 180 at full moon
    if lit < 0.03 or lit > 0.97:
        phase = "New moon" if lit < 0.5 else "Full moon"
    elif abs(lit - 0.5) < 0.04:
        phase = "First quarter" if waxing else "Last quarter"
    else:
        phase = ("Waxing " if waxing else "Waning ") + ("crescent" if lit < 0.5 else "gibbous")
    return {
        "date": solar_day,
        "sunset": sunset,
        "dusk": dusk,
        "dawn": dawn,
        "sunrise": sunrise,
        "moon_lit": lit,
        "waxing": waxing,
        "phase": phase,
        "bodies": bodies,
    }


def city_place(name: str) -> dict:
    """A listed city's position and time zone (UTC where Python has no time zone data)."""
    lat, lon, zone_name = CITIES[name]
    try:
        zone, zone_label = ZoneInfo(zone_name), f"{name} time"
    except ZoneInfoNotFoundError:
        zone, zone_label = UTC, None
    return {"name": name, "lat": lat, "lon": lon, "zone": zone, "zone_label": zone_label}


def nearest_city(lat: float, lon: float) -> str | None:
    """The listed city within 40 km of (lat, lon), if any."""

    def km(city: str) -> float:
        """Great-circle distance to the city."""
        c_lat, c_lon, _ = CITIES[city]
        p1, p2 = math.radians(lat), math.radians(c_lat)
        a = (
            math.sin((p2 - p1) / 2) ** 2
            + math.cos(p1) * math.cos(p2) * math.sin(math.radians(c_lon - lon) / 2) ** 2
        )
        return 12742 * math.asin(math.sqrt(a))

    city = min(CITIES, key=km)
    return city if km(city) < 40 else None


def device_place(lat: float, lon: float) -> dict:
    """The device's position, with the time zone of a listed city near it, else the device's own."""
    if city := nearest_city(lat, lon):
        return {**city_place(city), "lat": lat, "lon": lon}
    zone = datetime.now().astimezone().tzinfo
    return {
        "name": "Your location",
        "lat": lat,
        "lon": lon,
        "zone": zone,
        "zone_label": "your time",
    }


def hm(when: datetime | None, zone: tzinfo) -> str:
    """A UTC time as hours:minutes in `zone`."""
    return when.astimezone(zone).strftime("%H:%M") if when else "--:--"


def utc_offset(zone: tzinfo, when: datetime) -> str:
    """UTC+1, UTC-3, UTC+5:30."""
    minutes = round(when.astimezone(zone).utcoffset().total_seconds() / 60)
    hours, rest = divmod(abs(minutes), 60)
    return f"UTC{'-' if minutes < 0 else '+'}{hours}" + (f":{rest:02}" if rest else "")


def compass(az: float) -> str:
    """N, NE, E... for an azimuth in degrees."""
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][round(az / 45) % 8]


def night_name(days: int) -> str:
    """Tonight, Tomorrow night, In 3 nights, 2 nights ago..."""
    if days == 0:
        return "Tonight"
    if days == 1:
        return "Tomorrow night"
    if days == -1:
        return "Last night"
    return f"In {days} nights" if days > 0 else f"{-days} nights ago"
