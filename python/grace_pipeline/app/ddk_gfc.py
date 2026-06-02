"""Batch DDK filtering for GFC spherical-harmonic coefficient files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from grace_pipeline.filters.ddk import filter_sh_ddk
from grace_pipeline.inversion.gfc_reader import read_gfc


@dataclass(frozen=True)
class DDKGfcResult:
    ddk_type: str
    output_dir: Path
    files_written: int


def filter_gfc_directory(
    input_dir: str | Path,
    output_root: str | Path,
    ddk_types: Iterable[str],
    ddk_data_dir: str | Path,
    lmax: int = 96,
    overwrite: bool = True,
) -> list[DDKGfcResult]:
    """Apply one or more DDK filters to every GFC file in a directory."""
    in_dir = Path(input_dir)
    out_root = Path(output_root)
    kernel_dir = Path(ddk_data_dir)

    if not in_dir.is_dir():
        raise FileNotFoundError(f"Input GFC directory not found: {in_dir}")
    if not kernel_dir.is_dir():
        raise FileNotFoundError(f"DDK kernel directory not found: {kernel_dir}")

    gfc_files = sorted([p for p in in_dir.glob("*.gfc") if p.is_file()])
    if not gfc_files:
        raise FileNotFoundError(f"No .gfc files found in: {in_dir}")

    results: list[DDKGfcResult] = []
    for raw_type in ddk_types:
        ddk_type = _normalize_ddk_type(raw_type)
        out_dir = out_root / ddk_type
        out_dir.mkdir(parents=True, exist_ok=True)

        written = 0
        for src in gfc_files:
            dst = out_dir / _output_name(src.name, ddk_type)
            if dst.exists() and not overwrite:
                continue

            sh = read_gfc(str(src), lmax)
            c_filtered, s_filtered, meta = filter_sh_ddk(
                sh.C,
                sh.S,
                lmax,
                ddk_type=ddk_type,
                data_dir=str(kernel_dir),
            )
            if not meta.get("applied"):
                raise RuntimeError(f"{ddk_type} was not applied to {src}: {meta.get('error')}")

            _write_filtered_gfc(src, dst, c_filtered, s_filtered, ddk_type, lmax)
            written += 1

        results.append(DDKGfcResult(ddk_type=ddk_type, output_dir=out_dir, files_written=written))

    return results


def _normalize_ddk_type(raw: str) -> str:
    text = str(raw).strip().upper()
    if text.isdigit():
        text = f"DDK{text}"
    if not text.startswith("DDK"):
        text = f"DDK{text}"
    if text not in {f"DDK{i}" for i in range(1, 9)}:
        raise ValueError(f"Unsupported DDK type: {raw}")
    return text


def _output_name(source_name: str, ddk_type: str) -> str:
    stem = Path(source_name).stem
    suffix = Path(source_name).suffix or ".gfc"
    if f"_{ddk_type}" in stem:
        return f"{stem}{suffix}"
    return f"{stem}_{ddk_type}{suffix}"


def _write_filtered_gfc(
    source: Path,
    target: Path,
    c_filtered: np.ndarray,
    s_filtered: np.ndarray,
    ddk_type: str,
    lmax: int,
) -> None:
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
                        f"{c_filtered[degree, order]: .12E} "
                        f"{s_filtered[degree, order]: .12E} "
                        f"{sigma_c:>11s} {sigma_s:>11s}\n"
                    )
                else:
                    fout.write(line + "\n")
                continue

            fout.write(_rewrite_header_line(line, ddk_type, lmax) + "\n")

    tmp.replace(target)


def _rewrite_header_line(line: str, ddk_type: str, lmax: int) -> str:
    stripped = line.strip()
    if stripped.lower().startswith("modelname"):
        parts = stripped.split(None, 1)
        if len(parts) == 2 and not parts[1].endswith(f"_{ddk_type}"):
            return f"   modelname                {parts[1]}_{ddk_type}"
    if stripped.lower().startswith("max_degree"):
        return f"   max_degree               {lmax}"
    return line
