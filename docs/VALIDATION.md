# CFD Model Validation & Telemetry Parity

This document details the validation methodology, parity audit, and physical correlation between the 3D Reynolds-Averaged Navier-Stokes (RANS) Conjugate Heat Transfer (CHT) simulations and physical hardware telemetry from the MSI GF63 Thin 12VF chassis.

---

## The Verification Gate

The repository includes an automated verification script [`analysis/verify_consistency.py`](../analysis/verify_consistency.py) that evaluates raw solver outputs against hardware telemetry logs:

```bash
cd analysis && python3 verify_consistency.py
```

The gate checks:
1. **File Format & Numerical Integrity**: Fluent `.out` file structure, strictly increasing iterations, and valid numeric columns ($n \ge 200$ rows).
2. **Units & Envelope**: Conversion from Fluent SI Kelvin to Celsius ($T_{^\circ\text{C}} = T_{\text{K}} - 273.15$), confirming temperatures remain within physical boundaries ($15\ ^\circ\text{C} \le T \le 130\ ^\circ\text{C}$) and powers are positive.
3. **Parity Bands**: Evaluation against physical sensor logs using standard CFD validation tolerances:
   - **Temperatures**:
     * **PASS**: CPU $|\Delta T| \le 1.0\ ^\circ\text{C}$; GPU $|\Delta T| \le 4.0\ ^\circ\text{C}$; Auxiliary $|\Delta T| \le 4.0\ ^\circ\text{C}$
     * **BORDERLINE**: $|\Delta T| \le 5.0\ ^\circ\text{C}$ (quiet low-RPM regimes with free-convective boundary layers)
     * **FAIL**: $|\Delta T| > 5.0\ ^\circ\text{C}$ (0 failures across all regimes)
   - **Heat Transfers (Watts)**:
     * **PASS**: $|\Delta Q| \le 0.05\ \text{W}$ or relative error $E_Q \le 1.0\%$
     * **BORDERLINE**: $E_Q \le 3.0\%$
     * **FAIL**: $E_Q > 5.0\%$
4. **Cross-Artifact Consistency**: Verifies applied source terms, boundary conditions, and exact solid body counts (36 heat sources, including 4 GPU DrMOS and 6 CPU DrMOS stages) in `fluent-setup/*.jou`, `summary.json`, and `parity_table.csv` match the telemetry engine. Audits 56 primary telemetry targets across all 105 published solver monitor series.

---

## Parity Results Across All Regimes

The table below summarizes the unedited, raw Fluent solver monitor output compared directly to steady-state HWiNFO64 physical telemetry targets:

| Operating Regime | CPU Meas (°C) | CPU Raw CFD (°C) | CPU Raw Error | Status | GPU Meas (°C) | GPU Raw CFD (°C) | GPU Raw Error | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Eco Mode** (`eco.CSV`) | 57.4 | 53.6 | −3.7 °C | Borderline | 45.9 | 41.4 | −4.5 °C | Borderline |
| **Balanced Flat Desk** (`balanced-flat-desk.CSV`) | 61.3 | 60.8 | −0.4 °C | **PASS** | 48.6 | 45.4 | −3.2 °C | **PASS** |
| **Balanced Raised Stand** (`bal-stand.CSV`) | 57.8 | 57.5 | −0.3 °C | **PASS** | 45.2 | 42.4 | −2.8 °C | **PASS** |
| **Balanced Cooling Pad ON** (`bal-cooling-pad-on.CSV`) | 58.3 | 58.5 | +0.2 °C | **PASS** | 46.3 | 46.1 | −0.2 °C | **PASS** |
| **Balanced Cooling Pad OFF** (`bal-cooling-pad-off.CSV`) | 73.5 | 72.8 | −0.6 °C | **PASS** | 57.0 | 59.5 | +2.4 °C | **PASS** |
| **Performance Flat Desk** (`performance-flat-desk.CSV`) | 58.0 | 58.3 | +0.3 °C | **PASS** | 45.8 | 42.7 | −3.1 °C | **PASS** |
| **Performance-Max Stress** (`performance-max.CSV`) | 94.7 | 95.2 | +0.5 °C | **PASS** | 71.2 | 70.8 | −0.4 °C | **PASS** |

### Summary Statistics
- **CPU Die Parity**: **6 of 7 regimes PASS** within $\pm 0.6\ ^\circ\text{C}$ (well inside the $\pm 1.0\ ^\circ\text{C}$ pass band); 1 regime is borderline ($-3.7\ ^\circ\text{C}$ in quiet Eco mode); **0 Fail**.
- **GPU Die Parity**: **6 of 7 regimes PASS** within $\pm 3.2\ ^\circ\text{C}$ (inside the $\pm 4.0\ ^\circ\text{C}$ pass band); 1 regime is borderline ($-4.5\ ^\circ\text{C}$ in Eco mode); **0 Fail**.

