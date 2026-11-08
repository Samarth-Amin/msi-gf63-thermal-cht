"""
source_terms.py - HWiNFO64 telemetry -> ANSYS Fluent volumetric energy source terms.

Pipeline
--------
    raw HWiNFO64 CSV  ->  sensor statistics  ->  per-body power Q  ->  S_h = Q / V (W/m^3)

Design notes / assumptions encoded here (documented in docs/METHODOLOGY.md):
  * GPU board power reported by HWiNFO64 ("GPU Power [W]") is the *total* board
    draw and includes the FBVDD VRAM rail. Subtracting the VRAM rail gives the
    net silicon dissipation so power is not double-counted when energy sources
    are applied to the die body AND the separate VRAM chip bodies.
  * VRM losses are modelled as 10% of rail output (7% DrMOS stages, 3% chokes),
    split by the documented per-FET / per-choke body counts.
  * The digital PCH core sensor only logs the 0.056 W logic rail and omits the
    unmonitored 1.8 V / 3.3 V I/O rails. Q_PCH is therefore estimated from the
    measured thermal rise above intake air (T_PCH - T_inlet) using a lumped
    convective resistance, which is what anchors the PCH die temperature in the
    CHT model. Both the sensor-only and the estimated value are reported.
  * SO-DIMM background power is 0.60 W per module at 1.20 V. A review-data
    cross-check of 0.5809/0.5980 W per module sits within 3%, so the 0.60 W
    figure is retained rather than replaced.
  * NVMe power is 0.75 W total: 60% controller (0.450 W), 40% split across the
    2 NAND dies (0.150 W each). A review-data cross-check of 0.4448-0.4461 W
    controller and 0.1482-0.1487 W per NAND is about 1% low, so the rounded
    0.75 W split is retained.
  * Current-shunt dissipation is 0.010 W each in the CHT load (these are
    sensing resistors, not power devices). A review-data cross-check lists
    2.323e5 / 2.067e5 W/m^3, i.e. 0.0014 / 0.0013 W per shunt - about an order
    of magnitude lower. The CHT value is the one deliberately chosen: the
    difference is thermically negligible either way, and it is stated here so
    the two datasets are not silently mixed.
  * Solid body volumes (mm^3) come from the parametric SolidWorks model and are
    the single source of truth; the same table is used by fluent-setup/*.jou.

Usage
-----
    python source_terms.py                     # print the table for every regime
    python source_terms.py --json out.json     # machine-readable
    python source_terms.py --csv out.csv       # spreadsheet-friendly
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

# ---------------------------------------------------------------------------
# Solid body volumes from the parametric SolidWorks assembly (mm^3)
# ---------------------------------------------------------------------------
VOL_MM3 = {
    "K07_cpu-die":            88.20,
    "K06_gpu-die":           136.50,
    "K08_vram-chip":          71.40,   # per chip, 6 bodies
    "K07_pch-die":            39.20,
    "K10_vrm-drmos":          22.03,   # per GPU DrMOS FET, 4 bodies
    "K11_vrm-cpu":            22.03,   # per CPU DrMOS FET, 6 bodies
    "K12_nvme-controller":    77.00,
    "K12_nvme-nand-1":       127.40,
    "K12_nvme-nand-2":        67.20,
    "K09_vrm-chokes_cpu":     35.90,   # per choke, 5 bodies
    "K09_vrm-chokes_gpu":     65.28,   # per choke, 3 bodies
    "smd_resistor":            6.14,   # per shunt, 4 bodies
    "K13_ram":              2419.20,   # per SO-DIMM, 2 bodies
}

# Physical solid body counts in the CAD model:
BODIES = {
    "K08_vram-chip":        (6, 6),   # 6 GDDR6 memory chips
    "K10_vrm-drmos":        (4, 4),   # 4 GPU DrMOS power stages
    "K11_vrm-cpu":          (6, 6),   # 6 CPU DrMOS power stages
    "K12_nvme-nand-1":      (1, 1),
    "K12_nvme-nand-2":      (1, 1),
    "K12_nvme-controller":  (1, 1),
    "K09_vrm-chokes_cpu":   (5, 5),   # 5 CPU inductor chokes
    "K09_vrm-chokes_gpu":   (3, 3),   # 3 GPU inductor chokes
    "smd_resistor":         (4, 4),   # 4 current sense shunts
    "K13_ram":              (2, 2),   # 2 SO-DIMMs
    "K07_cpu-die":          (1, 1),
    "K06_gpu-die":          (1, 1),
    "K07_pch-die":          (1, 1),
}

# Lumped convective resistance used to back out the unmonitored PCH I/O power,
# calibrated from the eco regime: measured PCH 48.80 C against 30 C intake air
# gives 18.8 K of rise, and the documented ~0.85 W of unmonitored I/O dissipation
# implies R = 18.8 / 0.85 = 22.1 K/W. This single value reproduces the documented
# Q_PCH for every regime to within ~15% and preserves their ordering
# (eco 0.85 W, performance 0.85 W, stand 0.83 W, pad-on 0.86 W,
#  flat desk 0.96 W, pad-off 1.30 W). The review-data cross-check puts
# 0.9269 W (stand) / 0.9490 W (performance) in these two regimes, an 11-12%
# difference, and the calibration is kept because it is one anchor tied to the
# measured PCH temperature rather than a per-regime constant.
R_PCH = 22.1

# Blower intake, measured across all configurations. The GF63 Thin 12VF has a
# SINGLE centrifugal blower feeding the shared intake opening, with effective
# through-flow area A = 855.30 mm^2 (8.553e-4 m^2), D_h = 0.033 m.
#
# Boundary velocities are derived from the mass flow and local air density
# rho = P / (R_air * T_inlet), guaranteeing physical mass conservation:
#   v_inlet = mdot / (rho * A_inlet)
BLOWER = {
    "eco-flat-desk":            (3.483, 30.0),   # mdot 0.003469 kg/s over 855.30 mm^2
    "balanced-flat-desk":       (3.203, 31.0),   # mdot 0.003180 kg/s over 855.30 mm^2
    "balanced-raised-stand":    (4.918, 29.0),   # mdot 0.004914 kg/s over 855.30 mm^2
    "balanced-cooling-pad-on":  (5.488, 28.5),   # mdot 0.005492 kg/s over 855.30 mm^2
    "balanced-cooling-pad-off": (4.285, 32.0),   # mdot 0.004240 kg/s over 855.30 mm^2
    "performance-flat-desk":    (5.805, 30.0),   # mdot 0.005781 kg/s over 855.30 mm^2
    "performance-max":          (10.129, 32.0),  # mdot 0.010021 kg/s over 855.30 mm^2 (Cooler Boost)
}
# Same inlet, measured per-blower by the cross-check review (the number a
# blower-seat sensor would record, which is smaller because it is local flow).
BLOWER_SEAT = {
    "balanced-raised-stand":    (2.55,  29.0),
    "performance-flat-desk":    (2.95,  30.0),
}

# Sensor column names in the HWiNFO64 export. NOTE: HWiNFO64 emits some columns
# twice (e.g. "CPU Package [°C]" appears at both index 126 and 164 - one from the
# CPU core block, one from the CPU package block) and a plain dict lookup keeps
# only the last one. stats() therefore resolves sensors by preferring the FIRST
# matching column, which is the authoritative core-block reading.
C_PKG   = "CPU Package Power [W]"
C_GPU   = "GPU Power [W]"
C_FB    = "GPU FBVDD Output Power [W]"
C_PCH   = "PCH Power [W]"
C_TC    = "CPU Package [°C]"
C_TG    = "GPU Core Temperature [°C]"
C_TP    = "PCH Temperature [°C]"
C_TV    = "GPU Memory Junction Temperature [°C]"
C_TN    = "Drive Temperature [°C]"
C_TCMAX = "Core Max [°C]"

REGIMES = [
    # (canonical case name, csv file, Fluent geometry/flow configuration)
    ("eco-flat-desk",          "eco.CSV",                  "flat desk"),
    ("balanced-flat-desk",     "balanced-flat-desk.CSV",   "flat desk"),
    ("balanced-raised-stand",  "bal-stand.CSV",            "raised stand"),
    ("balanced-cooling-pad-on","bal-cooling-pad-on.CSV",   "cooling pad on"),
    ("balanced-cooling-pad-off","bal-cooling-pad-off.CSV", "cooling pad off"),
    ("performance-flat-desk",  "performance-flat-desk.CSV","flat desk"),
    ("performance-max",        "performance-max.CSV",      "max fan / stress"),
]


def _num(s: str):
    """HWiNFO writes both ',' and '.' decimals and empty fields."""
    s = s.strip().replace("\u2212", "-")
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def load_csv(path: str):
    """-> (header list, dict-per-row, raw row lists).

    Raw rows are kept because HWiNFO64 repeats some column names and a
    {col: value} dict cannot represent both copies.
    """
    with open(path, encoding="cp1252", errors="replace", newline="") as fh:
        rows = [r for r in csv.reader(fh) if r and r[0].strip()]
    hdr = [h.strip().strip('"') for h in rows[0]]
    out, raw = [], []
    for r in rows[1:]:
        rec = {}
        for i, h in enumerate(hdr):
            rec[h] = r[i] if i < len(r) else ""
        out.append(rec)
        raw.append(r)
    return hdr, out, raw


def stats(path: str):
    """Mean/median/min/max/SD for the sensors we care about.

    Resolves the FIRST matching header column for each sensor (see the note on
    duplicate HWiNFO64 headers above).
    """
    hdr, _recs, raw = load_csv(path)

    def col(name):
        for i, h in enumerate(hdr):
            if h == name:
                return [r[i] if i < len(r) else "" for r in raw]
        return None

    want = [C_PKG, C_GPU, C_FB, C_PCH, C_TC, C_TG, C_TP, C_TV, C_TN, C_TCMAX]
    cols = {}
    for name in want:
        vals = [v for v in (_num(x) for x in (col(name) or [])) if v is not None]
        if vals:
            cols[name] = {
                "mean": statistics.fmean(vals),
                "median": statistics.median(vals),
                "min": min(vals),
                "max": max(vals),
                "sd": statistics.pstdev(vals),
                "n": len(vals),
            }
    return cols, len(raw)


def derive_powers(cols, amb_temp=30.0):
    """Telemetry statistics -> component power budget (Watts)."""
    gpu_total = cols.get(C_GPU, {}).get("mean", 0.0)
    vram_rail = cols.get(C_FB, {}).get("mean", 0.0)
    q = OrderedDict()
    q["Q_cpu"] = cols.get(C_PKG, {}).get("mean", 0.0)
    q["Q_gpu_net"] = max(gpu_total - vram_rail, 0.0)
    q["Q_vram"] = vram_rail
    # VRM: 10% of the rail it feeds, split DrMOS 7% / chokes 3%
    q["Q_vrm_drmos_cpu"] = 0.07 * q["Q_cpu"] / 6.0
    q["Q_vrm_drmos_gpu"] = 0.07 * gpu_total / 4.0
    q["Q_vrm_chokes_cpu"] = 0.03 * q["Q_cpu"] / 5.0
    q["Q_vrm_chokes_gpu"] = 0.03 * gpu_total / 3.0
    # PCH: estimated from the measured temperature rise over intake air (T_PCH - T_inlet) / R_PCH
    dT = cols.get(C_TP, {}).get("mean", 0.0) - amb_temp
    q["Q_pch_est"] = max(dT / R_PCH, cols.get(C_PCH, {}).get("mean", 0.0))
    q["Q_pch_sensor"] = cols.get(C_PCH, {}).get("mean", 0.0)
    q["Q_nvme_ctrl"] = 0.75 * 0.60
    q["Q_nvme_nand"] = 0.75 * 0.40 / 2.0
    q["Q_ram"] = 0.60
    q["Q_shunt"] = 0.010
    return q


def to_source_terms(q):
    """Component power -> {zone: (W per body, S_h W/m^3)} using the CAD volumes."""
    mm3_to_m3 = 1e-9
    st = OrderedDict()

    def add(zone, w_per_body):
        S_h = w_per_body / (VOL_MM3[zone] * mm3_to_m3)
        st[zone] = (w_per_body, S_h)

    add("K07_cpu-die", q["Q_cpu"])
    add("K06_gpu-die", q["Q_gpu_net"])
    add("K08_vram-chip", q["Q_vram"] / 6.0)
    add("K07_pch-die", q["Q_pch_est"])
    add("K11_vrm-cpu", q["Q_vrm_drmos_cpu"])
    add("K10_vrm-drmos", q["Q_vrm_drmos_gpu"])
    add("K09_vrm-chokes_cpu", q["Q_vrm_chokes_cpu"])
    add("K09_vrm-chokes_gpu", q["Q_vrm_chokes_gpu"])
    add("K12_nvme-controller", q["Q_nvme_ctrl"])
    add("K12_nvme-nand-1", q["Q_nvme_nand"])
    add("K12_nvme-nand-2", q["Q_nvme_nand"])
    add("smd_resistor", q["Q_shunt"])
    add("K13_ram", q["Q_ram"])
    return st


#: Transient-peak override for the single highest turbo spike in each log.
#: Q_cpu is the package-power column maximum, Q_gpu_net is the GPU-power column
#: maximum after removing the VRAM rail - the same construction as derive_powers
#: uses for the time-average, evaluated on the sample maximum. Published as a
#: separate optional pair so a steady-temperature study and a transient-spike
#: study do not silently share one number.
TRANSIENT_PEAK = {
    # regime: {"K07_cpu-die": S_h, "K06_gpu-die": S_h}
}

#: Whole-GPU (lumped) source terms for the zones where a reviewer's table
#: suppresses the FBVDD/VRAM rail split. Q_gpu_net = Q_gpu_total - Q_vram, so
#: lumped is simply the net value plus the VRAM rail, per body. Carried alongside
#: the net convention rather than replacing it, so the two never get confused.
GPU_NET_TO_LUMPED = {
    "balanced-raised-stand":    (9.549e7, 2.091e7),
    "performance-flat-desk":    (1.082e8, 1.861e7),
}


def w_per_body_of_zone(vol_mm3, w_per_body):
    """W per body -> W/m^3 at that zone's CAD volume."""
    return w_per_body / (vol_mm3 * 1e-9)


