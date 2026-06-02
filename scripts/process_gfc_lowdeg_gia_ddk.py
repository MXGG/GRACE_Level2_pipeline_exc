from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from grace_pipeline.core.time_index import TimeEntry, extract_ym_from_gfc
from grace_pipeline.filters.ddk import filter_sh_ddk
from grace_pipeline.inversion.gfc_reader import SHCoefficients, read_gfc
from grace_pipeline.inversion.low_degree import select_tn14_slr_entry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace low-degree terms, apply GIA correction, then optionally DDK-filter GFC files."
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing input .gfc files.")
    parser.add_argument("--output-dir", required=True, help="Output root directory.")
    parser.add_argument("--lmax", type=int, default=96, help="Maximum degree/order to process.")
    parser.add_argument("--degree1-file", required=True, help="TN-13 degree-1 file for C10/C11/S11.")
    parser.add_argument("--c20-c30-file", required=True, help="TN-14 SLR file for C20/C30.")
    parser.add_argument("--gia-file", required=True, help="GIA Stokes coefficient file with columns l m C S.")
    parser.add_argument("--ddk-data-dir", required=True, help="Directory containing DDK kernel binaries.")
    parser.add_argument(
        "--ddk",
        action="append",
        default=None,
        help="DDK type to produce. Repeatable. Defaults to DDK3, DDK4, DDK5.",
    )
    parser.add_argument(
        "--gia-mode",
        choices=["fixed", "rate"],
        default="fixed",
        help="fixed subtracts the Stokes file directly; rate subtracts value*(decimal_year-reference_epoch).",
    )
    parser.add_argument("--gia-reference-epoch", type=float, default=2002.0)
    parser.add_argument("--c30-start-ym", default="2018-06")
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def normalize_ddk(raw: str) -> str:
    text = str(raw).strip().upper()
    if text.isdigit():
        text = f"DDK{text}"
    if not text.startswith("DDK"):
        text = f"DDK{text}"
    if text not in {f"DDK{i}" for i in range(1, 9)}:
        raise ValueError(f"Unsupported DDK type: {raw}")
    return text


def make_time_entry(path: Path) -> TimeEntry:
    ym = extract_ym_from_gfc(str(path))
    if ym is None:
        raise ValueError(f"Cannot infer YYYY-MM from {path}")
    return TimeEntry.from_ym(ym, gfc_file=str(path))


def apply_low_degree(
    sh: SHCoefficients,
    time_entry: TimeEntry,
    degree1_rows: list[dict[str, object]],
    c20_c30_file: Path,
    c30_start_ym: str,
) -> dict[str, object]:
    meta: dict[str, object] = {}
    ym = time_entry.ym

    deg1 = select_degree1_row(degree1_rows, time_entry)
    if deg1 is not None:
        sh.C[1, 0] = float(deg1["C10"])
        sh.C[1, 1] = float(deg1["C11"])
        sh.S[1, 1] = float(deg1["S11"])
        meta["degree1"] = "replaced"
        meta["degree1_match"] = "max_overlap"
        meta["degree1_source_ym"] = deg1.get("ym_mid", "")
    else:
        meta["degree1"] = "missing"

    slr = select_tn14_slr_entry(str(c20_c30_file), time_entry)
    c20 = float(slr.get("C20", np.nan))
    if np.isfinite(c20):
        sh.C[2, 0] = c20
        meta["C20"] = "replaced"
    else:
        meta["C20"] = "missing"

    c30 = float(slr.get("C30", np.nan))
    if ym >= c30_start_ym and np.isfinite(c30):
        sh.C[3, 0] = c30
        meta["C30"] = "replaced"
    else:
        meta["C30"] = "not_applied"

    return meta


