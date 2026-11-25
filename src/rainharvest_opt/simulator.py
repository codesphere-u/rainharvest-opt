"""Fewkes & Butler (2000) Yield-After-Spillage (YAS) daily rainwater tank behavioral simulation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

ROOF_RUNOFF_COEFFICIENTS: dict[str, float] = {
    "corrugated_iron": 0.88,
    "glazed_tile": 0.85,
    "asphalt_shingle": 0.80,
    "concrete_slab": 0.75,
}

DEFAULT_CANDIDATE_TANKS_L: tuple[int, ...] = (2000, 5000, 10000, 15000, 20000, 30000, 50000, 75000, 100000)


@dataclass(frozen=True)
class CatchmentSpec:
    """Roof catchment geometry, material runoff, first-flush diverter, and daily demand."""

    roof_area_m2: float
    daily_demand_liters: float
    roof_material: str = "corrugated_iron"
    first_flush_mm: float = 1.0  # Diverts initial 1 mm roof dust/debris per rain event
    initial_storage_fraction: float = 0.50

    def __post_init__(self) -> None:
        if self.roof_area_m2 <= 0 or self.daily_demand_liters <= 0:
            raise ValueError("roof_area_m2 and daily_demand_liters must be positive")
        if self.roof_material.lower() not in ROOF_RUNOFF_COEFFICIENTS:
            raise KeyError(
                f"Unknown roof_material '{self.roof_material}'. Options: {sorted(ROOF_RUNOFF_COEFFICIENTS)}"
            )
        if self.first_flush_mm < 0.0:
            raise ValueError("first_flush_mm cannot be negative")

    @property
    def runoff_coefficient(self) -> float:
        return ROOF_RUNOFF_COEFFICIENTS[self.roof_material.lower()]

    @property
    def first_flush_diverter_liters(self) -> float:
        return self.roof_area_m2 * self.first_flush_mm


@dataclass(frozen=True)
class YasSimulationResult:
    """Conservative Yield-After-Spillage (YAS) rainwater harvesting performance summary."""

    tank_capacity_liters: float
    days_simulated: int
    first_flush_diverter_liters: float
    total_rainfall_mm: float
    total_harvestable_inflow_liters: float
    total_demand_liters: float
    total_yield_supplied_liters: float
    total_shortfall_liters: float
    total_spillage_liters: float
    volumetric_reliability_pct: float
    time_reliability_pct: float
    spillage_pct_of_inflow: float
    max_consecutive_dry_days: int
    catchment_supply_to_demand_ratio: float


def simulate_yas_tank(
    catchment: CatchmentSpec,
    daily_rainfall_mm: Sequence[float],
    *,
    tank_capacity_liters: float,
) -> YasSimulationResult:
    """Run daily Yield-After-Spillage (YAS) mass balance across a daily rainfall time series."""
    if not daily_rainfall_mm:
        raise ValueError("daily_rainfall_mm must be non-empty")
    if tank_capacity_liters <= 0.0:
        raise ValueError("tank_capacity_liters must be positive")
    if any(r < 0.0 for r in daily_rainfall_mm):
        raise ValueError("Rainfall values cannot be negative")

    c_runoff = catchment.runoff_coefficient
    v_stored = tank_capacity_liters * catchment.initial_storage_fraction

    tot_rain = 0.0
    tot_inflow = 0.0
    tot_demand = 0.0
    tot_yield = 0.0
    tot_spill = 0.0
    days_fully_met = 0
    cur_dry_streak = 0
    max_dry_streak = 0

    for rain_mm in daily_rainfall_mm:
        tot_rain += rain_mm
        eff_rain = max(0.0, rain_mm - catchment.first_flush_mm) if rain_mm > 0.0 else 0.0
        inflow_l = eff_rain * catchment.roof_area_m2 * c_runoff
        demand_l = catchment.daily_demand_liters

        # Conservative YAS: today's withdrawal limited to storage already in tank
        yield_l = min(demand_l, v_stored)
        after_inflow = (v_stored - yield_l) + inflow_l
        if after_inflow > tank_capacity_liters:
            spill_l = after_inflow - tank_capacity_liters
            v_stored = tank_capacity_liters
        else:
            spill_l = 0.0
            v_stored = after_inflow

        tot_inflow += inflow_l
        tot_demand += demand_l
        tot_yield += yield_l
        tot_spill += spill_l

        if yield_l >= demand_l - 1e-6:
            days_fully_met += 1
            cur_dry_streak = 0
        else:
            cur_dry_streak += 1
            max_dry_streak = max(max_dry_streak, cur_dry_streak)

    n = len(daily_rainfall_mm)
    shortfall = max(0.0, tot_demand - tot_yield)
    vol_rel = (tot_yield / tot_demand) * 100.0 if tot_demand > 0 else 100.0
    time_rel = (days_fully_met / n) * 100.0
    spill_pct = (tot_spill / tot_inflow) * 100.0 if tot_inflow > 0 else 0.0
    supply_ratio = tot_inflow / tot_demand if tot_demand > 0 else 0.0

    return YasSimulationResult(
        tank_capacity_liters=round(tank_capacity_liters, 1),
        days_simulated=n,
        first_flush_diverter_liters=round(catchment.first_flush_diverter_liters, 1),
        total_rainfall_mm=round(tot_rain, 1),
        total_harvestable_inflow_liters=round(tot_inflow, 1),
        total_demand_liters=round(tot_demand, 1),
        total_yield_supplied_liters=round(tot_yield, 1),
        total_shortfall_liters=round(shortfall, 1),
        total_spillage_liters=round(tot_spill, 1),
        volumetric_reliability_pct=round(vol_rel, 2),
        time_reliability_pct=round(time_rel, 2),
        spillage_pct_of_inflow=round(spill_pct, 2),
        max_consecutive_dry_days=max_dry_streak,
        catchment_supply_to_demand_ratio=round(supply_ratio, 3),
    )


@dataclass(frozen=True)
class TankOptimizationResult:
    """Optimal cistern size recommendation and reliability curve across candidate volumes."""

    target_reliability_pct: float
    recommended_tank_liters: int
    achieved_reliability_pct: float
    target_met: bool
    roof_area_bottleneck_warning: str | None
    curve: tuple[YasSimulationResult, ...]


def optimize_tank_size(
    catchment: CatchmentSpec,
    daily_rainfall_mm: Sequence[float],
    *,
    target_reliability_pct: float = 90.0,
    candidate_tanks_liters: Sequence[int] = DEFAULT_CANDIDATE_TANKS_L,
) -> TankOptimizationResult:
    """Evaluate candidate tank sizes and choose the smallest cistern meeting target reliability."""
    if not candidate_tanks_liters:
        raise ValueError("candidate_tanks_liters must be non-empty")

    results = [
        simulate_yas_tank(catchment, daily_rainfall_mm, tank_capacity_liters=float(sz))
        for sz in sorted(candidate_tanks_liters)
    ]

    chosen = results[-1]
    met = False
    for r in results:
        if r.volumetric_reliability_pct >= target_reliability_pct:
            chosen = r
            met = True
            break

    warn: str | None = None
    if not met and chosen.catchment_supply_to_demand_ratio < 1.0:
        warn = (
            f"ROOF AREA BOTTLENECK: total harvestable roof inflow is only "
            f"{chosen.catchment_supply_to_demand_ratio * 100:.0f}% of demand; a larger tank cannot reach "
            f"{target_reliability_pct:.0f}% reliability without expanding roof catchment or reducing demand."
        )

    return TankOptimizationResult(
        target_reliability_pct=round(target_reliability_pct, 1),
        recommended_tank_liters=int(chosen.tank_capacity_liters),
        achieved_reliability_pct=chosen.volumetric_reliability_pct,
        target_met=met,
        roof_area_bottleneck_warning=warn,
        curve=tuple(results),
    )
