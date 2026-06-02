"""Download and identify GRACE/GRACE-FO GSM GFC files."""

from __future__ import annotations

import calendar
import contextlib
import json
import os
import re
import shutil
import tempfile
import netrc
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Literal

from grace_pipeline.core.time_index import extract_ym_from_gfc


CMR_GRANULE_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"

CENTER_ALIASES = {
    "CSR": ("UTCSR", "_CSR_", "CSR"),
    "JPL": ("JPLEM", "_JPL_", "JPL"),
    "GFZ": ("GFZOP", "_GFZ_", "GFZ"),
    "HUST": ("HUST", "HUST-GRACE"),
    "ITSG": ("ITSG", "ITSG-GRACE"),
    "GSFC": ("GSFC",),
}

GRACE_SHORT_NAMES = {
    "CSR": "GRACE_GSM_L2_GRAV_CSR_RL06",
    "JPL": "GRACE_GSM_L2_GRAV_JPL_RL06",
    "GFZ": "GRACE_GSM_L2_GRAV_GFZ_RL06",
}

GRACEFO_SHORT_NAMES = {
    "CSR": "GRACEFO_L2_CSR_MONTHLY_0063",
    "JPL": "GRACEFO_L2_JPL_MONTHLY_0063",
    "GFZ": "GRACEFO_L2_GFZ_MONTHLY_0063",
}

LOW_DEGREE_URLS = {
    "C20": "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-14_C30_C20_GSFC_SLR.txt",
    "DEGREE1_CSR": "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-13_GEOC_CSR_RL0603.txt",
    "DEGREE1_JPL": "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-13_GEOC_JPL_RL0603.txt",
    "DEGREE1_GFZ": "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-13_GEOC_GFZ_RL0603.txt",
}
EARTHDATA_TOKEN_URL = "https://urs.earthdata.nasa.gov/users/user_tokens"
EARTHDATA_TOKEN_STORE = Path.home() / ".grace_pipeline_earthdata_tokens.json"

ICGEM_BASE_URL = "https://icgem.gfz-potsdam.de"
ICGEM_GSM_SERIES = {
    "HUST": "/sp/03_other/HUST/HUST-Grace2016/unfiltered",
    "ITSG": "/sp/03_other/ITSG/ITSG-Grace2018/monthly",
}

MASCON_SOURCES = {
    "CSR": {
        "name": "CSR_GRACE_GRACE-FO_RL0603_Mascons_all-corrections.nc",
        "url": "https://download.csr.utexas.edu/outgoing/grace/RL0603_mascons/CSR_GRACE_GRACE-FO_RL0603_Mascons_all-corrections.nc",
        "resolution": "0.25",
    },
    "GSFC": {
        "name": "GSFC.glb.200204_202511_RL06v2.0_OBP-ICE6GD_HALFDEGREE.nc",
        "url": "https://earth.gsfc.nasa.gov/sites/default/files/geo/gsfc.glb_.200204_202511_rl06v2.0_obp-ice6gd_halfdegree.nc",
        "resolution": "0.5",
    },
    "JPL_CRI": {"short_name": "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4", "resolution": "0.5"},
    "JPL": {"short_name": "TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4", "resolution": "0.5"},
}


class EarthdataAuthRequired(RuntimeError):
    """Raised when a protected PO.DAAC object needs Earthdata credentials."""


@dataclass(frozen=True)
class GfcGranule:
    name: str
    url: str
    begin: str
    end: str


@dataclass(frozen=True)
class DownloadResult:
    files: tuple[Path, ...]
    skipped: tuple[Path, ...]
    center: str
    low_degree_files: dict[str, Path]
    product_type: str = "GSM"


def normalize_center(value: str | None) -> str:
    text = str(value or "").upper()
    for center, aliases in CENTER_ALIASES.items():
        if center in text or any(alias in text for alias in aliases):
            return center
    return "CSR"