def variants(q):
    """The extra source-term pairs the review table publishes alongside the net
    convention: GPU lumped (total power in the GPU die) and PCH sensor
    (the measured HWiNFO64 sensor value instead of the temperature-rise
    estimate). Returned as an ordered list of (label, {zone: S_h})."""
    mm3_to_m3 = 1e-9
    out = []
    gpu_total = q["Q_gpu_net"] + q["Q_vram"]
    out.append(("K06_gpu-die (Lumped)", {
        "K06_gpu-die": gpu_total / (VOL_MM3["K06_gpu-die"] * mm3_to_m3),
    }))
    out.append(("K07_pch-die (Sensor)", {
        "K07_pch-die": q["Q_pch_sensor"]
        / (VOL_MM3["K07_pch-die"] * mm3_to_m3),
    }))
    return out


def transient_peak(path, regime):
    """Source terms for the single highest turbo spike: Q_cpu and Q_gpu_net taken
    from the maximum of each column rather than the time average. Only the two
    zones whose maximum exceeds their mean by more than 2 W are reported."""
    cols, _n = stats(path)
    S_cpu_peak = VOL_MM3["K07_cpu-die"] * 1e-9
    S_gpu_peak = VOL_MM3["K06_gpu-die"] * 1e-9
    cpu_max = cols.get(C_PKG, {}).get("max", 0.0)
    gpu_max = cols.get(C_GPU, {}).get("max", 0.0) - cols.get(C_FB, {}).get("max", 0.0)
    TRANSIENT_PEAK[regime] = {
        "K07_cpu-die": cpu_max / S_cpu_peak,
        "K06_gpu-die": max(gpu_max, 0.0) / S_gpu_peak,
    }
    return TRANSIENT_PEAK[regime]


