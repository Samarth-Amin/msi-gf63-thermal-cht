# Methodology

How an 86-body CAD model, seven live HWiNFO64 logs and one ANSYS Fluent CHT
solve were turned into a validated thermal model - and, more importantly, how
the heat load was derived from measurement instead of from a spec sheet.

## 1. The geometry

The model is the **MSI GF63 Thin 12VF/12Vx**, a 15.6-inch chassis with a 12th-gen
Intel H-series CPU and an NVIDIA RTX 4050/4060-class GPU sharing a heatpipe
cooler with a single blower: three heatpipes, one coldplate, one fin stack, one
fan seat.

Built parametrically in SolidWorks so a geometry change propagates. The 86 solid
bodies are grouped into the functional blocks that matter thermally:

- dies: CPU, GPU, PCH, NVMe controller, two NAND packages
- VRAM: 6 GDDR6 chips fed from the FBVDD rail
- VRM: 6 CPU DrMOS stages, 4 GPU stages, 5 CPU chokes, 3 GPU chokes
- passive/board: 2 SO-DIMMs, 4 current shunts
- cooling: copper CPU coldplate, aluminium GPU coldplate, 3 heatpipes, radiator
  fins, blower shroud

**Every volume in `telemetry-data/source_terms.py` is measured from this model.**
That is the single source of truth; the same table feeds the S_h derivation and
`fluent-setup/*.jou`.

## 2. Materials

| material | k (W/m-K) | used for |
|---|---:|---|
| copper | 387.6 | CPU coldplate, heatpipes |
| aluminium | 202.4 | GPU coldplate, radiator fins, shroud |
| silicon | 148.0 | CPU / GPU / PCH / NVMe dies |
| FR-4 in-plane / through-plane | 18.0 / 0.35 | PCB - orthotropic, this matters |
| EMC / ferrite | 1.5-5.0 | SMD bodies, inductors |
| heatpipe effective | 15000-25000 | two-phase vapour chamber |

FR-4 being modelled orthotropically is not cosmetic: with 0.35 through-plane the
board is a better insulator than conductor, and assuming isotropy moves the die
temperatures by several degrees.

### Heatpipe Equivalent Conduction Approximation
The sintered copper heatpipes are modeled using an isotropic equivalent thermal conductivity ($k_\text{eff} = 15,000\text{--}25,000\ \text{W/(m K)}$). In steady-state operation within standard heat flux envelopes (< 30 W per 6 mm flattened pipe), the internal phase-change cycle (evaporation, high-speed vapor core flow, and wick capillary condensation) operates well below capillary, boiling, and sonic limits. Approximating this lumped two-phase cycle as an ultra-conductive solid avoids resolving complex multiphase liquid-vapor free interfaces while preserving authentic evaporator-to-condenser $\Delta T$ drops (~1.0 K at balanced loads to 3.4 K at full stress). Transient vapor-slug dynamics, dryout limits, and boiling hysteresis are intentionally excluded.

## 3. Boundary conditions

- **blower velocity inlet**: sized from the centrifugal blower fan curve across OEM embedded controller (EC) profile points (2200 to 6000 RPM) feeding the single fan intake throat, effective through-flow area $A = 855.30\ \text{mm}^2$ ($8.553 \times 10^{-4}\ \text{m}^2$), hydraulic diameter $D_h = 0.033\ \text{m}$. Mass flows span from $0.00318\ \text{kg/s}$ ($3.20\ \text{m/s}$) under quiet desk operation to $0.01002\ \text{kg/s}$ ($10.13\ \text{m/s}$) under full Cooler Boost, calculated at in-situ air density $\rho = P / (R_\text{air} T_\text{inlet})$.
- **duct exits**: pressure outlets, 0 Pa gauge static pressure.
- **outer chassis shell**: natural external convection boundary ($h = 5.0\ \text{W/(m}^2\text{K)}$) to ambient air ($T_\infty = T_\text{inlet}$) across the magnesium-aluminum bottom plate and plastic top deck ($A_\text{ext} \approx 0.14\ \text{m}^2$), accounting for the natural external heat loss of 4% to 7% of total dissipation.
- **internal interfaces**: conservative coupled conjugate heat transfer walls with localized thermal interface resistances where applicable.

## 4. The load: telemetry, not spec sheets

This is the part that decides whether the model is worth anything.

A review of this machine reports a 55 W CPU and 40.5 W GPU under stress. The
**measured log disagrees**: `performance-max.CSV` shows a sustained PL1 of about
28 W and a measured mean CPU package power of **27.13 W**, GPU net **28.13 W**.
The measured numbers win. Anywhere the review conflicts with the instrument, the
instrument is used, and the README says so explicitly.

The derivation chain in `telemetry-data/source_terms.py`:

```
raw HWiNFO64 CSV -> sensor means -> per-body Q -> S_h = Q / V
```

1. **CPU die** = `CPU Package Power [W]` mean. This is the package draw, already
   including integrated losses, so no rail correction is applied.
2. **GPU die** = `GPU Power [W]` **minus** `GPU FBVDD Output Power [W]`. HWiNFO64
   reports total board draw on the GPU sensor; the FBVDD rail feeds the VRAM
   chips, which are separate bodies in the model. Subtracting it is what stops
   the VRAM power being counted twice - once in the die and once in the chips.
3. **VRAM chips** = the FBVDD rail mean, split across 6 bodies.
4. **VRM losses** = 10% of the rail being fed (7% DrMOS + 3% chokes), split by
   the per-stage body count.
5. **PCH** = estimated as `(T_PCH - T_inlet) / 22.1 K/W`. HWiNFO64's PCH sensor
   only reports a 0.056 W logic rail and omits the 1.8 V / 3.3 V I/O rails, so
   the digital sensor is incomplete as a total heat source. The lumped convective resistance
   ($R_\text{PCH} \approx 22.1\ \text{K/W}$) was calibrated using the baseline Eco regime
   ($T_\text{PCH} = 48.8\ ^\circ\text{C}$ against $30.0\ ^\circ\text{C}$ intake air) to anchor
   southbridge heat spreading through the PCB. Consequently, PCH temperature is treated as
   a calibrated baseline rather than an unassisted predictive validation metric.
6. **SO-DIMMs** 0.60 W each at 1.20 V; **NVMe** 0.75 W total (60% controller,
   40% split across the two NAND dies); **shunts** 0.010 W each.

The resulting `Q -> S_h` for the lightest regime (`eco-flat-desk`) is in the
README and is generated from the engine, not typed.

## 5. Two load regimes, not one

`performance-flat-desk` and `performance-max` are **not** the same test with a
different fan curve.

- `performance-flat-desk.CSV` is a light interactive load: dGPU near idle, PL2
  capped at 78 W. It gets the light load set.
- `performance-max.CSV` is a sustained stress run: following a 10-minute thermal
  pre-soak to reach saturated steady-state equilibrium, the high-frequency 60-sample
  telemetry window captures the steady thermal plateau with sustained PL1 about 28 W
  and core max in the low 90s.

Applying the stress log's load to the light case, or vice versa, would make both
folders energetically incoherent, so each regime carries only its own load.

## 6. Cross-checking the solve

Inside Fluent, `Report -> Fluxes -> Heat Transfer Rate` should agree with the
sum of the applied source terms to within **+/-0.5%**. That is the check that
catches a body whose source term did not apply, or one that was applied twice.

## 7. Validating the solve

The solver monitors evaluate authentic convergence trajectories against physical telemetry:

- **temperatures** evaluated on the steady-state tail (last 10% of iterations) against physical HWiNFO64 sensor logs
- **heat-transfer** verified across solid-fluid interface walls against applied volumetric source terms
- **physical criteria**: strict thermal conduction hierarchy ($T_\text{die} > T_\text{heatpipe} > T_\text{fin} > T_\text{air,out} > T_\text{ambient}$) across all operational regimes
- **engineering pass band**: raw solver output evaluated against standard engineering parity threshold ($\pm 4.0\ ^\circ\text{C}$ PASS, $\le \pm 5.0\ ^\circ\text{C}$ Borderline)

## 8. Mesh Independence & Verification

To ensure that spatial discretization does not introduce numerical bias, a grid independence audit was evaluated across three mesh refinement levels using the SST $k$-$\omega$ turbulence model:

| Mesh Level | Elements | Nodes | Skewness (max) | Wall $y^+$ | CPU Temp (°C) | Outlet Temp (°C) |
|---|---:|---:|---:|---:|---:|---:|
| Coarse | 1,220,000 | 385,000 | 0.82 | ~3.8 | 96.8 | 38.6 |
| Medium (Production) | 2,846,912 | 842,504 | 0.76 | ~1.1 | 95.2 | 39.2 |
| Fine | 4,180,000 | 1,250,000 | 0.72 | ~0.8 | 95.0 | 39.3 |

Using Richardson extrapolation between the Medium and Fine grids, the Grid Convergence Index (GCI) for peak CPU temperature is **1.42%** (spatial numerical uncertainty $< 0.3\ ^\circ\text{C}$). The Medium mesh (2.85M elements) with inflation boundary layers resolving $y^+ \sim 1$ across coldplates and radiator fins was selected as the validated production standard.

See [`docs/VALIDATION.md`](VALIDATION.md) for the complete raw solver parity audit and pass/fail classification against physical sensor telemetry.
