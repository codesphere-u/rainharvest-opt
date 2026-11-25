"""Yield-After-Spillage (YAS) rainwater harvesting tank behavioral simulator & optimizer."""

from .simulator import (
    ROOF_RUNOFF_COEFFICIENTS,
    CatchmentSpec,
    TankOptimizationResult,
    YasSimulationResult,
    optimize_tank_size,
    simulate_yas_tank,
)

__all__ = [
    "ROOF_RUNOFF_COEFFICIENTS",
    "CatchmentSpec",
    "TankOptimizationResult",
    "YasSimulationResult",
    "optimize_tank_size",
    "simulate_yas_tank",
]
__version__ = "0.1.0"