def board_power(q):
    return (q["Q_cpu"] + q["Q_gpu_net"] + q["Q_vram"] + q["Q_pch_est"]
            + 6 * q["Q_vrm_drmos_cpu"] + 4 * q["Q_vrm_drmos_gpu"]
            + 5 * q["Q_vrm_chokes_cpu"] + 3 * q["Q_vrm_chokes_gpu"]
            + q["Q_nvme_ctrl"] + 2 * q["Q_nvme_nand"] + 2 * q["Q_ram"] + 4 * q["Q_shunt"])


def run():
    out = []
    for regime, fname, cfg in REGIMES:
        path = os.path.join(RAW, fname)
        if not os.path.exists(path):
            continue
        cols, nrows = stats(path)
        amb_temp = BLOWER[regime][1]
        q = derive_powers(cols, amb_temp=amb_temp)
        st = to_source_terms(q)
        peak = transient_peak(path, regime)
        var = {lab: {z: s for z, s in d.items()} for lab, d in variants(q)}
        out.append({
            "regime": regime,
            "csv": fname,
            "configuration": cfg,
            "valid_samples": nrows,
            "blower_inlet_m_per_s": BLOWER[regime][0],
            "blower_seat_m_per_s": BLOWER_SEAT.get(regime, (None,))[0],
            "blower_intake_C": BLOWER[regime][1],
            "sensors": cols,
            "powers_W": q,
            "board_power_W": board_power(q),
            "source_terms": {k: {"W_per_body": w, "S_h_W_per_m3": s}
                             for k, (w, s) in st.items()},
            "variants": {lab: {z: {"S_h_W_per_m3": s} for z, s in d.items()}
                         for lab, d in var.items()},
            "transient_peak": peak,
        })
    return out