def parse_degree1_rows(filepath: Path) -> list[dict[str, object]]:
    from datetime import datetime, timedelta

    partial: dict[tuple[datetime, datetime], dict[str, object]] = {}
    rows: list[dict[str, object]] = []

    def _ym_mid(start_dt: datetime, end_dt: datetime) -> str:
        mid = start_dt + (end_dt - start_dt) / 2
        return f"{mid.year:04d}-{mid.month:02d}"

    with filepath.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith(("#", "%")):
                continue
            parts = line.split()
            if len(parts) >= 9 and parts[0].upper().startswith("GRCOF2"):
                try:
                    degree = int(parts[1])
                    order = int(parts[2])
                    c_val = float(parts[3])
                    s_val = float(parts[4])
                    start_dt = datetime.strptime(parts[-2].split(".")[0][:8], "%Y%m%d")
                    stop_dt = datetime.strptime(parts[-1].split(".")[0][:8], "%Y%m%d") - timedelta(days=1)
                except (ValueError, IndexError):
                    continue
                if degree != 1 or order not in (0, 1):
                    continue
                key = (start_dt, stop_dt)
                row = partial.setdefault(
                    key,
                    {
                        "start": start_dt,
                        "end": stop_dt,
                        "ym_mid": _ym_mid(start_dt, stop_dt),
                        "C10": np.nan,
                        "C11": np.nan,
                        "S11": np.nan,
                    },
                )
                if order == 0:
                    row["C10"] = c_val
                else:
                    row["C11"] = c_val
                    row["S11"] = s_val
                continue

            if len(parts) >= 5:
                try:
                    year = int(float(parts[0]))
                    month = int(float(parts[1]))
                    c10 = float(parts[2])
                    c11 = float(parts[3])
                    s11 = float(parts[4])
                except ValueError:
                    continue
                if year < 100:
                    year += 2000 if year < 50 else 1900
                if 1 <= month <= 12:
                    start_dt = datetime(year, month, 1)
                    end_dt = datetime(year + int(month == 12), month % 12 + 1, 1) - timedelta(days=1)
                    rows.append(
                        {
                            "start": start_dt,
                            "end": end_dt,
                            "ym_mid": f"{year:04d}-{month:02d}",
                            "C10": c10,
                            "C11": c11,
                            "S11": s11,
                        }
                    )

    for row in partial.values():
        if np.isfinite([row["C10"], row["C11"], row["S11"]]).all():
            rows.append(row)
    return rows


def select_degree1_row(degree1_rows: list[dict[str, object]], time_entry: TimeEntry) -> dict[str, object] | None:
    from datetime import datetime, timedelta

    month_start = datetime(time_entry.year, time_entry.month, 1)
    month_end = datetime(time_entry.year + int(time_entry.month == 12), time_entry.month % 12 + 1, 1) - timedelta(days=1)
    best = None
    best_overlap = float("-inf")
    for row in degree1_rows:
        start = row["start"]
        end = row["end"]
        overlap = (min(month_end, end) - max(month_start, start)).days + 1
        if overlap >= 0 and overlap > best_overlap:
            best = row
            best_overlap = overlap
    return best


def apply_gia(
    sh: SHCoefficients,
    gia_c: np.ndarray,
    gia_s: np.ndarray,
    time_entry: TimeEntry,
    mode: str,
    reference_epoch: float,
) -> dict[str, object]:
    lmax = min(sh.Lmax, gia_c.shape[0] - 1)
    if mode == "rate":
        decimal_year = time_entry.year + (time_entry.month - 0.5) / 12.0
        factor = decimal_year - reference_epoch
    else:
        factor = 1.0
    sh.C[: lmax + 1, : lmax + 1] -= gia_c[: lmax + 1, : lmax + 1] * factor
    sh.S[: lmax + 1, : lmax + 1] -= gia_s[: lmax + 1, : lmax + 1] * factor
    return {"mode": mode, "factor": factor, "Lmax": lmax}


def read_gia_stokes_first_occurrence(filepath: Path, lmax: int) -> tuple[np.ndarray, np.ndarray]:
    """Read GIA Stokes coefficients, keeping the first value for duplicate low-degree rows."""
    c = np.zeros((lmax + 1, lmax + 1), dtype=float)
    s = np.zeros_like(c)
    seen: set[tuple[int, int]] = set()
    with filepath.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            parts = raw.strip().split()
            if len(parts) < 4:
                continue
            try:
                degree = int(parts[0])
                order = int(parts[1])
                c_val = float(parts[2])
                s_val = float(parts[3])
            except ValueError:
                continue
            if not (0 <= order <= degree <= lmax):
                continue
            key = (degree, order)
            if key in seen:
                continue
            c[degree, order] = c_val
            s[degree, order] = s_val
            seen.add(key)
    return c, s


