"""CLI entrypoint for rainharvest-opt."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .simulator import CatchmentSpec, optimize_tank_size


def _east_africa_bimodal_demo_rain() -> list[float]:
    """Synthetic 365-day bimodal rainfall (~1250 mm/yr, two rainy + two dry seasons)."""
    # Monthly approximate rain patterns (days with rain vs dry spells)
    monthly_mm = [50, 65, 140, 210, 170, 55, 35, 60, 110, 160, 145, 70]
    daily: list[float] = []
    for m_mm in monthly_mm:
        days_in_m = 30
        rain_days = 6 if m_mm < 70 else 12
        per_event = m_mm / rain_days
        step = days_in_m // rain_days
        for d in range(days_in_m):
            daily.append(round(per_event, 1) if (d % step == 0 and (d // step) < rain_days) else 0.0)
    return daily


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rainharvest-opt",
        description="Simulate Yield-After-Spillage (YAS) rainwater tank reliability and optimal cistern size.",
    )
    parser.add_argument("--roof-m2", type=float, default=180.0, help="Roof horizontal catchment area (m2).")
    parser.add_argument("--demand-liters", type=float, default=350.0, help="Daily water demand (L/day).")
    parser.add_argument("--material", default="corrugated_iron", help="Roof material key.")
    parser.add_argument("--target-reliability", type=float, default=90.0, help="Target volumetric reliability pct.")
    parser.add_argument("--rain-json", type=Path, default=None, help="Optional JSON array of daily rainfall (mm).")
    args = parser.parse_args(argv)

    rainfall = (
        [float(x) for x in json.loads(args.rain_json.read_text(encoding="utf-8"))]
        if args.rain_json is not None
        else _east_africa_bimodal_demo_rain()
    )
    res = optimize_tank_size(
        CatchmentSpec(
            roof_area_m2=args.roof_m2,
            daily_demand_liters=args.demand_liters,
            roof_material=args.material,
        ),
        rainfall,
        target_reliability_pct=args.target_reliability,
    )
    print(json.dumps(asdict(res), indent=2))
    return 0 if res.target_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