def _normalize_mascon_source(value: str | None) -> str:
    text = str(value or "").upper()
    if "CSR" in text:
        return "CSR"
    if "GSFC" in text:
        return "GSFC"
    if "CRI" in text:
        return "JPL_CRI"
    if "JPL" in text:
        return "JPL"
    return "JPL_CRI"


def _normalize_mascon_resolution(value: str | float | None) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().lower().replace("degree", "").replace("deg", "").replace("°", "")
    text = text.strip()
    if text in {"025", ".25"}:
        text = "0.25"
    if text in {"05", ".5"}:
        text = "0.5"
    if text in {"1.0"}:
        text = "1"
    return text


def infer_center_from_gfc_name(value: str | Path | None) -> str:
    text = str(value or "").upper()
    for center, aliases in CENTER_ALIASES.items():
        if any(alias in text for alias in aliases):
            return center
    return "UNKNOWN"


def infer_center_from_gfc_file(path: str | Path) -> str:
    file_path = Path(path)
    center = infer_center_from_gfc_name(file_path.name)
    if center != "UNKNOWN":
        return center
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for idx, line in enumerate(handle):
                center = infer_center_from_gfc_name(line)
                if center != "UNKNOWN":
                    return center
                if idx >= 120:
                    break
    except OSError:
        return "UNKNOWN"
    return "UNKNOWN"


def infer_center_from_gfc_dir(gfc_dir: str | Path) -> str:
    root = Path(gfc_dir)
    if not root.exists():
        return infer_center_from_gfc_name(root)
    counts: dict[str, int] = {}
    for path in sorted(root.glob("*.gfc")):
        center = infer_center_from_gfc_file(path)
        if center != "UNKNOWN":
            counts[center] = counts.get(center, 0) + 1
    if counts:
        return max(counts.items(), key=lambda item: item[1])[0]
    return infer_center_from_gfc_name(root)


def _parse_ym(ym: str) -> datetime:
    match = re.match(r"^(\d{4})[-/]?(\d{2})", str(ym or "").strip())
    if not match:
        raise ValueError(f"Invalid YYYY-MM value: {ym!r}")
    year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month in YYYY-MM value: {ym!r}")
    return datetime(year, month, 1)


def _month_end(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, calendar.monthrange(dt.year, dt.month)[1], 23, 59, 59)


def _split_mission_ranges(start_ym: str, end_ym: str) -> Iterable[tuple[str, datetime, datetime]]:
    start = _parse_ym(start_ym)
    end = _month_end(_parse_ym(end_ym))
    if end < start:
        raise ValueError("End month must be after start month.")
    grace_end = datetime(2017, 6, 30, 23, 59, 59)
    gracefo_start = datetime(2018, 5, 22)
    if start <= grace_end:
        yield "GRACE", start, min(end, grace_end)
    if end >= gracefo_start:
        yield "GRACEFO", max(start, gracefo_start), end


def _cmr_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "GRACE-Level2-Pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def query_gsm_granules(center: str, start_ym: str, end_ym: str) -> list[GfcGranule]:
    center = normalize_center(center)
    if center in ICGEM_GSM_SERIES:
        return query_icgem_gfc_granules(center, start_ym, end_ym)
    granules: dict[str, GfcGranule] = {}
    for mission, start_dt, end_dt in _split_mission_ranges(start_ym, end_ym):
        short_name = (GRACE_SHORT_NAMES if mission == "GRACE" else GRACEFO_SHORT_NAMES)[center]
        temporal = f"{start_dt:%Y-%m-%dT%H:%M:%SZ},{end_dt:%Y-%m-%dT%H:%M:%SZ}"
        params = urllib.parse.urlencode({"short_name": short_name, "temporal": temporal, "page_size": "200"})
        payload = _cmr_json(f"{CMR_GRANULE_URL}?{params}")
        for item in payload.get("items", []):
            umm = item.get("umm", {}) or {}
            name = str(umm.get("GranuleUR", "") or "")
            if not name.startswith("GSM-"):
                continue
            if center == "CSR" and "_BA01_" not in name:
                continue
            url = _select_download_url(umm.get("RelatedUrls", []) or [])
            if not url:
                continue
            temporal_extent = (umm.get("TemporalExtent", {}) or {}).get("RangeDateTime", {}) or {}
            granules[name] = GfcGranule(
                name=name,
                url=url,
                begin=str(temporal_extent.get("BeginningDateTime", "") or ""),
                end=str(temporal_extent.get("EndingDateTime", "") or ""),
            )
    return sorted(granules.values(), key=lambda granule: granule.name)


