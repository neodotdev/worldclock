"""Core API: no input()/print() in here, so it is safe to import anywhere."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import pytz  # only for the country -> timezones mapping

VALID_REGIONS = {"Africa", "America", "Antarctica", "Asia", "Atlantic",
                 "Australia", "Europe", "Indian", "Pacific"}
DEFAULT_FAVS = ["Asia/Kolkata", "UTC", "America/New_York", "Europe/London", "Asia/Tokyo"]


class UnknownTimezoneError(ValueError):
    """Raised when a timezone name can't be resolved."""


@dataclass(frozen=True)
class Country:
    code: str
    name: str


@dataclass(frozen=True)
class ClockReading:
    zone: str
    time: datetime  # timezone-aware

    @property
    def offset(self) -> str:
        off = self.time.strftime("%z")
        return f"UTC{off[:3]}:{off[3:]}"

    def formatted(self, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        return self.time.strftime(fmt)

    def __str__(self) -> str:
        return f"{self.zone}: {self.formatted()} ({self.offset})"


def default_db_path() -> Path:
    """~/.worldclock/worldclock.db, override with env var WORLDCLOCK_DB."""
    env = os.environ.get("WORLDCLOCK_DB")
    return Path(env) if env else Path.home() / ".worldclock" / "worldclock.db"


class WorldClock:
    """Timezone database. Use as `WorldClock()` or `with WorldClock() as wc:`.

    db_path=":memory:" gives a throwaway database (nothing written to disk).
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = str(db_path) if db_path is not None else str(default_db_path())
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.db_path)
        self._init_db()

    # ------------------------------------------------------------ lifecycle
    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "WorldClock":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _init_db(self) -> None:
        zones = available_timezones()
        if not zones:
            raise RuntimeError("No timezone data found. Run: pip install tzdata")
        db = self._db
        db.execute("CREATE TABLE IF NOT EXISTS timezones "
                   "(name TEXT PRIMARY KEY, region TEXT NOT NULL, city TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS favorites (name TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE IF NOT EXISTS countries "
                   "(code TEXT PRIMARY KEY, name TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS country_zones "
                   "(code TEXT NOT NULL, tz TEXT NOT NULL, PRIMARY KEY (code, tz))")

        if db.execute("SELECT COUNT(*) FROM timezones").fetchone()[0] == 0:
            rows = []
            for z in sorted(zones):
                if "/" in z and z.split("/")[0] in VALID_REGIONS:
                    region, city = z.split("/", 1)
                    rows.append((z, region, city.replace("_", " ")))
            rows.append(("UTC", "UTC", "UTC"))
            db.executemany("INSERT OR IGNORE INTO timezones VALUES (?,?,?)", rows)
            db.executemany("INSERT OR IGNORE INTO favorites VALUES (?)",
                           [(f,) for f in DEFAULT_FAVS])

        if db.execute("SELECT COUNT(*) FROM countries").fetchone()[0] == 0:
            for code, cname in pytz.country_names.items():
                db.execute("INSERT OR IGNORE INTO countries VALUES (?,?)", (code, cname))
                for tz in pytz.country_timezones.get(code, []):
                    db.execute("INSERT OR IGNORE INTO country_zones VALUES (?,?)", (code, tz))
        db.commit()

    # ------------------------------------------------------------ timezones
    def resolve(self, zone: str) -> str:
        """Case-insensitive exact name -> canonical IANA name."""
        row = self._db.execute(
            "SELECT name FROM timezones WHERE lower(name)=lower(?)", (zone.strip(),)
        ).fetchone()
        if row:
            return row[0]
        try:
            ZoneInfo(zone.strip())
            return zone.strip()
        except (ZoneInfoNotFoundError, ValueError):
            raise UnknownTimezoneError(f"Unknown timezone: {zone!r}") from None

    def now(self, zone: str) -> ClockReading:
        name = self.resolve(zone)
        return ClockReading(name, datetime.now(ZoneInfo(name)))

    def search(self, query: str, limit: Optional[int] = None) -> List[str]:
        q = f"%{query.strip().replace(' ', '_')}%"
        sql = "SELECT name FROM timezones WHERE name LIKE ? ORDER BY name"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._db.execute(sql, (q,))]

    def regions(self) -> List[str]:
        return [r[0] for r in self._db.execute(
            "SELECT DISTINCT region FROM timezones ORDER BY region")]

    def zones_in_region(self, region: str) -> List[str]:
        return [r[0] for r in self._db.execute(
            "SELECT name FROM timezones WHERE lower(region)=lower(?) ORDER BY name",
            (region,))]

    # ------------------------------------------------------------ countries
    def find_countries(self, query: str) -> List[Country]:
        q = query.strip()
        rows = self._db.execute(
            "SELECT code, name FROM countries WHERE name LIKE ? OR code = ? "
            "ORDER BY (lower(name) = lower(?) OR code = ?) DESC, name",
            (f"%{q}%", q.upper(), q, q.upper())).fetchall()
        return [Country(c, n) for c, n in rows]

    def country_zones(self, country: str) -> List[str]:
        """Accepts a country code ('IN') or a name ('India')."""
        code = country.strip().upper()
        if not self._db.execute("SELECT 1 FROM countries WHERE code=?", (code,)).fetchone():
            matches = self.find_countries(country)
            if not matches:
                raise ValueError(f"Unknown country: {country!r}")
            code = matches[0].code
        return [r[0] for r in self._db.execute(
            "SELECT tz FROM country_zones WHERE code=? ORDER BY tz", (code,))]

    # ------------------------------------------------------------ favorites
    def favorites(self) -> List[str]:
        return [r[0] for r in self._db.execute("SELECT name FROM favorites ORDER BY name")]

    def add_favorite(self, zone: str) -> str:
        name = self.resolve(zone)
        self._db.execute("INSERT OR IGNORE INTO favorites VALUES (?)", (name,))
        self._db.commit()
        return name

    def remove_favorite(self, zone: str) -> None:
        self._db.execute("DELETE FROM favorites WHERE lower(name)=lower(?)", (zone.strip(),))
        self._db.commit()

    def favorites_now(self) -> List[ClockReading]:
        return [self.now(z) for z in self.favorites()]

    # ------------------------------------------------------------ convert
    def convert(self, from_zone: str, to_zone: str,
                when: Union[None, str, datetime] = None) -> Tuple[ClockReading, ClockReading]:
        """Convert a time between zones. `when` = None (now), 'YYYY-MM-DD HH:MM',
        or a datetime (naive datetimes are treated as being in from_zone)."""
        src, dst = self.resolve(from_zone), self.resolve(to_zone)
        if when is None:
            dt = datetime.now(ZoneInfo(src))
        elif isinstance(when, str):
            dt = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(src))
        elif when.tzinfo is None:
            dt = when.replace(tzinfo=ZoneInfo(src))
        else:
            dt = when
        return ClockReading(src, dt.astimezone(ZoneInfo(src))), \
               ClockReading(dst, dt.astimezone(ZoneInfo(dst)))


# ---------------------------------------------------------------- shortcuts
_default: Optional[WorldClock] = None


def _wc() -> WorldClock:
    global _default
    if _default is None:
        _default = WorldClock()
    return _default


def now(zone: str) -> ClockReading:
    return _wc().now(zone)


def convert(from_zone: str, to_zone: str, when=None):
    return _wc().convert(from_zone, to_zone, when)


def search(query: str, limit: Optional[int] = None) -> List[str]:
    return _wc().search(query, limit)


def country_zones(country: str) -> List[str]:
    return _wc().country_zones(country)


def find_countries(query: str) -> List[Country]:
    return _wc().find_countries(query)