def write_gfc(source: Path, target: Path, c: np.ndarray, s: np.ndarray, tag: str, lmax: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with source.open("r", encoding="utf-8", errors="ignore") as fin, tmp.open(
        "w", encoding="utf-8", newline="\n"
    ) as fout:
        for raw in fin:
            line = raw.rstrip("\r\n")
            parts = line.split()
            if len(parts) >= 5 and parts[0].lower().startswith("gfc"):
                try:
                    degree = int(parts[1])
                    order = int(parts[2])
                except ValueError:
                    fout.write(line + "\n")
                    continue
                if 0 <= order <= degree <= lmax:
                    sigma_c = parts[5] if len(parts) >= 6 else "0.0000E+00"
                    sigma_s = parts[6] if len(parts) >= 7 else "0.0000E+00"
                    fout.write(
                        f"gfc {degree:4d} {order:4d} "
                        f"{c[degree, order]: .12E} {s[degree, order]: .12E} "
                        f"{sigma_c:>11s} {sigma_s:>11s}\n"
                    )
                else:
                    fout.write(line + "\n")
                continue

            stripped = line.strip()
            if stripped.lower().startswith("modelname"):
                parts2 = stripped.split(None, 1)
                model = parts2[1] if len(parts2) == 2 else source.stem
                fout.write(f"   modelname                {model}_{tag}\n")
            elif stripped.lower().startswith("max_degree"):
                fout.write(f"   max_degree               {lmax}\n")
            else:
                fout.write(line + "\n")
    tmp.replace(target)


def output_name(source: Path, tag: str) -> str:
    return f"{source.stem}_{tag}{source.suffix or '.gfc'}"


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    ddk_data_dir = Path(args.ddk_data_dir)
    c20_c30_file = Path(args.c20_c30_file)

    ddk_types = [normalize_ddk(t) for t in (args.ddk or ["DDK3", "DDK4", "DDK5"])]
    files = sorted([p for p in input_dir.glob("*.gfc") if p.is_file()])
    if not files:
        raise FileNotFoundError(f"No .gfc files found in {input_dir}")

    degree1_rows = parse_degree1_rows(Path(args.degree1_file))
    gia_c, gia_s = read_gia_stokes_first_occurrence(Path(args.gia_file), args.lmax)

    manifest = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "lmax": args.lmax,
        "degree1_file": str(Path(args.degree1_file)),
        "c20_c30_file": str(c20_c30_file),
        "gia_file": str(Path(args.gia_file)),
        "gia_mode": args.gia_mode,
        "gia_reference_epoch": args.gia_reference_epoch,
        "ddk_data_dir": str(ddk_data_dir),
        "ddk_types": ddk_types,
        "files": [],
    }

    counts = {"RAW_LD_GIA": 0, **{tag: 0 for tag in ddk_types}}
    for src in files:
        te = make_time_entry(src)
        sh = read_gfc(str(src), args.lmax)
        lowdeg_meta = apply_low_degree(sh, te, degree1_rows, c20_c30_file, args.c30_start_ym)
        gia_meta = apply_gia(sh, gia_c, gia_s, te, args.gia_mode, args.gia_reference_epoch)

        raw_tag = "RAW_LD_GIA"
        raw_out = output_dir / raw_tag / output_name(src, raw_tag)
        if not raw_out.exists() or not args.skip_existing:
            write_gfc(src, raw_out, sh.C, sh.S, raw_tag, args.lmax)
            counts[raw_tag] += 1

        file_record = {
            "source": str(src),
            "ym": te.ym,
            "low_degree": lowdeg_meta,
            "gia": gia_meta,
            "outputs": {"RAW_LD_GIA": str(raw_out)},
        }

        for tag in ddk_types:
            out = output_dir / tag / output_name(src, f"LD_GIA_{tag}")
            if out.exists() and args.skip_existing:
                file_record["outputs"][tag] = str(out)
                continue
            c_d, s_d, meta = filter_sh_ddk(sh.C, sh.S, args.lmax, tag, str(ddk_data_dir))
            if not meta.get("applied"):
                raise RuntimeError(f"{tag} failed for {src}: {meta.get('error')}")
            write_gfc(src, out, c_d, s_d, f"LD_GIA_{tag}", args.lmax)
            counts[tag] += 1
            file_record["outputs"][tag] = str(out)

        manifest["files"].append(file_record)

    manifest["counts_written"] = counts
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest_lowdeg_gia_ddk.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for tag, count in counts.items():
        print(f"{tag}: wrote {count} files to {output_dir / tag}")
    print(f"Manifest: {output_dir / 'manifest_lowdeg_gia_ddk.json'}")


if __name__ == "__main__":
    main()
