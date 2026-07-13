"""Stable preview rendering for longitude-normalized global grids.

This renderer is installed last.  It avoids the common CSR Mascon/Level-3
longitude mismatch where data are stored on a 0..360 grid while coastlines and
annotations are drawn in -180..180 coordinates.
"""

from __future__ import annotations

import contextlib
import time
import warnings
from pathlib import Path
from types import MethodType

import numpy as np
import matplotlib.ticker as mticker

from grace_pipeline.infra.stack.loader import load_stack_any, load_stack_slice_any
from grace_pipeline.infra.stack.probe import probe_stack_any
from grace_pipeline.ui.plotting.boundaries import draw_boundaries, plot_line, read_boundary_file, split_dateline
from grace_pipeline.ui.plotting.projections import (
    apply_proj_scale,
    get_conic_parallels,
    get_proj_center,
    normalize_lon_for_plot,
    parse_float,
    scale_projection,
    split_plot_lon_segments,
    wrap_delta_lon,
)
from grace_pipeline.ui.qt import preview_enhancements as pe
from grace_pipeline.ui.qt.preview_view_polish import _draw_graticule_frame, _graticule_options, _projection_accepts_rectangular_frame
from grace_pipeline.ui.qt.projection_registry import (
    is_global_extent,
    projection_default_extent,
    projection_name_to_key,
    projection_renderer,
    projection_spec,
    projection_supports_global_extent,
)
from grace_pipeline.ui.qt.preview_title_status import restore_preview_header
from grace_pipeline.ui.qt.preview_science import (
    LayerTimeMatch,
    open_shapefile_reader,
    select_layer_time_index,
    unit_from_metadata,
    value_label,
    variable_unit_from_file,
)

_GRID_COLOR = "#6f8fa3"
_COAST_COLOR = "#1f3547"
_RECTANGULAR_CARTOPY_KEYS = {"plate_carree", "mercator", "miller", "lambert_cylindrical"}


def _safe_disconnect(signal) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with contextlib.suppress(Exception):
            signal.disconnect()


def _show_layer(controller, layer_type: str, *, path: str | None = None, fallback: bool = True) -> bool:
    with contextlib.suppress(Exception):
        if hasattr(controller, "_preview_layer_visible"):
            return bool(controller._preview_layer_visible(layer_type, path=path))
    return bool(fallback)


def _visible_layers(controller, *layer_types: str):
    with contextlib.suppress(Exception):
        if hasattr(controller, "_preview_layers_by_type"):
            return controller._preview_layers_by_type(*layer_types, visible_only=True)
    return []


def _show_grid(controller) -> bool:
    page = controller.window.page_preview
    spatial_switch = getattr(page, "chk_enable_spatial_grid", None)
    if spatial_switch is not None and not spatial_switch.isChecked():
        return False
    fallback = bool(getattr(page, "chk_layer_grid", None) and page.chk_layer_grid.isChecked())
    return _show_layer(controller, "graticule", fallback=fallback)


def _show_colorbar(controller) -> bool:
    page = controller.window.page_preview
    fallback = bool(getattr(page, "chk_show_colorbar", None) is None or page.chk_show_colorbar.isChecked())
    return _show_layer(controller, "colorbar", fallback=fallback)


def _show_coastlines(controller) -> bool:
    page = controller.window.page_preview
    fallback = bool(getattr(page, "chk_layer_coastlines", None) is None or page.chk_layer_coastlines.isChecked())
    return _show_layer(controller, "coastline", fallback=fallback)


def _show_base_raster(controller) -> bool:
    with contextlib.suppress(Exception):
        controller._ensure_preview_layers()
        return any(layer.type == "raster" and layer.path is None and layer.visible for layer in controller.preview_layers)
    page = controller.window.page_preview
    return bool(getattr(page, "chk_layer_data", None) is None or page.chk_layer_data.isChecked())


def _layer_artist_zorder(layer, fallback: float = 0.0) -> float:
    """Map the controller's bottom-first layer order to Matplotlib directly."""

    raw = getattr(layer, "zorder", fallback)
    try:
        return 2.0 + float(fallback if raw is None else raw)
    except (TypeError, ValueError):
        return 2.0 + float(fallback)


def _is_3d_label(page) -> bool:
    return projection_renderer(page.cmb_projection.currentText().strip()) == "matplotlib_3d"