---

## Physical Interpretation & Engineering Findings

### 1. High CPU Prediction Accuracy
The conjugate heat transfer model demonstrates exceptional correlation on the CPU package:
- Across Balanced Flat Desk, Raised Stand, Cooling Pad ON, Cooling Pad OFF, and Performance Flat Desk, the raw CFD solver prediction lands within **0.2 to 0.6 °C** of hardware measurements.
- In the maximum Cooler Boost stress case (`performance-max`), CFD predicts **95.2 °C** against a measured **94.7 °C** (+0.5 °C error), validating the model's accuracy under high-heat-flux and high-mass-flow conditions.
- Under the choked air path (`balanced-cooling-pad-off`), the solver accurately captures the severe thermal penalty (CPU reaching 72.8 °C vs 73.5 °C measured), demonstrating the model's responsiveness to inlet boundary restrictions.

### 2. High GPU Prediction Accuracy
The GPU thermal model correlates tightly with physical sensor telemetry across all convective regimes:
- Under active forced cooling (Cooling Pad ON at $-0.2\ ^\circ\text{C}$ and Performance-Max at $-0.4\ ^\circ\text{C}$), CFD and telemetry show near-perfect agreement.
- Under natural desk and stand convection, GPU die errors remain closely bounded within $-2.8\text{ to }-3.2\ ^\circ\text{C}$, reflecting minor contact resistance across the GPU coldplate and die spreader interface.

### 3. Stress-Case Component Analysis
Under the 76.1 W sustained Cooler Boost stress regime (`performance-max`), auxiliary board components remain tightly bounded within engineering parity limits:
- **VRAM Memory Junction**: CFD solver predicts $82.8\ ^\circ\text{C}$ against $81.7\ ^\circ\text{C}$ measured on the GPU Memory Junction ($+1.1\ ^\circ\text{C}$ delta), accurately reflecting the thermal conduction path from the 6 GDDR6 dies through the shared thermal pads to the cooling assembly.
- **NVMe SSD Drive Temperature**: The CFD monitor converges to $38.4\ ^\circ\text{C}$ against $38.0\ ^\circ\text{C}$ physical telemetry ($+0.4\ ^\circ\text{C}$ delta), capturing the effective cooling delivered across the M.2 slot by the high chassis convective airflow provided by Cooler Boost.
- **PCH Chipset**: The solver stabilizes at $68.8\ ^\circ\text{C}$ against $69.5\ ^\circ\text{C}$ telemetry ($-0.7\ ^\circ\text{C}$ delta), validating the lumped $R_\text{PCH} \approx 22.1\ \text{K/W}$ thermal coupling across the southbridge package.

### 4. Aerodynamic Impedance & Choked Intake
Fitting system pressure drop against mass flow ($\Delta P = K \cdot \dot{m}^2$) across all cases confirms physical flow behavior:
- Unchoked regimes (desk, stand, pad-on, performance-max) follow the internal chassis curve with $K \approx 1.42\text{--}1.49 \times 10^6\ \text{Pa/(kg/s)}^2$.
- The choked intake case (`balanced-cooling-pad-off`) shifts upward to $K \approx 1.88 \times 10^6\ \text{Pa/(kg/s)}^2$, an increase of ~28% in hydraulic resistance. This quantitatively models the physical restriction caused by resting the chassis flush against an unpowered cooling pad.

### 5. First-Law Energy Balance Closure
Across the seven regimes, the convective enthalpy carried by exhaust airflow ($Q_\text{air} = \dot{m} c_p \Delta T_\text{air}$) accounts for **92.7% to 95.8%** of the total sustained board heat release ($Q_\text{board}$):
- Forced convection through the exhaust fin stack accounts for 92.7% (choked intake) to 95.8% (cooling pad forced intake) of dissipated thermal wattage.
- The remaining **4.2% to 7.3%** is dissipated through the outer chassis enclosure walls via natural convection ($h_\text{ext} \approx 5.0\ \text{W/(m}^2\text{ K)}$) and radiative transfer to the local ambient, providing complete First Law thermodynamic closure ($Q_\text{air} + Q_\text{chassis} = Q_\text{board}$).
- Mass flow continuity between the blower intake and radiator exhaust is conserved with net imbalance residuals settling between **9.8 and 26.8 ppm** (residual mass flux $< 1.2 \times 10^{-7}\ \text{kg/s}$), fully converged across all runs.
