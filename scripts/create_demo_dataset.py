"""Generate synthetic rides for dashboard previews; no account or API is used."""

from __future__ import annotations

import argparse
import datetime as dt
import math
import random
from pathlib import Path

from ryde_cli.config import secure_write_json


def create_demo(directory: Path) -> None:
    rng = random.Random(42)
    # Public city-centre coordinates used only as anchors for generated geometry.
    hubs = [
        (13.377, 52.525),
        (13.405, 52.520),
        (13.415, 52.528),
        (13.395, 52.506),
        (13.436, 52.515),
        (13.385, 52.518),
    ]
    rides = []
    routes = {}
    for index in range(180):
        morning = index % 2 == 0
        start = dt.datetime(2026, 1, 5, 8 if morning else 17, 15) + dt.timedelta(days=index // 2)
        if start.weekday() < 5 and index % 5:
            origin, destination = (0, 1) if morning else (1, 0)
        else:
            origin, destination = rng.sample(range(len(hubs)), 2)
        one, two = hubs[origin], hubs[destination]
        duration = rng.randint(6, 24)
        end = start + dt.timedelta(minutes=duration)
        identifier = f"demo-{index + 1:03d}"
        rides.append(
            {
                "useId": identifier,
                "startTime": start.isoformat(sep=" "),
                "endTime": end.isoformat(sep=" "),
                "startGps": f"{one[0]},{one[1]}",
                "endGps": f"{two[0]},{two[1]}",
                "startAdd": f"Demo stop {origin + 1}",
                "endAdd": f"Demo stop {destination + 1}",
                "paidNum": 0 if index % 4 == 0 else 1000 + duration * 250,
                "payableNum": 1000 + duration * 250,
                "useDist": rng.randint(900, 4200),
                "monType": "NOK",
            }
        )
        if index % 4:
            bend = rng.uniform(-0.003, 0.003)
            points = []
            for step in range(25):
                fraction = step / 24
                points.append(
                    {
                        "gpsAddress": f"{one[0] + (two[0] - one[0]) * fraction + math.sin(fraction * math.pi) * bend:.6f},{one[1] + (two[1] - one[1]) * fraction + math.sin(fraction * math.pi * 2) * bend / 2:.6f}"
                    }
                )
            routes[identifier] = {
                "useId": identifier,
                "year": "2026",
                "status": "complete",
                "response": {"locus": points},
            }
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    secure_write_json(directory / "rides.raw.json", {"rides": rides})
    secure_write_json(directory / "routes-demo.raw.json", {"year": "2026", "routes": routes})
    secure_write_json(
        directory / "manifest.json",
        {
            "version": 1,
            "exportedAt": "2026-04-05T00:00:00Z",
            "rideFile": "rides.raw.json",
            "routeFiles": [{"year": "2026", "file": "routes-demo.raw.json", "count": len(routes)}],
            "counts": {
                "rides": len(rides),
                "complete": len(routes),
                "missing": len(rides) - len(routes),
                "failed": 0,
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    create_demo(args.output)
    print(f"Generated 180 demo rides in {args.output}")


if __name__ == "__main__":
    main()