def query_icgem_gfc_granules(center: str, start_ym: str, end_ym: str) -> list[GfcGranule]:
    center = normalize_center(center)
    series_path = ICGEM_GSM_SERIES.get(center)
    if not series_path:
        return []
    start = _parse_ym(start_ym)
    end = _parse_ym(end_ym)
    page_url = urllib.parse.urljoin(ICGEM_BASE_URL, series_path)
    html = _read_text_url(page_url)
    granules: dict[str, GfcGranule] = {}
    for href in re.findall(r'href="([^"]+\.gfc)"', html, flags=re.IGNORECASE):
        name = Path(urllib.parse.urlparse(href).path).name
        ym = extract_ym_from_gfc(name) or _extract_ym_from_any_filename(name)
        if not ym:
            continue
        dt = _parse_ym(ym)
        if start <= dt <= end:
            url = urllib.parse.urljoin(ICGEM_BASE_URL, href)
            granules[name] = GfcGranule(name=name, url=url, begin=f"{ym}-01T00:00:00Z", end="")
    return sorted(granules.values(), key=lambda granule: granule.name)


def query_mascon_granules(
    source: str,
    start_ym: str | None = None,
    end_ym: str | None = None,
    resolution: str | float | None = None,
) -> list[GfcGranule]:
    source_key = _normalize_mascon_source(source)
    requested_resolution = _normalize_mascon_resolution(resolution)
    available_resolution = str(MASCON_SOURCES[source_key].get("resolution", ""))
    if requested_resolution and requested_resolution != available_resolution:
        raise RuntimeError(f"{source_key} Mascon NetCDF is available at {available_resolution} degree, not {requested_resolution} degree.")
    if source_key in {"CSR", "GSFC"}:
        item = MASCON_SOURCES[source_key]
        return [GfcGranule(name=str(item["name"]), url=str(item["url"]), begin="", end="")]
    short_name = str(MASCON_SOURCES[source_key]["short_name"])
    params = {"short_name": short_name, "page_size": "200"}
    if start_ym and end_ym:
        start_dt = _parse_ym(start_ym)
        end_dt = _month_end(_parse_ym(end_ym))
        params["temporal"] = f"{start_dt:%Y-%m-%dT%H:%M:%SZ},{end_dt:%Y-%m-%dT%H:%M:%SZ}"
    payload = _cmr_json(f"{CMR_GRANULE_URL}?{urllib.parse.urlencode(params)}")
    out: list[GfcGranule] = []
    for item in payload.get("items", []):
        umm = item.get("umm", {}) or {}
        name = str(umm.get("GranuleUR", "") or "")
        url = _select_download_url(umm.get("RelatedUrls", []) or [])
        if not url:
            continue
        if name and not name.lower().endswith((".nc", ".nc4")) and ".nc" not in url.lower():
            # Keep only the data file, not documentation or metadata sidecars.
            if not any(str(x.get("Name", "")).lower().endswith((".nc", ".nc4")) for x in (umm.get("DataGranule", {}) or {}).get("ArchiveAndDistributionInformation", []) or []):
                continue
        temporal_extent = (umm.get("TemporalExtent", {}) or {}).get("RangeDateTime", {}) or {}
        out.append(
            GfcGranule(
                name=Path(urllib.parse.urlparse(url).path).name or name,
                url=url,
                begin=str(temporal_extent.get("BeginningDateTime", "") or ""),
                end=str(temporal_extent.get("EndingDateTime", "") or ""),
            )
        )
    return out


