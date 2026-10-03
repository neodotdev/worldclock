"""Command line + interactive menu. Run `worldclock` or `python -m worldclock`."""
from __future__ import annotations

import argparse
import os
import sys
import time

from .core import UnknownTimezoneError, WorldClock


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _line(r):
    return f"  {r.zone:<34} {r.formatted('%H:%M:%S')}  {r.formatted('%a %d %b %Y')}  {r.offset}"


def live(wc: WorldClock):
    favs = wc.favorites()
    if not favs:
        print("Favorites khaali hai.")
        return
    try:
        while True:
            _clear()
            print("=" * 66)
            print("  WORLD CLOCK        (Ctrl+C to go back)")
            print("=" * 66)
            for z in favs:
                print(_line(wc.now(z)))
            print("=" * 66)
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def _pick(wc: WorldClock, prompt="Timezone/city name: "):
    q = input(prompt).strip()
    if not q:
        return None
    res = wc.search(q)
    if not res:
        print("  Kuch nahi mila.")
        return None
    if len(res) == 1:
        return res[0]
    for i, r in enumerate(res[:20], 1):
        print(f"  {i}. {r}")
    c = input("Number select karo (enter = cancel): ").strip()
    return res[int(c) - 1] if c.isdigit() and 1 <= int(c) <= min(20, len(res)) else None


def menu(wc: WorldClock):
    text = ("\n==== WORLD CLOCK DB ====\n 1. Live world clock\n 2. Search timezone\n"
            " 3. Browse by region\n 4. Browse by country\n 5. Add favorite\n"
            " 6. Remove favorite\n 7. Convert time\n 0. Exit\n")
    while True:
        print(text)
        c = input("Choose: ").strip()
        if c == "0":
            return
        if c == "1":
            live(wc)
        elif c == "2":
            for z in wc.search(input("Search: "), limit=30):
                print(_line(wc.now(z)))
        elif c == "3":
            regs = wc.regions()
            for i, r in enumerate(regs, 1):
                print(f"  {i}. {r}")
            n = input("Region number: ").strip()
            if n.isdigit() and 1 <= int(n) <= len(regs):
                for z in wc.zones_in_region(regs[int(n) - 1]):
                    print(_line(wc.now(z)))
        elif c == "4":
            found = wc.find_countries(input("Country name/code: "))
            if not found:
                print("  Country nahi mili.")
                continue
            if len(found) > 1:
                for i, co in enumerate(found[:20], 1):
                    print(f"  {i}. {co.name} ({co.code})")
                n = input("Number: ").strip()
                if not (n.isdigit() and 1 <= int(n) <= min(20, len(found))):
                    continue
                found = [found[int(n) - 1]]
            zs = wc.country_zones(found[0].code)
            print(f"\n  {found[0].name} - {len(zs)} timezone(s)")
            for z in zs:
                print(_line(wc.now(z)))
        elif c == "5":
            z = _pick(wc)
            if z:
                print("  Added:", wc.add_favorite(z))
        elif c == "6":
            favs = wc.favorites()
            for i, f in enumerate(favs, 1):
                print(f"  {i}. {f}")
            n = input("Remove number: ").strip()
            if n.isdigit() and 1 <= int(n) <= len(favs):
                wc.remove_favorite(favs[int(n) - 1])
        elif c == "7":
            a, b = _pick(wc, "From: "), None
            if a:
                b = _pick(wc, "To: ")
            if a and b:
                raw = input("Time YYYY-MM-DD HH:MM [enter = now]: ").strip() or None
                try:
                    s, d = wc.convert(a, b, raw)
                    print(f"\n  {s}\n  {d}")
                except ValueError:
                    print("  Format galat hai.")
        else:
            print("  Invalid option.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="worldclock", description="World clock + timezone DB")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("now", help="current time in a zone"); s.add_argument("zone")
    s = sub.add_parser("search", help="search timezones"); s.add_argument("query")
    s = sub.add_parser("country", help="zones of a country"); s.add_argument("country")
    s = sub.add_parser("convert", help="convert time between zones")
    s.add_argument("from_zone"); s.add_argument("to_zone")
    s.add_argument("--when", help='"YYYY-MM-DD HH:MM" in from_zone (default: now)')
    sub.add_parser("live", help="live clock of favorites")
    args = p.parse_args(argv)

    with WorldClock() as wc:
        try:
            if args.cmd is None:
                menu(wc)
            elif args.cmd == "now":
                print(wc.now(args.zone))
            elif args.cmd == "search":
                print("\n".join(wc.search(args.query)) or "No match")
            elif args.cmd == "country":
                for z in wc.country_zones(args.country):
                    print(wc.now(z))
            elif args.cmd == "convert":
                s, d = wc.convert(args.from_zone, args.to_zone, args.when)
                print(s); print(d)
            elif args.cmd == "live":
                live(wc)
        except (UnknownTimezoneError, ValueError) as e:
            print("Error:", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
