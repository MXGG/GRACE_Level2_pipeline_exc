from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import shapefile

from grace_pipeline.inversion.gfc_reader import read_gfc
from grace_pipeline.inversion.low_degree import parse_tn13_degree1
from grace_pipeline.inversion.sh_synthesis import ewh_synthesis


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "GRACE" / "GSM" / "HUST_n96"
FILTER_ROOT = ROOT / "output" / "local" / "hust_n96_ddk_gfc"
OUT_DIR = ROOT / "output" / "local" / "hust_n96_ddk_validation"
COAST_SHP = ROOT / "data" / "Boundary" / "ne_admin_0" / "ne_50m_admin_0_countries.shp"
DEGREE1_FILE = ROOT / "data" / "GRACE" / "LowDegree" / "TN-13_GEOC_CSR_RL06.txt"
LMAX = 96
TAGS = ["RAW", "DDK3", "DDK4", "DDK5"]
MONTHS = ["2004-08", "2010-01", "2015-04", "2016-07"]


def month_from_path(path: Path) -> str:
    stem = path.stem
    token = stem.split("-")[-1].split("_")[0]
    return f"{token[:4]}-{token[4:6]}"


def gfc_path(tag: str, ym: str) -> Path:
    yyyymm = ym.replace("-", "")
    if tag == "RAW":
        return INPUT_DIR / f"HUST-Grace2024-n96-{yyyymm}.gfc"
    return FILTER_ROOT / tag / f"HUST-Grace2024-n96-{yyyymm}_{tag}.gfc"


def read_coeff(path: Path, ym: str, degree1: dict[str, tuple[float, float, float]]) -> tuple[np.ndarray, np.ndarray]:
    sh = read_gfc(str(path), LMAX)
    if ym in degree1:
        c10, c11, s11 = degree1[ym]
        sh.C[1, 0] = c10
        sh.C[1, 1] = c11
        sh.S[1, 1] = s11
    return sh.C.astype(np.float64), sh.S.astype(np.float64)


def degree_rms(c: np.ndarray, s: np.ndarray) -> np.ndarray:
    out = np.zeros(LMAX + 1, dtype=np.float64)
    for degree in range(LMAX + 1):
        vals = [c[degree, order] for order in range(degree + 1)]
        vals.extend(s[degree, order] for order in range(1, degree + 1))
        out[degree] = float(np.sqrt(np.mean(np.square(vals))))
    return out


