"""Tests for rainharvest-opt."""

from __future__ import annotations

import json

import pytest

from rainharvest_opt import CatchmentSpec, optimize_tank_size, simulate_yas_tank
from rainharvest_opt.cli import main as cli_main


def _bimodal_year() -> list[float]:
    # 60 wet days (15mm each), 60 dry days (0mm), repeated x3 = 360 days, 2700 mm total
    return ([15.0, 0.0, 15.0, 0.0] * 15 + [0.0] * 60) * 3


def test_yas_reliability_improves_with_larger_tank_and_first_flush_reduces_inflow() -> None:
    rain = _bimodal_year()
    catch_ff = CatchmentSpec(roof_area_m2=150.0, daily_demand_liters=300.0, first_flush_mm=1.0)
    catch_no_ff = CatchmentSpec(roof_area_m2=150.0, daily_demand_liters=300.0, first_flush_mm=0.0)

    small = simulate_yas_tank(catch_ff, rain, tank_capacity_liters=5000.0)
    big = simulate_yas_tank(catch_ff, rain, tank_capacity_liters=30000.0)
    no_ff = simulate_yas_tank(catch_no_ff, rain, tank_capacity_liters=30000.0)

    assert big.volumetric_reliability_pct > small.volumetric_reliability_pct
    assert big.max_consecutive_dry_days < small.max_consecutive_dry_days
    assert big.total_harvestable_inflow_liters < no_ff.total_harvestable_inflow_liters
    assert small.first_flush_diverter_liters == pytest.approx(150.0)


def test_optimize_tank_flags_roof_area_bottleneck() -> None:
    rain = [0.0] * 300 + [5.0] * 65  # arid 325 mm/yr
    tiny_roof = CatchmentSpec(roof_area_m2=40.0, daily_demand_liters=200.0)
    opt = optimize_tank_size(tiny_roof, rain, target_reliability_pct=90.0)
    assert opt.target_met is False
    assert opt.roof_area_bottleneck_warning is not None
    assert "ROOF AREA BOTTLENECK" in opt.roof_area_bottleneck_warning


def test_cli_demo_reaches_target_reliability(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["--roof-m2", "250", "--demand-liters", "300", "--target-reliability", "90"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["target_met"] is True
    assert out["achieved_reliability_pct"] >= 90.0
