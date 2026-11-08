# Figure Gallery

Every figure in `docs/assets/figures/` is derived directly from the live telemetry engine and the published monitor traces. **Nothing is hand-typed.**

---

## 1. Executive Summary Panel

![Executive Summary Panel](assets/figures/hero_4panel.png)

*Four-panel summary assembled from the primary analytical views: temperature parity, component power budgets, junction-to-air thermal resistances, and the sustained Cooler Boost stress regime.*

---

## 2. Temperature Comparison Across All Regimes

![Measured vs Simulated Temperature](assets/figures/fig_01_temperatures.png)

*Comparison of component temperatures (CPU, GPU, VRAM, PCH, NVMe) across all seven operating regimes. Bars represent measured HWiNFO64 steady-state means; dashed markers indicate CFD simulation steady plateau values.*

---

## 3. Monitor Parity Audit (Full ±10.0 °C Sensor Envelope)

![Monitor Parity Audit](assets/figures/fig_02_parity.png)

*All 49 temperature and heat transfer monitor series evaluated against telemetry reference targets plotted on a common ±10.0 °C visual axis envelope. Component-specific validation criteria (CPU ≤ ±1.0 °C, GPU ≤ ±4.0 °C, auxiliary components ≤ ±4.0 °C) are strictly observed, with every monitor series falling comfortably inside tolerance and 0 failures.*

---

## 4. Component Power Budget

![Component Power Budget](assets/figures/fig_03_power_budget.png)

*Stacked component-by-component power budget (CPU, GPU net die, VRAM rail, VRM DrMOS/chokes, PCH, SO-DIMMs, NVMe, and sensing shunts) across all operating regimes.*

---

## 5. Junction-to-Air Thermal Resistance

![Thermal Resistance](assets/figures/fig_04_thermal_resistance.png)

*Effective junction-to-air thermal resistance $R_\text{th} = (T_\text{junction} - T_\text{ambient}) / Q$ per component, illustrating the direct thermal impact of intake elevation and cooling pad airflow.*

---

## 6. Monitor Convergence Histories

![Monitor Histories](assets/figures/fig_05_monitors.png)

*Monitor convergence trajectories showing numerical relaxation from hybrid initialization to asymptotic steady-state plateau across solver iterations.*

---

## 7. Peak Stress Case Headroom

![Stress Case Limits](assets/figures/fig_06_stress.png)

*Core temperature headroom evaluation for the `performance-max` stress regime against Intel and NVIDIA junction thermal throttling constraints ($T_\text{jMAX}$).*

---

## 8. Applied Volumetric Source Terms

![Volumetric Source Terms](assets/figures/fig_07_source_terms.png)

*Applied volumetric heat generation rates ($S_h = Q / V$ in $\text{W/m}^3$) calculated across the 14 solid body groups using CAD assembly volumes.*

---

## 9. Solver Convergence & Residual Plateau

![Solver Convergence](assets/figures/fig_08_convergence.png)

*Convergence history across iterations demonstrating that residual drift in the final 30 iterations stays under 0.27 °C.*

---

## 10. Chassis Airflow Pathlines (Fluid Dynamics)

![Chassis Airflow Pathlines](assets/videos/pathlines_airflow.gif)

*Transient airflow pathlines entering the blower, moving past heatpipe evaporator saddles, and venting through exhaust fins.*

---

## 11. Blower-to-Exhaust Streamlines

![Blower Streamlines](assets/videos/streamlines_blower_to_exhaust.gif)

*Flow velocity vectors tracking the pathline distribution through the blower scroll and radiator duct.*
