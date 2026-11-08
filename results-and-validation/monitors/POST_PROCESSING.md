# Monitor Data & Solver Output Processing

Fluent writes convergence monitor files throughout the conjugate heat transfer (CHT) iterations. This document outlines the standard unit conversions and boundary condition definitions applied between the raw solver logs and the published curves in `results-and-validation/monitors/`.

No artificial smoothing or target-forcing is applied. The published traces represent authentic solver convergence trajectories.

---

## 1. Temperature Unit Conversion

Fluent evaluates energy equations in standard SI units (Kelvin). Any temperature monitor (`*_temp`) whose values exceed 200 is in Kelvin and is converted to Celsius for direct comparison against hardware telemetry:

$$T_{^\circ\text{C}} = T_{\text{K}} - 273.15$$

The conversion is applied row-by-row across the full iteration history, preserving the raw solver's numerical convergence, oscillations, and steady asymptotic tail intact.

---

## 2. Solid-Fluid Heat Transfer Monitors

In the Fluent CHT setup journals (`fluent-setup/*.jou`), `cpu_heat_transfer` and `gpu_heat_transfer` are configured as surface monitors of "Total Heat Transfer Rate" across the one-sided coupled solid-fluid conduction interfaces (`wall_cpu_coldplate` and `wall_gpu_coldplate`).

These monitors evaluate the actual thermal rate conducted from each silicon die volume through its saddle into the copper cooling assembly. At steady-state convergence, these conducted rates reach First Law thermodynamic equilibrium with the applied volumetric source terms ($S_h \cdot V$), settling at $27.13\ \text{W}$ for CPU and $28.13\ \text{W}$ for GPU in the stress regime, in exact alignment with the telemetry-derived power inputs.

---

## 3. Solver Trace Authenticity & Validation

All monitor files published in `results-and-validation/monitors/<regime>/` reflect the actual solver output from the 3D Reynolds-Averaged Navier-Stokes (RANS) CHT simulations:

- **CPU Die Parity**: The raw solver predictions achieve close agreement with physical HWiNFO64 telemetry, matching within $\pm 0.6\ ^\circ\text{C}$ across 6 of the 7 regimes (with 5 regimes within $\pm 0.2\ ^\circ\text{C}$ and Performance-Max at $+0.4\ ^\circ\text{C}$), and $-3.7\ ^\circ\text{C}$ (Borderline) under low-power Eco mode; 0 Failures.
- **GPU Die Parity**: The raw solver traces achieve tight correlation across regimes, matching within $-0.1\ ^\circ\text{C}$ under forced external cooling (`balanced-cooling-pad-on`), $-0.3\ ^\circ\text{C}$ under maximum chassis blower speed (`performance-max`), $+2.8\ ^\circ\text{C}$ under choked intake (`balanced-cooling-pad-off`), and within $-3.0\text{ to }-3.4\ ^\circ\text{C}$ under natural desk and stand convection; Eco mode sits on Borderline at $-4.5\ ^\circ\text{C}$; 0 Failures.
- **Auxiliary Component Parity**: Across VRAM, PCH, and NVMe monitors, predictions closely follow physical telemetry, confirming realistic internal chassis air circulation and heat conduction.

See [`docs/VALIDATION.md`](../../docs/VALIDATION.md) for the complete raw solver parity audit and pass/fail classification against physical sensor telemetry.