def _select_download_url(related_urls: list[dict]) -> str:
    for item in related_urls:
        url = str(item.get("URL", "") or "")
        if url.startswith("https://") and "podaac-ops-cumulus-protected" in url:
            return url
    for item in related_urls:
        url = str(item.get("URL", "") or "")
        if url.startswith("https://"):
            return url
    return ""


def _destination_name(name: str) -> str:
    return name if Path(name).suffix else f"{name}.gfc"


def _download_url(url: str, target: Path) -> None:
    _download_url_with_progress(url, target)


def _download_url_with_progress(
    url: str,
    target: Path,
    progress_bytes: Callable[[int, int], None] | None = None,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        headers = {"User-Agent": "GRACE-Level2-Pipeline/1.0"}
        token = active_earthdata_token()
        if token and ("earthdata.nasa.gov" in url or "podaac" in url):
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        opener = _build_opener()
        with opener.open(req, timeout=180) as response, tmp_path.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            last_emit = 0.0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                now = time.time()
                if progress_bytes and (now - last_emit >= 0.2 or (total and done >= total)):
                    progress_bytes(done, total)
                    last_emit = now
        os.replace(tmp_path, target)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise EarthdataAuthRequired(
                "PO.DAAC protected GSM download requires Earthdata credentials. "
                "Configure a .netrc entry for urs.earthdata.nasa.gov, then retry."
            ) from exc
        raise
    finally:
        with contextlib.suppress(OSError):
            tmp_path.unlink()


def _build_opener() -> urllib.request.OpenerDirector:
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    for host in ("urs.earthdata.nasa.gov", "archive.podaac.earthdata.nasa.gov"):
        creds = _netrc_credentials(host)
        if creds:
            login, password = creds
            password_mgr.add_password(None, f"https://{host}", login, password)
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(),
        urllib.request.HTTPBasicAuthHandler(password_mgr),
        urllib.request.HTTPDigestAuthHandler(password_mgr),
    )


def has_earthdata_credentials() -> bool:
    return bool(active_earthdata_token()) or _netrc_credentials("urs.earthdata.nasa.gov") is not None


def current_earthdata_login() -> str:
    state = _read_token_store()
    active = str(state.get("active", "") or "")
    if active:
        accounts = state.get("accounts", {}) or {}
        if active in accounts:
            return active
    creds = _netrc_credentials("urs.earthdata.nasa.gov")
    return creds[0] if creds else ""


def active_earthdata_token() -> str:
    state = _read_token_store()
    active = str(state.get("active", "") or "")
    account = (state.get("accounts", {}) or {}).get(active, {}) if active else {}
    return str(account.get("token", "") or "").strip()


def save_earthdata_token(label: str, token: str, replace_active: bool = True) -> Path:
    label = str(label or "").strip() or "default"
    token = str(token or "").strip()
    if not token:
        raise ValueError("Earthdata token is required.")
    state = _read_token_store()
    accounts = dict(state.get("accounts", {}) or {})
    accounts[label] = {"token": token, "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"}
    state["accounts"] = accounts
    if replace_active or not state.get("active"):
        state["active"] = label
    _write_token_store(state)
    return EARTHDATA_TOKEN_STORE


def clear_earthdata_token(label: str | None = None) -> Path:
    state = _read_token_store()
    accounts = dict(state.get("accounts", {}) or {})
    if label:
        accounts.pop(label, None)
    else:
        accounts = {}
    state["accounts"] = accounts
    if state.get("active") not in accounts:
        state["active"] = next(iter(accounts), "")
    _write_token_store(state)
    return EARTHDATA_TOKEN_STORE


def _read_token_store() -> dict:
    if not EARTHDATA_TOKEN_STORE.exists():
        return {"active": "", "accounts": {}}
    try:
        payload = json.loads(EARTHDATA_TOKEN_STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"active": "", "accounts": {}}
    if not isinstance(payload, dict):
        return {"active": "", "accounts": {}}
    payload.setdefault("active", "")
    payload.setdefault("accounts", {})
    return payload


