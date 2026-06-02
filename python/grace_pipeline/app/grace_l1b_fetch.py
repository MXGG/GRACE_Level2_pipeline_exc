"""Utilities to fetch GRACE Level-1B orbit/instrument bundles from GFZ ISDC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List
import shutil
import tarfile
import urllib.request


GFZ_L1B_BASE = "https://isdc-data.gfz.de/grace/Level-1B/JPL/INSTRUMENT"


@dataclass(frozen=True)
class GraceL1BTarget:
    release: str
    stamp: str
    url: str
    archive_name: str


def build_gfz_target(*, release: str, month: str | None = None, day: str | None = None) -> GraceL1BTarget:
    rel = str(release or "RL03").strip().upper()
    if rel not in {"RL02", "RL03"}:
        raise ValueError("release must be RL02 or RL03")
    if rel == "RL03":
        if not month:
            raise ValueError("RL03 requires --month YYYY-MM")
        stamp = datetime.strptime(month, "%Y-%m").strftime("%Y-%m")
        archive = f"grace_1B_{stamp}_03.tar.gz"
        url = f"{GFZ_L1B_BASE}/RL03/{archive}"
        return GraceL1BTarget(rel, stamp, url, archive)
    if not day:
        raise ValueError("RL02 requires --day YYYY-MM-DD")
    stamp = datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d")
    year = stamp[:4]
    archive = f"grace_1B_{stamp}_02.tar.gz"
    url = f"{GFZ_L1B_BASE}/RL02/{year}/{archive}"
    return GraceL1BTarget(rel, stamp, url, archive)


def download_target(target: GraceL1BTarget, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / target.archive_name
    if archive_path.exists() and archive_path.stat().st_size > 0:
        return archive_path
    tmp_path = archive_path.with_suffix(archive_path.suffix + ".tmp")
    with urllib.request.urlopen(target.url) as response, tmp_path.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1024 * 1024)
    tmp_path.replace(archive_path)
    return archive_path


def list_archive_members(archive_path: Path, limit: int | None = None) -> List[str]:
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    return names[:limit] if limit else names


def extract_selected_members(
    archive_path: Path,
    out_dir: Path,
    prefixes: Iterable[str],
) -> List[Path]:
    wanted = tuple(str(p).upper() for p in prefixes if str(p).strip())
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: List[Path] = []
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if wanted and not any(name.upper().startswith(prefix) for prefix in wanted):
                continue
            target_path = (out_dir / member.name).resolve()
            if not str(target_path).startswith(str(out_dir.resolve())):
                continue
            tar.extract(member, path=out_dir)
            extracted.append(out_dir / member.name)
    return extracted