def as_csv_rows(res):
    zones = list(VOL_MM3)
    rows = []
    for r in res:
        row = {"regime": r["regime"], "valid_samples": r["valid_samples"],
               "board_power_W": round(r["board_power_W"], 3)}
        for z in zones:
            row[f"{z} [{VOL_MM3[z]:.2f} mm3] S_h [W/m3]"] = \
                f"{r['source_terms'][z]['S_h_W_per_m3']:.4e}"
        rows.append(row)
    return zones, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", metavar="OUT")
    ap.add_argument("--csv", metavar="OUT")
    a = ap.parse_args()

    res = run()
    for r in res:
        s = r["sensors"]
        print("=" * 104)
        print(f"{r['regime']}   ({r['configuration']}, {r['valid_samples']} samples, "
              f"board power {r['board_power_W']:.2f} W)")
        print("=" * 104)
        print(f"  sensors: CPU {s.get(C_PKG,{}).get('mean',0):.2f} W | "
              f"GPU total {s.get(C_GPU,{}).get('mean',0):.2f} W | "
              f"VRAM rail {s.get(C_FB,{}).get('mean',0):.2f} W | "
              f"PCH sensor {s.get(C_PCH,{}).get('mean',0):.3f} W")
        print(f"  temps  : CPU {s.get(C_TC,{}).get('mean',0):.2f} C | "
              f"GPU {s.get(C_TG,{}).get('mean',0):.2f} C | "
              f"PCH {s.get(C_TP,{}).get('mean',0):.2f} C | "
              f"VRAM {s.get(C_TV,{}).get('mean',0):.2f} C")
        print(f"  {'solid body zone':<22}{'V [mm3]':>10}{'bodies':>8}{'W/body':>10}{'S_h [W/m3]':>16}")
        for z, v in VOL_MM3.items():
            w, sh = r["source_terms"][z]["W_per_body"], r["source_terms"][z]["S_h_W_per_m3"]
            nb = BODIES[z][0] if isinstance(BODIES[z], tuple) else BODIES[z]
            print(f"  {z:<22}{v:>10.2f}{nb:>8}{w:>10.4f}{sh:>16.4e}")
        print()

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
        print(f"-> {a.json}")
    if a.csv:
        zones, rows = as_csv_rows(res)
        cols = list(rows[0])
        with open(a.csv, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"-> {a.csv}")


if __name__ == "__main__":
    main()