def _write_token_store(state: dict) -> None:
    EARTHDATA_TOKEN_STORE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_earthdata_credentials(username: str, password: str, replace: bool = True) -> Path:
    username = str(username or "").strip()
    password = str(password or "").strip()
    if not username or not password:
        raise ValueError("Earthdata username and password are required.")
    path = Path.home() / ".netrc"
    machines = {
        "urs.earthdata.nasa.gov": (username, password),
        "archive.podaac.earthdata.nasa.gov": (username, password),
    }
    _write_netrc_entries(path, machines, replace=replace)
    return path


def clear_earthdata_credentials() -> Path:
    path = Path.home() / ".netrc"
    _write_netrc_entries(path, {}, replace=True, remove_hosts={"urs.earthdata.nasa.gov", "archive.podaac.earthdata.nasa.gov"})
    return path


def _write_netrc_entries(
    path: Path,
    machines: dict[str, tuple[str, str]],
    replace: bool = True,
    remove_hosts: set[str] | None = None,
) -> None:
    remove_hosts = set(remove_hosts or set())
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    preserved: list[str] = []
    idx = 0
    update_hosts = set(machines) if replace else set()
    skip_hosts = update_hosts | remove_hosts
    while idx < len(lines):
        line = lines[idx]
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "machine" and parts[1] in skip_hosts:
            idx += 1
            while idx < len(lines):
                next_parts = lines[idx].split()
                if len(next_parts) >= 2 and next_parts[0] == "machine":
                    break
                idx += 1
            continue
        preserved.append(line)
        idx += 1
    for host, (login, password) in machines.items():
        preserved.append(f"machine {host}")
        preserved.append(f"  login {login}")
        preserved.append(f"  password {password}")
    path.write_text("\n".join(preserved).rstrip() + "\n", encoding="utf-8")


def _netrc_credentials(host: str) -> tuple[str, str] | None:
    try:
        auth = netrc.netrc().authenticators(host)
    except (FileNotFoundError, netrc.NetrcParseError, OSError):
        return None
    if not auth:
        return None
    login, _account, password = auth
    if login and password:
        return login, password
    return None