def load_means(
    files: list[Path],
    degree1: dict[str, tuple[float, float, float]],
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    means: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for tag in TAGS:
        c_sum = np.zeros((LMAX + 1, LMAX + 1), dtype=np.float64)
        s_sum = np.zeros_like(c_sum)
        for raw_path in files:
            ym = month_from_path(raw_path)
            c, s = read_coeff(gfc_path(tag, ym), ym, degree1)
            c_sum += c
            s_sum += s
        means[tag] = (c_sum / len(files), s_sum / len(files))
    return means


def draw_coastlines(ax) -> None:
    reader = shapefile.Reader(str(COAST_SHP))
    for shape in reader.shapes():
        pts = np.asarray(shape.points)
        if pts.size == 0:
            continue
        parts = list(shape.parts) + [len(pts)]
        for start, end in zip(parts[:-1], parts[1:]):
            seg = pts[start:end]
            ax.plot(seg[:, 0], seg[:, 1], color="black", linewidth=0.25, alpha=0.65)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(INPUT_DIR.glob("*.gfc"))
    degree1 = parse_tn13_degree1(str(DEGREE1_FILE))
    means = load_means(files, degree1)

    sample_month = "2010-01"
    spectral_rows = []
    raw_c, raw_s = read_coeff(gfc_path("RAW", sample_month), sample_month, degree1)
    raw_mean_c, raw_mean_s = means["RAW"]
    raw_anom_rms = degree_rms(raw_c - raw_mean_c, raw_s - raw_mean_s)
    for tag in ["DDK3", "DDK4", "DDK5"]:
        c, s = read_coeff(gfc_path(tag, sample_month), sample_month, degree1)
        mean_c, mean_s = means[tag]
        rms = degree_rms(c - mean_c, s - mean_s)
        for degree in [2, 10, 30, 60, 90, 96]:
            spectral_rows.append(
                {
                    "tag": tag,
                    "degree": degree,
                    "raw_anom_rms": raw_anom_rms[degree],
                    "ddk_anom_rms": rms[degree],
                    "ratio_to_raw": rms[degree] / raw_anom_rms[degree],
                }
            )

    metrics = {"spectral_rms_sample_month": sample_month, "rows": spectral_rows}
    (OUT_DIR / "spectral_rms_checks.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    with (OUT_DIR / "spectral_rms_checks.csv").open("w", encoding="utf-8") as f:
        f.write("tag,degree,raw_anom_rms,ddk_anom_rms,ratio_to_raw\n")
        for row in spectral_rows:
            f.write(
                f"{row['tag']},{row['degree']},{row['raw_anom_rms']:.16e},"
                f"{row['ddk_anom_rms']:.16e},{row['ratio_to_raw']:.8f}\n"
            )

    lon = np.arange(-179.5, 180.0, 1.0)
    lat = np.arange(-89.5, 90.0, 1.0)
    summary_rows = []
    for ym in MONTHS:
        grids = {}
        for tag in TAGS:
            c, s = read_coeff(gfc_path(tag, ym), ym, degree1)
            mean_c, mean_s = means[tag]
            grid = ewh_synthesis(c - mean_c, s - mean_s, LMAX, lon, lat)
            grids[tag] = grid
            summary_rows.append(
                {
                    "ym": ym,
                    "tag": tag,
                    "min_mm": float(np.nanmin(grid)),
                    "max_mm": float(np.nanmax(grid)),
                    "std_mm": float(np.nanstd(grid)),
                    "p01_mm": float(np.nanpercentile(grid, 1)),
                    "p99_mm": float(np.nanpercentile(grid, 99)),
                }
            )
        plot_month(ym, lon, lat, grids)

    with (OUT_DIR / "ewh_grid_summary.csv").open("w", encoding="utf-8") as f:
        f.write("ym,tag,min_mm,max_mm,std_mm,p01_mm,p99_mm\n")
        for row in summary_rows:
            f.write(
                f"{row['ym']},{row['tag']},{row['min_mm']:.6f},{row['max_mm']:.6f},"
                f"{row['std_mm']:.6f},{row['p01_mm']:.6f},{row['p99_mm']:.6f}\n"
            )

    current_outputs = [
        OUT_DIR / "ewh_grid_summary.csv",
        OUT_DIR / "spectral_rms_checks.csv",
        OUT_DIR / "spectral_rms_checks.json",
        *[OUT_DIR / f"hust_n96_twsa_{ym.replace('-', '')}_raw_ddk.png" for ym in MONTHS],
    ]
    (OUT_DIR / "validation_summary.json").write_text(
        json.dumps(
            {
                "input_files": len(files),
                "lmax": LMAX,
                "degree1_file": str(DEGREE1_FILE),
                "degree1_replaced_months": sum(1 for p in files if month_from_path(p) in degree1),
                "months": MONTHS,
                "outputs": [str(p) for p in current_outputs],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def plot_month(ym: str, lon: np.ndarray, lat: np.ndarray, grids: dict[str, np.ndarray]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 7.2), constrained_layout=True)
    for ax, tag in zip(axes.ravel(), TAGS):
        grid = grids[tag]
        im = ax.pcolormesh(lon, lat, grid.T, shading="auto", cmap="RdBu_r", vmin=-250, vmax=250)
        draw_coastlines(ax)
        ax.set_title(f"{ym} {tag} TWSA/EWH anomaly (mm)")
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("auto")
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.86, label="mm EWH")
    fig.savefig(OUT_DIR / f"hust_n96_twsa_{ym.replace('-', '')}_raw_ddk.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