def _normalize_grid_longitudes(lon: np.ndarray, grid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return longitude as -180..180 and reorder the first grid axis."""

    lon = np.asarray(lon, dtype=float).squeeze()
    grid = np.asarray(grid, dtype=float)
    lon_plot = normalize_lon_for_plot(lon)
    order = np.argsort(lon_plot)
    lon_sorted = lon_plot[order]
    if grid.shape[0] == lon.size:
        grid_sorted = grid[order, :]
    elif grid.ndim >= 2 and grid.shape[1] == lon.size:
        grid_sorted = grid[:, order].T
    else:
        grid_sorted = grid
    return lon_sorted, grid_sorted


def _frame_context(controller):
    page = controller.window.page_preview
    path, idx, frame, grid, lon, lat = pe._grid_context(controller)
    grid, lon, lat, bbox = pe._apply_bbox(controller, grid, lon, lat)
    lon_plot, grid = _normalize_grid_longitudes(lon, grid)
    lat = np.asarray(lat, dtype=float).squeeze()
    return path, idx, frame, grid, lon_plot, lat, bbox


def _project(controller, proj: str, lon, lat, *, lon0=0.0, lat0=0.0, lat1=30.0, lat2=60.0):
    if proj == "PlateCarree":
        return np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    x, y = controller._project(proj, lon, lat, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
    x = apply_proj_scale(x, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None))
    return x, y


def _line(ax, x, y, *, color, linewidth, alpha=1.0, linestyle="-", zorder=20):
    if str(linestyle or "").strip().lower() in {"none", "no line", "无线条", "off", "关闭"}:
        return
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    if not np.any(ok):
        return
    x2 = x.copy()
    y2 = y.copy()
    x2[~ok] = np.nan
    y2[~ok] = np.nan
    plot_line(ax, x2, y2, color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle, zorder=zorder)


def _label(ax, x, y, text, *, ha="center", va="center", fontsize=7, fontfamily=None, zorder=35) -> None:
    if not (np.isfinite(x) and np.isfinite(y)):
        return
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    dx = abs(xmax - xmin)
    dy = abs(ymax - ymin)
    if not (min(xmin, xmax) - 0.05 * dx <= x <= max(xmin, xmax) + 0.05 * dx):
        return
    if not (min(ymin, ymax) - 0.05 * dy <= y <= max(ymin, ymax) + 0.05 * dy):
        return
    ax.text(
        x,
        y,
        text,
        fontsize=fontsize,
        fontfamily=fontfamily,
        color="#405766",
        ha=ha,
        va=va,
        clip_on=True,
        zorder=zorder,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.55, "pad": 0.8},
    )


def _draw_graticule(controller, proj, lon0, lat0, lat1, lat2, zorder=25) -> None:
    if not _show_grid(controller):
        return
    ax = controller._ax
    opts = _graticule_options(controller)
    lat_lines = np.arange(-90 + opts["lat_interval"], 90, opts["lat_interval"])
    lon_lines = np.arange(-180, 180 + 0.1, opts["lon_interval"])
    for lat_line in lat_lines:
        lons = np.linspace(-180, 180, 721)
        lats = np.full_like(lons, lat_line, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        _line(ax, x, y, color=opts["color"], linewidth=opts["linewidth"], alpha=0.86, linestyle=opts["linestyle"], zorder=zorder)
    for lon_line in lon_lines:
        lats = np.linspace(-88, 88, 721)
        lons = np.full_like(lats, lon_line, dtype=float)
        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        _line(ax, x, y, color=opts["color"], linewidth=opts["linewidth"], alpha=0.86, linestyle=opts["linestyle"], zorder=zorder)

    if not opts["show_labels"]:
        if _projection_accepts_rectangular_frame(proj):
            _draw_graticule_frame(ax, opts)
        return

    label_lat = -82.0
    for lon_line in np.arange(-180 + opts["lon_interval"], 180 + 0.1, opts["lon_interval"]):
        x, y = _project(
            controller,
            proj,
            np.asarray([lon_line], dtype=float),
            np.asarray([label_lat], dtype=float),
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
        )
        text = f"{abs(int(lon_line))}°{'W' if lon_line < 0 else ('E' if lon_line > 0 else '')}"
        _label(
            ax,
            float(x[0]),
            float(y[0]),
            text,
            va="top",
            fontsize=opts["font_size"],
            fontfamily=opts["font_family"],
            zorder=zorder + 0.1,
        )

    label_lon = -174.0
    for lat_line in lat_lines:
        x, y = _project(
            controller,
            proj,
            np.asarray([label_lon], dtype=float),
            np.asarray([lat_line], dtype=float),
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
        )
        text = f"{abs(int(lat_line))}°{'S' if lat_line < 0 else ('N' if lat_line > 0 else '')}"
        _label(
            ax,
            float(x[0]),
            float(y[0]),
            text,
            ha="right",
            fontsize=opts["font_size"],
            fontfamily=opts["font_family"],
            zorder=zorder + 0.1,
        )
    if _projection_accepts_rectangular_frame(proj):
        _draw_graticule_frame(ax, opts)


def _draw_coastlines(controller, proj, lon0, lat0, lat1, lat2, zorder=32) -> None:
    if not _show_coastlines(controller):
        return
    coast_path = ""
    with contextlib.suppress(Exception):
        coast_path = controller._resolve_coastline_path()
    if not coast_path:
        return
    try:
        import os
        shp_path = coast_path
        if os.path.isdir(shp_path):
            for filename in os.listdir(shp_path):
                if filename.lower().endswith(".shp"):
                    shp_path = os.path.join(shp_path, filename)
                    break
        with open_shapefile_reader(shp_path) as reader:
            for shape in reader.shapes():
                pts = np.asarray(shape.points, dtype=float)
                if pts.ndim != 2 or pts.shape[0] < 2:
                    continue
                parts = list(shape.parts) + [len(pts)]
                for i in range(len(parts) - 1):
                    seg = pts[parts[i] : parts[i + 1]]
                    if seg.shape[0] < 2:
                        continue
                    for lons, lats in split_dateline(seg[:, 0], seg[:, 1], wrap_delta_lon, lon0=lon0):
                        x, y = _project(controller, proj, lons, lats, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                        _line(controller._ax, x, y, color=_COAST_COLOR, linewidth=0.44, alpha=0.92, zorder=zorder)
    except Exception:
        return


def _draw_boundary_layer(controller, layer, proj, lon0, lat0, lat1, lat2, bbox, zorder=40) -> None:
    path = str(getattr(layer, "path", "") or "")
    if not path or Path(path).suffix.lower() not in {".shp", ".bln", ".txt"}:
        return
    if not Path(path).exists():
        return
    with contextlib.suppress(Exception):
        boundaries = read_boundary_file(path)
        draw_boundaries(
            controller._ax,
            boundaries,
            proj=proj,
            lon0=lon0,
            lat0=lat0,
            lat1=lat1,
            lat2=lat2,
            bbox=bbox,
            normalize_lon_for_plot_cb=lambda arr: normalize_lon_for_plot(arr, lon_mode="-180_180"),
            split_dateline_cb=lambda lons, lats, lon0=0.0: split_dateline(lons, lats, wrap_delta_lon, lon0=lon0),
            split_plot_lon_segments_cb=lambda lons, lats, plate_carree=False: split_plot_lon_segments(
                lons,
                lats,
                split_dateline,
                lon0=lon0,
                plate_carree=plate_carree,
                lon_mode="-180_180",
            ),
            apply_proj_scale_cb=lambda xx: apply_proj_scale(xx, getattr(controller, "_proj_scale", None), getattr(controller, "_proj_x0", None)),
            plot_line_cb=lambda ax, x, y, **kwargs: plot_line(ax, x, y, **{**kwargs, "zorder": zorder}),
            projector_cb=controller._project,
        )


def _draw_boundary_layers(controller, proj, lon0, lat0, lat1, lat2, bbox) -> None:
    for layer in _visible_layers(controller, "boundary", "shapefile"):
        _draw_boundary_layer(controller, layer, proj, lon0, lat0, lat1, lat2, bbox)


def _log_preview_once(controller, key: tuple, message: str, channel: str = "stderr") -> None:
    seen = getattr(controller, "_preview_science_log_keys", None)
    if not isinstance(seen, set):
        seen = set()
        controller._preview_science_log_keys = seen
    if key in seen:
        return
    seen.add(key)
    with contextlib.suppress(Exception):
        controller.on_log(message, channel)


def _imported_raster_probe(controller, layer) -> tuple[int, object, dict]:
    path = str(getattr(layer, "path", "") or "")
    layer_meta = dict(getattr(layer, "metadata", {}) or {})
    active_var = str(layer_meta.get("active_var") or "").strip()
    mtime_ns = Path(path).stat().st_mtime_ns
    key = (path, mtime_ns, active_var)
    cache = getattr(controller, "_preview_imported_raster_probe_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        controller._preview_imported_raster_probe_cache = cache
    if key in cache:
        layer_length, times, file_meta = cache[key]
        merged_meta = dict(file_meta)
        merged_meta.update(layer_meta)
        return layer_length, times, merged_meta

    shape, _lon, _lat, times, probed_meta = probe_stack_any(path, load_stack_any)
    if not shape:
        raise ValueError("Unable to inspect raster layer time axis.")
    file_meta = dict(probed_meta or {})
    if active_var:
        file_meta["active_var"] = active_var
    selected_var = str(file_meta.get("active_var") or active_var or "").strip()
    unit = variable_unit_from_file(path, selected_var)
    if unit:
        file_meta["units"] = unit
    layer_length = int(shape[2]) if len(shape) >= 3 else 1
    result = (max(1, layer_length), times, file_meta)
    if len(cache) > 12:
        cache.clear()
    cache[key] = result
    merged_meta = dict(file_meta)
    merged_meta.update(layer_meta)
    return result[0], result[1], merged_meta


def _resolve_imported_raster_time(
    controller,
    layer,
    requested_index: int,
    *,
    target_time=None,
    target_meta: dict | None = None,
) -> tuple[int, dict, LayerTimeMatch] | None:
    path = str(getattr(layer, "path", "") or "")
    try:
        layer_length, layer_times, layer_meta = _imported_raster_probe(controller, layer)
    except Exception as exc:
        _log_preview_once(
            controller,
            ("overlay-probe", path, str(exc)),
            f"[PREVIEW] Raster overlay skipped; unable to inspect {path}: {exc}",
        )
        return None

    target_meta = dict(target_meta or {})
    match = select_layer_time_index(
        target_time,
        layer_times,
        requested_index=requested_index,
        layer_length=layer_length,
        # Preview layers follow the selected preview month exactly.  Nearest-
        # month tolerance belongs to processing/reference matching, not to a
        # visual layer stack, and is intentionally not user-configurable here.
        tolerance_months=0,
        target_units=target_meta.get("time_units"),
        target_calendar=target_meta.get("time_calendar"),
        layer_units=layer_meta.get("time_units"),
        layer_calendar=layer_meta.get("time_calendar"),
    )
    layer_name = str(getattr(layer, "name", "") or Path(path).name)
    if not match.matched:
        _log_preview_once(
            controller,
            ("overlay-time-unmatched", path, str(match.target_month), match.message),
            f"[PREVIEW] Raster overlay '{layer_name}' skipped: {match.message}",
        )
        return None
    if match.method == "positional-unverified":
        _log_preview_once(
            controller,
            ("overlay-time-positional", path, requested_index, match.message),
            f"[PREVIEW] Raster overlay '{layer_name}': {match.message}",
        )
    return int(match.index), layer_meta, match


def _tag_raster_artist(
    artist,
    *,
    var_name: str,
    meta: dict,
    match: LayerTimeMatch | None = None,
    source_path: str = "",
    values=None,
):
    if artist is None:
        return None
    unit = unit_from_metadata(meta, var_name)
    artist._grace_preview_label = value_label(var_name, unit)
    artist._grace_preview_unit = unit
    artist._grace_preview_time_match = match
    artist._grace_preview_source_path = str(source_path or "")
    if values is not None:
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        artist._grace_preview_mean = float(np.nanmean(finite)) if finite.size else float("nan")
    return artist


def _base_raster_label(controller, frame: dict) -> str:
    page = controller.window.page_preview
    meta = dict(frame.get("meta", {}) or {})
    var_name = str(meta.get("active_var") or page.cmb_data_var.currentText().strip() or "value")
    unit = unit_from_metadata(meta, var_name) or variable_unit_from_file(
        page.edit_dataset_source.text().strip(),
        var_name,
    )
    return value_label(var_name, unit)


def _raster_artist_label(controller, artist, frame: dict) -> str:
    label = str(getattr(artist, "_grace_preview_label", "") or "").strip()
    return label or _base_raster_label(controller, frame)


def _update_visible_raster_status(controller, artist) -> None:
    if artist is None:
        return
    source_path = str(getattr(artist, "_grace_preview_source_path", "") or "")
    if not source_path:
        return
    page = controller.window.page_preview
    label = str(getattr(artist, "_grace_preview_label", "") or "value")
    page.lbl_dataset.setText(f"{Path(source_path).name} | {label}")
    mean = float(getattr(artist, "_grace_preview_mean", float("nan")))
    unit = str(getattr(artist, "_grace_preview_unit", "") or "")
    controller._preview_value_unit = unit
    if np.isfinite(mean):
        page.lbl_grid_value.setText(f"{mean:.3f} {unit}".strip())


def _append_preview_value_unit(controller) -> None:
    """Keep the cursor-value status unit after the legacy pick callback runs."""

    unit = str(getattr(controller, "_preview_value_unit", "") or "").strip()
    if not unit:
        return
    label = controller.window.page_preview.lbl_grid_value
    text = str(label.text() or "").strip()
    if not text or text in {"—", "-", "NaN"} or text.endswith(f" {unit}"):
        return
    label.setText(f"{text} {unit}")


def _draw_imported_raster_layer(
    controller,
    layer,
    idx,
    proj,
    lon0,
    lat0,
    lat1,
    lat2,
    cmap,
    cmin,
    cmax,
    *,
    target_time=None,
    target_meta: dict | None = None,
):
    page = controller.window.page_preview
    path = str(getattr(layer, "path", "") or "")
    if not path:
        return None
    if Path(path).suffix.lower() not in {".nc", ".nc4", ".cdf", ".h5", ".hdf5", ".hdf", ".mat"}:
        return None
    if not Path(path).exists():
        return None
    resolved = _resolve_imported_raster_time(
        controller,
        layer,
        idx,
        target_time=target_time,
        target_meta=target_meta,
    )
    if resolved is None:
        return None
    layer_index, meta, time_match = resolved
    try:
        active_var = str(meta.get("active_var") or page.cmb_data_var.currentText().strip() or "").strip() or None
        grid, lon, lat, _t_val, loaded_meta = load_stack_slice_any(
            path,
            time_index=layer_index,
            active_var=active_var,
            selection_meta=meta,
        )
        if grid is None or lon is None or lat is None:
            return None
        merged_meta = dict(meta)
        merged_meta.update(dict(loaded_meta or {}))
        unit = unit_from_metadata(merged_meta, active_var or "") or variable_unit_from_file(path, active_var or "")
        if unit:
            merged_meta["units"] = unit
        grid = np.asarray(grid, dtype=float)
        lon = np.asarray(lon, dtype=float).squeeze()
        lat = np.asarray(lat, dtype=float).squeeze()
        if grid.shape[0] != lon.size and grid.ndim >= 2 and grid.shape[1] == lon.size:
            grid = grid.T
        lon, grid = _normalize_grid_longitudes(lon, grid)
        lon2d, lat2d = np.meshgrid(lon, lat)
        grid_plot = grid.T if grid.shape == (lon.size, lat.size) else np.squeeze(grid)
        x, y = _project(controller, proj, lon2d, lat2d, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        alpha = float(getattr(layer, "opacity", 0.72) or 0.72)
        zorder = _layer_artist_zorder(layer)
        artist = controller._ax.pcolormesh(
            x,
            y,
            grid_plot,
            shading="auto",
            cmap=cmap,
            vmin=cmin,
            vmax=cmax,
            alpha=max(0.05, min(1.0, alpha)),
            zorder=zorder,
        )
        return _tag_raster_artist(
            artist,
            var_name=active_var or "value",
            meta=merged_meta,
            match=time_match,
            source_path=path,
            values=grid,
        )
    except Exception as exc:
        _log_preview_once(
            controller,
            ("overlay-render", path, layer_index, str(exc)),
            f"[PREVIEW] Raster overlay failed: {path}: {exc}",
        )
    return None


def _draw_imported_raster_layers(controller, idx, proj, lon0, lat0, lat1, lat2, cmap, cmin, cmax, *, target_time=None, target_meta=None):
    first_im = None
    for layer in _visible_layers(controller, "raster"):
        if not getattr(layer, "path", None):
            continue
        im = _draw_imported_raster_layer(
            controller,
            layer,
            idx,
            proj,
            lon0,
            lat0,
            lat1,
            lat2,
            cmap,
            cmin,
            cmax,
            target_time=target_time,
            target_meta=target_meta,
        )
        if first_im is None and im is not None:
            first_im = im
    return first_im


def _color_limits(page, grid_plot):
    cmin = parse_float(page.edit_cmin.text())
    cmax = parse_float(page.edit_cmax.text())
    return cmin, cmax


def _render_manual_2d(controller) -> None:
    page = controller.window.page_preview
    with contextlib.suppress(Exception):
        controller._ensure_preview_layers()
        controller._sync_preview_legacy_layer_controls()
    start = time.perf_counter()
    path, idx, frame, grid, lon, lat, _bbox = _frame_context(controller)
    proj = pe._projection_key(controller, page.cmb_projection.currentText().strip())

    lon2d, lat2d = np.meshgrid(lon, lat)
    grid_plot = grid.T if grid.shape == (lon.size, lat.size) else grid
    lon0, lat0 = get_proj_center(lon, lat)
    lat1, lat2 = get_conic_parallels(float(np.nanmin(lat)), float(np.nanmax(lat)))

    if proj == "PlateCarree":
        x, y = lon2d, lat2d
        controller._proj_scale = None
        controller._proj_x0 = None
    else:
        x_raw, y_raw = controller._project(proj, lon2d, lat2d, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
        x, y, controller._proj_scale, controller._proj_x0 = scale_projection(x_raw, y_raw, target_ratio=2.0)

    cmin, cmax = _color_limits(page, grid_plot)
    cmap = page.cmb_cmap.currentText().strip() or "RdBu_r"

    controller._figure.clear()
    ax = controller._figure.add_subplot(111)
    controller._ax = ax
    im = None
    ax.set_axis_off()
    finite = np.isfinite(x) & np.isfinite(y)
    if np.any(finite):
        xmin, xmax = float(np.nanmin(x[finite])), float(np.nanmax(x[finite]))
        ymin, ymax = float(np.nanmin(y[finite])), float(np.nanmax(y[finite]))
        xr = max(1e-9, xmax - xmin)
        yr = max(1e-9, ymax - ymin)
        ax.set_xlim(xmin - 0.045 * xr, xmax + 0.045 * xr)
        ax.set_ylim(ymin - 0.07 * yr, ymax + 0.07 * yr)
        controller._preview_full_view = (xmin - 0.045 * xr, xmax + 0.045 * xr, ymin - 0.07 * yr, ymax + 0.07 * yr)

    layer_queue = []
    with contextlib.suppress(Exception):
        if hasattr(controller, "_preview_render_layers"):
            layer_queue = controller._preview_render_layers(visible_only=True)
        else:
            layer_queue = controller._preview_sorted_layers(visible_only=True)
    if not layer_queue:
        layer_queue = []

    for layer in layer_queue:
        layer_type = getattr(layer, "type", "")
        layer_zorder = _layer_artist_zorder(layer)
        if layer_type == "raster" and not getattr(layer, "path", None):
            finite_xy = np.isfinite(x) & np.isfinite(y) & np.isfinite(grid_plot)
            if np.all(np.isfinite(x)) and np.all(np.isfinite(y)):
                im = ax.pcolormesh(
                    x,
                    y,
                    grid_plot,
                    shading="auto",
                    cmap=cmap,
                    vmin=cmin,
                    vmax=cmax,
                    zorder=layer_zorder,
                )
            elif np.any(finite_xy):
                im = ax.scatter(
                    x[finite_xy],
                    y[finite_xy],
                    c=grid_plot[finite_xy],
                    s=9,
                    marker="s",
                    linewidths=0,
                    cmap=cmap,
                    vmin=cmin,
                    vmax=cmax,
                    zorder=layer_zorder,
                )
            if im is not None:
                im._grace_preview_label = _base_raster_label(controller, frame)
        elif layer_type == "raster":
            overlay_im = _draw_imported_raster_layer(
                controller,
                layer,
                idx,
                proj,
                lon0,
                lat0,
                lat1,
                lat2,
                cmap,
                cmin,
                cmax,
                target_time=frame.get("t"),
                target_meta=frame.get("meta", {}),
            )
            if overlay_im is not None:
                im = overlay_im
        elif layer_type == "coastline":
            _draw_coastlines(controller, proj, lon0, lat0, lat1, lat2, zorder=layer_zorder)
        elif layer_type == "graticule":
            _draw_graticule(controller, proj, lon0, lat0, lat1, lat2, zorder=layer_zorder)
        elif layer_type in {"boundary", "shapefile"}:
            _draw_boundary_layer(controller, layer, proj, lon0, lat0, lat1, lat2, _bbox, zorder=layer_zorder)

    if not layer_queue and _show_base_raster(controller):
        finite_xy = np.isfinite(x) & np.isfinite(y) & np.isfinite(grid_plot)
        if np.all(np.isfinite(x)) and np.all(np.isfinite(y)):
            im = ax.pcolormesh(x, y, grid_plot, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
        elif np.any(finite_xy):
            im = ax.scatter(x[finite_xy], y[finite_xy], c=grid_plot[finite_xy], s=9, marker="s", linewidths=0, cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
        if im is not None:
            im._grace_preview_label = _base_raster_label(controller, frame)
        _draw_coastlines(controller, proj, lon0, lat0, lat1, lat2)
        _draw_graticule(controller, proj, lon0, lat0, lat1, lat2)
        _draw_boundary_layers(controller, proj, lon0, lat0, lat1, lat2, _bbox)

    if im is not None and _show_colorbar(controller):
        cbar = controller._figure.colorbar(im, ax=ax, shrink=0.78, pad=0.02)
        cbar.set_label(_raster_artist_label(controller, im, frame), fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    # Larger default map view.  Leave room for a visible color scale only when it is enabled.
    if _show_colorbar(controller):
        ax.set_position([0.035, 0.06, 0.80, 0.86])
        for cax in [item for item in controller._figure.axes if item is not ax]:
            cax.set_position([0.865, 0.18, 0.022, 0.64])
    else:
        ax.set_position([0.035, 0.06, 0.92, 0.86])

    controller._preview_pick_state = {
        "x": np.asarray(x, dtype=float),
        "y": np.asarray(y, dtype=float),
        "lon": np.asarray(lon2d, dtype=float),
        "lat": np.asarray(lat2d, dtype=float),
        "grid": np.asarray(grid_plot, dtype=float),
    }

    pe._update_preview_status(controller, path, idx, frame, grid, (time.perf_counter() - start) * 1000.0)
    _update_visible_raster_status(controller, im)
    restore_preview_header(controller.window)
    controller._canvas.draw_idle()


def _cartopy_crs_module():
    try:
        import cartopy.crs as ccrs

        return ccrs
    except Exception:
        return None


def _build_cartopy_crs(label: str, params: dict):
    ccrs = _cartopy_crs_module()
    if ccrs is None:
        return None
    spec = projection_spec(label)
    class_name = spec.get("crs_class")
    if not class_name:
        return None
    cls = getattr(ccrs, str(class_name), None)
    if cls is None:
        raise RuntimeError(f"Cartopy CRS class is not available: {class_name}")
    kwargs = {}
    for key in spec.get("crs_params", []):
        if key not in params:
            continue
        value = params[key]
        if key == "standard_parallels" and isinstance(value, (list, tuple)):
            value = tuple(float(item) for item in value[:2])
        kwargs[key] = value
    if class_name == "UTM":
        return cls(zone=int(kwargs.get("zone", 49)), southern_hemisphere=bool(kwargs.get("southern_hemisphere", False)))
    try:
        return cls(**kwargs)
    except TypeError:
        allowed = {"central_longitude", "central_latitude", "standard_parallels"}
        return cls(**{key: value for key, value in kwargs.items() if key in allowed})


def _polish_cartopy_frame(ax, label: str) -> None:
    """Avoid a Matplotlib rectangular frame around curved Cartopy projections."""

    key = projection_name_to_key(label)
    if key in _RECTANGULAR_CARTOPY_KEYS:
        return
    for name, spine in ax.spines.items():
        with contextlib.suppress(Exception):
            spine.set_visible(False)
    with contextlib.suppress(Exception):
        ax.set_frame_on(False)
    with contextlib.suppress(Exception):
        ax.patch.set_edgecolor("none")
        ax.patch.set_linewidth(0.0)
    with contextlib.suppress(Exception):
        ax.tick_params(left=False, right=False, bottom=False, top=False)


def _extent_from_page(controller) -> list[float]:
    page = controller.window.page_preview
    return [
        controller._safe_float(page.edit_region_lon_min.text(), -180.0),
        controller._safe_float(page.edit_region_lon_max.text(), 180.0),
        controller._safe_float(page.edit_region_lat_min.text(), -90.0),
        controller._safe_float(page.edit_region_lat_max.text(), 90.0),
    ]


def _extent_lon_span(lon_min: float, lon_max: float) -> float:
    raw_span = float(lon_max) - float(lon_min)
    if raw_span < 0.0:
        raw_span += 360.0
    return abs(raw_span)


def _extent_uses_0360(extent: list[float] | tuple[float, ...]) -> bool:
    lon_min, lon_max = float(extent[0]), float(extent[1])
    return lon_min >= 0.0 and (lon_max > 180.0 or lon_min > lon_max)


def _normalize_extent_lons(extent: list[float] | tuple[float, ...], lon_mode: str) -> tuple[float, float, float, float]:
    lon_min, lon_max, lat_min, lat_max = [float(v) for v in extent]
    lat_min, lat_max = min(lat_min, lat_max), max(lat_min, lat_max)
    if lon_mode == "0_360":
        lon_min = lon_min % 360.0
        lon_max = lon_max % 360.0
        if abs(float(extent[1]) - 360.0) < 1.0e-9:
            lon_max = 360.0
    else:
        lon_min = float(normalize_lon_for_plot([lon_min], lon_mode="-180_180")[0])
        lon_max = float(normalize_lon_for_plot([lon_max], lon_mode="-180_180")[0])
        if abs(float(extent[1]) - 180.0) < 1.0e-9:
            lon_max = 180.0
    return lon_min, lon_max, lat_min, lat_max


def _cartopy_display_extent(extent: list[float] | tuple[float, ...] | None) -> list[float] | None:
    if extent is None:
        return None
    lon_min_raw, lon_max_raw, lat_min, lat_max = [float(v) for v in extent]
    lat_min, lat_max = min(lat_min, lat_max), max(lat_min, lat_max)
    span = _extent_lon_span(lon_min_raw, lon_max_raw)
    if span >= 359.0:
        return [-180.0, 180.0, lat_min, lat_max]

    lon_min = float(normalize_lon_for_plot([lon_min_raw], lon_mode="-180_180")[0])
    lon_max = float(normalize_lon_for_plot([lon_max_raw], lon_mode="-180_180")[0])
    if abs(lon_max_raw - 180.0) < 1.0e-9 or abs(lon_max_raw - 360.0) < 1.0e-9:
        lon_max = 180.0 if lon_min >= 0.0 else 0.0

    # A wrapped interval cannot be represented as one PlateCarree extent.
    # Keep a global frame; the grid itself is still cropped before drawing.
    if lon_min > lon_max:
        return [-180.0, 180.0, lat_min, lat_max]
    return [lon_min, lon_max, lat_min, lat_max]


def _resolve_projection_extent(controller, label: str, params: dict, bbox) -> tuple[list[float] | None, str | None]:
    spec = projection_spec(label)
    has_extent_param = "extent" in spec.get("view_params", [])
    page = controller.window.page_preview
    custom_extent = bool(getattr(page, "chk_auto_region", None) is not None and not page.chk_auto_region.isChecked())
    if has_extent_param and isinstance(params.get("extent"), (list, tuple)) and len(params["extent"]) == 4:
        extent = [float(v) for v in params["extent"]]
    elif bbox is not None:
        extent = [float(v) for v in bbox]
    else:
        extent = _extent_from_page(controller)

    if not custom_extent and not has_extent_param and spec.get("recommended_scope") == "global":
        return None, None

    if not projection_supports_global_extent(label) and is_global_extent(extent):
        default_extent = projection_default_extent(label)
        msg = (
            f"{spec.get('name', label)} is not recommended for global extent; "
            f"using default {default_extent}."
        )
        return default_extent, msg
    return extent, None


def _crop_grid_to_extent(grid, lon, lat, extent):
    if extent is None:
        return grid, lon, lat
    lon_mode = "0_360" if _extent_uses_0360(extent) else "-180_180"
    lon_min, lon_max, lat_min, lat_max = _normalize_extent_lons(extent, lon_mode)
    lon_eval = normalize_lon_for_plot(lon, lon_mode=lon_mode)
    full_lon = _extent_lon_span(float(extent[0]), float(extent[1])) >= 359.0
    if full_lon:
        lon_mask = np.ones_like(lon_eval, dtype=bool)
    elif lon_mode == "0_360" and abs(lon_max - 360.0) < 1.0e-9:
        lon_mask = lon_eval >= lon_min
    elif lon_min <= lon_max:
        lon_mask = (lon_eval >= lon_min) & (lon_eval <= lon_max)
    else:
        lon_mask = (lon_eval >= lon_min) | (lon_eval <= lon_max)
    lat_mask = (lat >= min(lat_min, lat_max)) & (lat <= max(lat_min, lat_max))
    if np.any(lon_mask) and np.any(lat_mask):
        cropped_grid = grid[np.ix_(lon_mask, lat_mask)]
        cropped_lon = normalize_lon_for_plot(lon[lon_mask], lon_mode="-180_180")
        order = np.argsort(cropped_lon)
        return cropped_grid[order, :], cropped_lon[order], lat[lat_mask]
    return grid, lon, lat


def _draw_cartopy_coastlines(controller, ax, data_crs, *, zorder: int) -> None:
    if not _show_coastlines(controller):
        return
    coast_path = ""
    with contextlib.suppress(Exception):
        coast_path = controller._resolve_coastline_path()
    if not coast_path:
        return
    try:
        import os
        shp_path = coast_path
        if os.path.isdir(shp_path):
            for filename in os.listdir(shp_path):
                if filename.lower().endswith(".shp"):
                    shp_path = os.path.join(shp_path, filename)
                    break
        with open_shapefile_reader(shp_path) as reader:
            for shape in reader.shapes():
                pts = np.asarray(shape.points, dtype=float)
                if pts.ndim != 2 or pts.shape[0] < 2:
                    continue
                parts = list(shape.parts) + [len(pts)]
                for i in range(len(parts) - 1):
                    seg = pts[parts[i] : parts[i + 1]]
                    if seg.shape[0] >= 2:
                        ax.plot(seg[:, 0], seg[:, 1], transform=data_crs, color=_COAST_COLOR, linewidth=0.44, alpha=0.92, zorder=zorder)
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Coastline layer failed: {exc}", "stderr")


def _draw_cartopy_graticule(controller, ax, data_crs, *, zorder: int) -> None:
    if not _show_grid(controller):
        return
    try:
        opts = _graticule_options(controller)
        line_visible = opts["linestyle"] not in {"none", "None", ""} and opts["linewidth"] > 0
        gl = ax.gridlines(
            crs=data_crs,
            draw_labels=bool(opts["show_labels"]),
            linewidth=opts["linewidth"] if line_visible else 0.0,
            color=opts["color"],
            alpha=0.76 if line_visible else 0.0,
            linestyle=opts["linestyle"] if line_visible else "-",
            zorder=zorder,
        )
        gl.xlocator = mticker.FixedLocator(np.arange(-180, 180 + 0.1, opts["lon_interval"]))
        gl.ylocator = mticker.FixedLocator(np.arange(-90, 90 + 0.1, opts["lat_interval"]))
        gl.top_labels = False
        gl.right_labels = False
        label_style = {"size": opts["font_size"], "color": "#405766"}
        if opts.get("font_family"):
            label_style["family"] = opts["font_family"]
        gl.xlabel_style = dict(label_style)
        gl.ylabel_style = dict(label_style)
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Graticule layer failed: {exc}", "stderr")


def _draw_cartopy_boundary_layer(controller, ax, data_crs, layer, *, zorder: int) -> None:
    path = str(getattr(layer, "path", "") or "")
    if not path or Path(path).suffix.lower() not in {".shp", ".bln", ".txt"} or not Path(path).exists():
        return
    try:
        boundaries = read_boundary_file(path)
        for boundary in boundaries:
            lons = np.asarray(getattr(boundary, "lon", []), dtype=float)
            lats = np.asarray(getattr(boundary, "lat", []), dtype=float)
            if lons.size >= 2 and lats.size >= 2:
                ax.plot(lons, lats, transform=data_crs, color="#b00020", linewidth=0.8, alpha=0.85, zorder=zorder)
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Boundary layer failed: {path}: {exc}", "stderr")


def _draw_cartopy_imported_raster(
    controller,
    ax,
    data_crs,
    layer,
    idx,
    cmap,
    cmin,
    cmax,
    *,
    target_time=None,
    target_meta: dict | None = None,
):
    page = controller.window.page_preview
    path = str(getattr(layer, "path", "") or "")
    if not path or Path(path).suffix.lower() not in {".nc", ".nc4", ".cdf", ".h5", ".hdf5", ".hdf", ".mat"} or not Path(path).exists():
        return None
    resolved = _resolve_imported_raster_time(
        controller,
        layer,
        idx,
        target_time=target_time,
        target_meta=target_meta,
    )
    if resolved is None:
        return None
    layer_index, meta, time_match = resolved
    try:
        active_var = str(meta.get("active_var") or page.cmb_data_var.currentText().strip() or "").strip() or None
        grid, lon, lat, _t_val, loaded_meta = load_stack_slice_any(
            path,
            time_index=layer_index,
            active_var=active_var,
            selection_meta=meta,
        )
        if grid is None or lon is None or lat is None:
            return None
        merged_meta = dict(meta)
        merged_meta.update(dict(loaded_meta or {}))
        unit = unit_from_metadata(merged_meta, active_var or "") or variable_unit_from_file(path, active_var or "")
        if unit:
            merged_meta["units"] = unit
        grid = np.asarray(grid, dtype=float)
        lon = np.asarray(lon, dtype=float).squeeze()
        lat = np.asarray(lat, dtype=float).squeeze()
        if grid.shape[0] != lon.size and grid.ndim >= 2 and grid.shape[1] == lon.size:
            grid = grid.T
        lon, grid = _normalize_grid_longitudes(lon, grid)
        lon2d, lat2d = np.meshgrid(lon, lat)
        grid_plot = grid.T if grid.shape == (lon.size, lat.size) else np.squeeze(grid)
        zorder = _layer_artist_zorder(layer)
        artist = ax.pcolormesh(
            lon2d,
            lat2d,
            grid_plot,
            transform=data_crs,
            shading="auto",
            cmap=cmap,
            vmin=cmin,
            vmax=cmax,
            alpha=max(0.05, min(1.0, float(getattr(layer, "opacity", 0.72) or 0.72))),
            zorder=zorder,
        )
        return _tag_raster_artist(
            artist,
            var_name=active_var or "value",
            meta=merged_meta,
            match=time_match,
            source_path=path,
            values=grid,
        )
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Raster overlay failed: {path}: {exc}", "stderr")
    return None


def _show_projection_error(controller, message: str) -> None:
    controller._figure.clear()
    ax = controller._figure.add_subplot(111)
    controller._ax = ax
    ax.set_axis_off()
    ax.text(
        0.5,
        0.52,
        "当前投影绘制失败，请检查投影参数或范围设置。",
        ha="center",
        va="center",
        fontsize=12,
        color="#b00020",
        transform=ax.transAxes,
    )
    ax.text(0.5, 0.44, message, ha="center", va="center", fontsize=9, color="#405766", transform=ax.transAxes, wrap=True)
    controller._canvas.draw_idle()


def _render_cartopy_2d(controller) -> None:
    page = controller.window.page_preview
    ccrs = _cartopy_crs_module()
    if ccrs is None:
        with contextlib.suppress(Exception):
            controller.on_log("[PREVIEW] Cartopy is not installed; using legacy 2D projection fallback.", "stderr")
        _render_manual_2d(controller)
        return

    with contextlib.suppress(Exception):
        controller._ensure_preview_layers()
        controller._sync_preview_legacy_layer_controls()
    start = time.perf_counter()
    label = page.cmb_projection.currentText().strip() or "Robinson"
    params = pe._projection_params(page, label)
    spec = projection_spec(label)
    path, idx, frame, grid, lon, lat, bbox = _frame_context(controller)
    extent, warning = _resolve_projection_extent(controller, label, params, bbox)
    if warning:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] {warning}", "stderr")
    should_crop_extent = extent is not None and (
        getattr(page, "chk_auto_region", None) is None
        or not page.chk_auto_region.isChecked()
        or not spec.get("supports_global_extent", True)
    )
    if should_crop_extent:
        grid, lon, lat = _crop_grid_to_extent(grid, lon, lat, extent)
    if lon.size < 2 or lat.size < 2:
        raise RuntimeError("Selected extent does not contain enough grid cells.")

    lon2d, lat2d = np.meshgrid(lon, lat)
    grid_plot = grid.T if grid.shape == (lon.size, lat.size) else grid
    cmin, cmax = _color_limits(page, grid_plot)
    cmap = page.cmb_cmap.currentText().strip() or "RdBu_r"

    target_crs = _build_cartopy_crs(label, params)
    if target_crs is None:
        raise RuntimeError(f"Unsupported projection renderer: {label}")
    data_crs = ccrs.PlateCarree()

    controller._figure.clear()
    ax = controller._figure.add_subplot(111, projection=target_crs)
    controller._ax = ax
    _polish_cartopy_frame(ax, label)
    im = None
    layer_queue = []
    with contextlib.suppress(Exception):
        if hasattr(controller, "_preview_render_layers"):
            layer_queue = controller._preview_render_layers(visible_only=True)
        else:
            layer_queue = controller._preview_sorted_layers(visible_only=True)

    for layer in layer_queue:
        layer_type = getattr(layer, "type", "")
        zorder = _layer_artist_zorder(layer)
        if layer_type == "raster" and not getattr(layer, "path", None):
            im = ax.pcolormesh(lon2d, lat2d, grid_plot, transform=data_crs, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax, zorder=zorder)
            im._grace_preview_label = _base_raster_label(controller, frame)
        elif layer_type == "raster":
            overlay_im = _draw_cartopy_imported_raster(
                controller,
                ax,
                data_crs,
                layer,
                idx,
                cmap,
                cmin,
                cmax,
                target_time=frame.get("t"),
                target_meta=frame.get("meta", {}),
            )
            if overlay_im is not None:
                im = overlay_im
        elif layer_type == "coastline":
            _draw_cartopy_coastlines(controller, ax, data_crs, zorder=zorder)
        elif layer_type == "graticule":
            _draw_cartopy_graticule(controller, ax, data_crs, zorder=zorder)
        elif layer_type in {"boundary", "shapefile"}:
            _draw_cartopy_boundary_layer(controller, ax, data_crs, layer, zorder=zorder)

    if not layer_queue and _show_base_raster(controller):
        im = ax.pcolormesh(lon2d, lat2d, grid_plot, transform=data_crs, shading="auto", cmap=cmap, vmin=cmin, vmax=cmax, zorder=2)
        im._grace_preview_label = _base_raster_label(controller, frame)
        _draw_cartopy_coastlines(controller, ax, data_crs, zorder=20)
        _draw_cartopy_graticule(controller, ax, data_crs, zorder=30)

    try:
        display_extent = _cartopy_display_extent(extent)
        if display_extent is None:
            ax.set_global()
        else:
            ax.set_extent(display_extent, crs=data_crs)
    except Exception as exc:
        with contextlib.suppress(Exception):
            controller.on_log(f"[PREVIEW] Extent failed for {label}: {extent}: {exc}", "stderr")

    if im is not None and _show_colorbar(controller):
        cbar = controller._figure.colorbar(im, ax=ax, shrink=0.78, pad=0.02)
        cbar.set_label(_raster_artist_label(controller, im, frame), fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    ax.set_title("")
    _polish_cartopy_frame(ax, label)
    if _show_colorbar(controller):
        ax.set_position([0.035, 0.06, 0.80, 0.86])
        for cax in [item for item in controller._figure.axes if item is not ax]:
            cax.set_position([0.865, 0.18, 0.022, 0.64])
    else:
        ax.set_position([0.035, 0.06, 0.92, 0.86])

    pick_x = np.asarray(lon2d, dtype=float)
    pick_y = np.asarray(lat2d, dtype=float)
    with contextlib.suppress(Exception):
        points = target_crs.transform_points(data_crs, pick_x, pick_y)
        if points is not None and points.shape[-1] >= 2:
            pick_x = points[..., 0]
            pick_y = points[..., 1]

    controller._preview_pick_state = {
        "x": np.asarray(pick_x, dtype=float),
        "y": np.asarray(pick_y, dtype=float),
        "lon": np.asarray(lon2d, dtype=float),
        "lat": np.asarray(lat2d, dtype=float),
        "grid": np.asarray(grid_plot, dtype=float),
    }
    pe._update_preview_status(controller, path, idx, frame, grid, (time.perf_counter() - start) * 1000.0)
    _update_visible_raster_status(controller, im)
    restore_preview_header(controller.window)
    with contextlib.suppress(Exception):
        controller._sync_preview_toolbar_mode()
    controller._canvas.draw_idle()


def _render_normalized_2d(controller) -> None:
    _render_cartopy_2d(controller)


def install_preview_stable_rendering(window) -> None:
    """Install the final rendering hook after all preview UI polish hooks."""

    if getattr(window, "_preview_stable_rendering_installed", False):
        return
    controller = window.controller
    page = window.page_preview
    previous_render = controller.on_render_preview

    def render(self):
        if _is_3d_label(page):
            result = pe._render_3d_globe(self)
            restore_preview_header(window)
            return result
        try:
            if not pe._handle_cpt_combo(self):
                return None
            _render_normalized_2d(self)
            return None
        except Exception as exc:
            label = page.cmb_projection.currentText().strip() or "Robinson"
            params = {}
            extent = None
            with contextlib.suppress(Exception):
                params = pe._projection_params(page, label)
                extent = params.get("extent") or _extent_from_page(self)
            projection_key = projection_name_to_key(label)
            with contextlib.suppress(Exception):
                self.on_log(
                    f"[PREVIEW] Projection render failed: key={projection_key}; params={params}; extent={extent}; error={exc}",
                    "stderr",
                )
            _show_projection_error(self, str(exc))
            self._show_error("Preview", f"当前投影绘制失败，请检查投影参数或范围设置。\n\n{exc}")
            return None

    controller.on_render_preview = MethodType(render, controller)
    _safe_disconnect(page.btn_plot.clicked)
    page.btn_plot.clicked.connect(controller.on_render_preview)
    for signal in (
        getattr(page, "chk_show_graticule", None),
        getattr(page, "chk_show_colorbar", None),
        getattr(page, "chk_layer_coastlines", None),
        getattr(page, "chk_layer_grid", None),
    ):
        if signal is not None:
            with contextlib.suppress(Exception):
                signal.toggled.connect(lambda *_args, _controller=controller: _controller.on_render_preview())
    with contextlib.suppress(Exception):
        controller._preview_unit_motion_cid = controller._canvas.mpl_connect(
            "motion_notify_event",
            lambda _event, _controller=controller: _append_preview_value_unit(_controller),
        )
        controller._preview_unit_click_cid = controller._canvas.mpl_connect(
            "button_press_event",
            lambda _event, _controller=controller: _append_preview_value_unit(_controller),
        )
    window._preview_stable_rendering_installed = True