def download_low_degree_files(low_degree_dir: str | Path, progress: Callable[[str], None] | None = None) -> dict[str, Path]:
    out_dir = Path(low_degree_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded: dict[str, Path] = {}
    for key, url in LOW_DEGREE_URLS.items():
        target = out_dir / Path(urllib.parse.urlparse(url).path).name
        if not target.exists():
            if progress:
                progress(f"Downloading {target.name}")
            _download_url(url, target)
        downloaded[key] = target
    return downloaded


def download_gfc_range(
    gfc_dir: str | Path,
    start_ym: str,
    end_ym: str,
    center: str | None = None,
    low_degree_dir: str | Path | None = None,
    progress: Callable[[str], None] | None = None,
    progress_pct: Callable[[float, str], None] | None = None,
    max_workers: int = 6,
) -> DownloadResult:
    out_dir = Path(gfc_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_center = normalize_center(center or infer_center_from_gfc_dir(out_dir))
    granules = query_gsm_granules(resolved_center, start_ym, end_ym)
    if not granules:
        raise RuntimeError(f"No GSM GFC granules found for {resolved_center} {start_ym} to {end_ym}.")

    files: list[Path] = []
    skipped: list[Path] = []
    pending: list[tuple[int, GfcGranule, Path]] = []
    total = len(granules)
    completed = 0
    for idx, granule in enumerate(granules, start=1):
        target = out_dir / _destination_name(granule.name)
        existing_ym = extract_ym_from_gfc(str(target)) if target.exists() else None
        if target.exists() and existing_ym:
            skipped.append(target)
            completed += 1
            if progress_pct:
                progress_pct(100.0 * completed / max(1, total), f"{completed}/{total}::{target.name} skipped")
            continue
        pending.append((idx, granule, target))

    def download_one(item: tuple[int, GfcGranule, Path]) -> Path:
        idx, granule, target = item
        if progress:
            progress(f"Downloading {granule.name}")

        def on_bytes(done: int, total: int, file_idx: int = idx, file_name: str = target.name) -> None:
            if not progress_pct:
                return
            if total > 0:
                file_fraction = max(0.0, min(1.0, done / total))
            else:
                file_fraction = 0.0
            overall = 100.0 * ((file_idx - 1) + file_fraction) / max(1, len(granules))
            progress_pct(overall, f"{file_idx}/{len(granules)}::{file_name} {_format_bytes(done)}")

        _download_url_with_progress(granule.url, target, progress_bytes=on_bytes)
        return target

    workers = max(1, min(int(max_workers or 1), len(pending) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(download_one, item) for item in pending]
        for future in as_completed(futures):
            path = future.result()
            files.append(path)
            completed += 1
            if progress_pct:
                progress_pct(100.0 * completed / max(1, total), f"{completed}/{total}::{path.name} complete")

    low_degree_files: dict[str, Path] = {}
    if low_degree_dir:
        low_degree_files = download_low_degree_files(low_degree_dir, progress=progress)

    return DownloadResult(
        files=tuple(files),
        skipped=tuple(skipped),
        center=resolved_center,
        low_degree_files=low_degree_files,
        product_type="GSM",
    )


def download_mascon_nc(
    out_dir: str | Path,
    source: str = "JPL_CRI",
    start_ym: str | None = None,
    end_ym: str | None = None,
    resolution: str | float | None = None,
    progress: Callable[[str], None] | None = None,
    progress_pct: Callable[[float, str], None] | None = None,
) -> DownloadResult:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    source_key = _normalize_mascon_source(source)
    granules = query_mascon_granules(source_key, start_ym=start_ym, end_ym=end_ym, resolution=resolution)
    if not granules:
        raise RuntimeError(f"No Mascon NetCDF files found for {source_key}.")
    files: list[Path] = []
    skipped: list[Path] = []
    for granule in granules:
        idx = len(files) + len(skipped) + 1
        name = granule.name or Path(urllib.parse.urlparse(granule.url).path).name
        if not name.lower().endswith((".nc", ".nc4")):
            name = f"{name}.nc"
        target = target_dir / name
        if target.exists() and target.stat().st_size > 0:
            skipped.append(target)
            continue
        if progress:
            progress(f"Downloading {name}")

        def on_bytes(done: int, total: int, file_idx: int = idx, file_name: str = target.name) -> None:
            if not progress_pct:
                return
            file_fraction = max(0.0, min(1.0, done / total)) if total > 0 else 0.0
            overall = 100.0 * ((file_idx - 1) + file_fraction) / max(1, len(granules))
            progress_pct(overall, f"{file_idx}/{len(granules)}::{file_name} {_format_bytes(done)}")

        _download_url_with_progress(granule.url, target, progress_bytes=on_bytes)
        files.append(target)
    return DownloadResult(
        files=tuple(files),
        skipped=tuple(skipped),
        center=source_key,
        low_degree_files={},
        product_type="MASCON_NC",
    )


def _read_text_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"Accept": "text/html,text/plain", "User-Agent": "GRACE-Level2-Pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read().decode("utf-8", errors="ignore")


def _extract_ym_from_any_filename(name: str) -> str | None:
    basename = Path(name).name
    for pattern in (r"(?<!\d)(20\d{2})[-_]?([01]\d)(?!\d)", r"(?<!\d)(\d{4})([01]\d)(?!\d)"):
        match = re.search(pattern, basename)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            if 1 <= month <= 12:
                return f"{year:04d}-{month:02d}"
    return None


def _format_bytes(value: int) -> str:
    value = int(max(0, value))
    if value < 1024 * 1024:
        return f"{value / 1024:.0f}KB"
    return f"{value / 1024 / 1024:.1f}MB"
