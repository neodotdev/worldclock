# 🌍 worldclock

World clock + timezone database for Python. Search zones by **region or country**, convert times, and run a live clock. Use it as a **library** or a **CLI**.

## Install

```
pip install git+https://github.com/neodotdev/worldclock.git
```

Needs Python 3.9+.

## Use in your code

```python
from worldclock import WorldClock, now, convert, search

print(now("Asia/Kolkata"))
print(search("tokyo"))

src, dst = convert("Asia/Kolkata", "America/New_York", "2026-10-05 10:00")
print(src, "->", dst)

with WorldClock() as wc:
    print(wc.country_zones("US"))      # all 29 US zones
    wc.add_favorite("Europe/Paris")
    for r in wc.favorites_now():
        print(r.zone, r.formatted("%H:%M"), r.offset)
```

## CLI

```
worldclock                 # interactive menu
worldclock now Asia/Tokyo
worldclock country India
worldclock convert Asia/Kolkata Europe/London --when "2026-10-05 10:00"
worldclock live            # ticking clock of your favorites
```

## Features

- 400+ timezones stored in a local SQLite database
- Browse by region (Asia, Europe...) or by country
- Time converter with DST handled
- Favorites list and live ticking clock
- No input()/print() in the library code, safe to import anywhere

## Notes

DB is stored at `~/.worldclock/worldclock.db` (override with env var `WORLDCLOCK_DB`). Use `WorldClock(":memory:")` for a throwaway DB.

## License

MIT
