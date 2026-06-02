"""Basin analysis service extracted from GUI layer."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import tkinter as tk


def run_basin_analysis(self):
    if not bool(self.var_basin_enable.get()):
        self._msg_warn("Basin", "Basin analysis is disabled.")
        return
    self._append_log("[BASIN] Starting basin analysis...")
    try:
        data = self._get_basin_data()
        grid3d = np.asarray(data["ewh"])
        lon_vec = np.asarray(data["lon"]).squeeze()
        lat_vec = np.asarray(data["lat"]).squeeze()
        t_arr = data.get("t", None)
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        if grid3d.ndim == 2:
            grid3d = grid3d[:, :, None]
        nlon, nlat, nt = grid3d.shape
        self._append_log(f"[BASIN] Input grid: {nlon} x {nlat} x {nt}")
    except Exception as e:
        self._append_log(f"[BASIN][ERROR] Failed to load basin data: {e}", tag="stderr")
        self._msg_error("Basin", f"Failed to load basin data: {e}")
        return

    try:
        from grace_pipeline.domain.basin import read_boundary, make_mask, extract_basin_ts, fit_seasonal_trend
    except Exception as e:
        self._msg_error("Basin", f"Missing basin utilities: {e}")
        return

    bfile = self.var_basin_file.get().strip()
    if not bfile:
        self._msg_warn("Basin", "Please select a boundary file.")
        return
    try:
        basins = read_boundary(bfile, name_field=self.var_basin_name_field.get().strip() or "Name")
        target_names = []
        if hasattr(self, "var_basin_names"):
            raw_names = self.var_basin_names.get()
            if isinstance(raw_names, (list, tuple, set)):
                target_names = [str(name).strip() for name in raw_names if str(name).strip()]
        target_name = self.var_basin_name.get().strip()
        if not target_names and target_name:
            target_names = [name.strip() for name in target_name.split(",") if name.strip()]
        if target_names:
            target_lut = {name.lower() for name in target_names}
            basins = [b for b in basins if str(b.name).strip().lower() in target_lut]
    except Exception as e:
        self._append_log(f"[BASIN][ERROR] Failed to read boundary: {e}", tag="stderr")
        self._msg_error("Basin", f"Failed to read boundary: {e}")
        return
    if not basins:
        self._append_log("[BASIN][WARN] No basins found in boundary file.", tag="stderr")
        self._msg_warn("Basin", "No basins found in boundary file.")
        return
    self._append_log(f"[BASIN] Loaded {len(basins)} basin(s) from boundary.")

    t_years, t_labels = self._resolve_time(t_arr, nt, meta=meta)
    out_dir = self.var_basin_out_dir.get().strip()
    if not out_dir:
        out_dir = str(Path(self.cfg.path.OUTPUT) / "basin")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    prefix = self.var_basin_prefix.get().strip() or "basin"
    tag = self.var_basin_tag.get().strip() or "DATA"

    do_ts = bool(self.var_basin_do_ts.get())
    do_stats = bool(self.var_basin_do_stats.get())
    do_grid = bool(self.var_basin_do_grid.get())
    mean_grid_all = np.nanmean(grid3d, axis=2) if do_grid else None

    save_ts_txt = bool(self.var_basin_save_ts_txt.get())
    save_ts_mat = bool(self.var_basin_save_ts_mat.get())
    save_grid_txt = bool(self.var_basin_save_grid_txt.get())
    save_grid_mat = bool(self.var_basin_save_grid_mat.get())

    n_basins = max(1, len(basins))
    sig_payload = {
        "data": self._file_fingerprint(self.var_basin_data.get().strip() if hasattr(self, "var_basin_data") else ""),
        "boundary": self._file_fingerprint(bfile),
        "out_dir": out_dir,
        "prefix": prefix,
        "tag": tag,
        "do_ts": do_ts,
        "do_stats": do_stats,
        "do_grid": do_grid,
        "save_ts_txt": save_ts_txt,
        "save_ts_mat": save_ts_mat,
        "save_grid_txt": save_grid_txt,
        "save_grid_mat": save_grid_mat,
        "target_name": self.var_basin_name.get().strip() if hasattr(self, "var_basin_name") else "",
        "target_names": target_names,
        "name_field": self.var_basin_name_field.get().strip() if hasattr(self, "var_basin_name_field") else "",
        "use_file_time": bool(self.var_basin_use_file_time.get()) if hasattr(self, "var_basin_use_file_time") else True,
        "fallback_start": self.var_basin_start.get().strip() if hasattr(self, "var_basin_start") else "",
        "fallback_step": str(self.var_basin_step.get()).strip() if hasattr(self, "var_basin_step") else "",
        "n_basins": n_basins,
        "nt": int(nt),
    }
    sig = self._build_scope_signature("basin", sig_payload)
    start_idx = 1
    cache = self._load_scope_progress("basin", sig)
    if cache:
        try:
            next_idx = int(cache.get("state", {}).get("next_basin_idx", 1))
            if 1 < next_idx <= n_basins:
                start_idx = next_idx
                self._append_log(f"[BASIN] Resuming from cached progress: basin {start_idx}/{n_basins}")
                self._set_scope_progress_pct("basin", ((start_idx - 1) / n_basins) * 100.0)
        except Exception:
            start_idx = 1
    start_pct = ((start_idx - 1) / n_basins) * 100.0
    self._set_scope_progress_pct("basin", start_pct, f"{start_pct:4.1f}%")

    for b_idx, b in enumerate(basins, start=1):
        if b_idx < start_idx:
            continue
        if not self._check_pause_stop():
            self._append_log("[BASIN] Stopped by user.", tag="stderr")
            self._save_scope_progress_throttled(
                "basin",
                sig,
                {"next_basin_idx": b_idx, "n_basins": n_basins},
                force=True,
            )
            return
        b_name = str(getattr(b, "name", f"basin_{b_idx}"))
        base = (b_idx - 1) / n_basins

        def _pct(local_phase: float):
            local_phase = max(0.0, min(1.0, float(local_phase)))
            return (base + local_phase / n_basins) * 100.0

        self._append_log(f"[BASIN] ({b_idx}/{n_basins}) {b_name}: generating mask...")
        self._set_scope_progress_pct("basin", _pct(0.05))
        try:
            mask = make_mask(b, lon_vec, lat_vec)
        except Exception as e:
            self._msg_warn("Basin", f"Mask failed for {b_name}: {e}")
            self._append_log(f"[BASIN][WARN] {b_name}: mask failed: {e}", tag="stderr")
            continue
        try:
            n_cells = int(np.count_nonzero(mask > 0))
        except Exception:
            n_cells = 0
        self._append_log(f"[BASIN] ({b_idx}/{n_basins}) {b_name}: mask cells = {n_cells}")
        if n_cells <= 0:
            self._append_log(f"[BASIN][WARN] ({b_idx}/{n_basins}) {b_name}: empty mask, skipping.", tag="stderr")
            self._set_scope_progress_pct("basin", _pct(1.0))
            continue

        ts = None
        if do_ts or do_stats:
            self._set_scope_progress_pct("basin", _pct(0.2))
            try:
                ts_dict = extract_basin_ts({tag: grid3d}, mask, lon_vec, lat_vec)
                ts = ts_dict.get(tag)
            except Exception:
                ts = None

        if do_ts and ts is not None:
            self._append_log(f"[BASIN] ({b_idx}/{n_basins}) {b_name}: saving time series...")
            self._set_scope_progress_pct("basin", _pct(0.3))
            if save_ts_txt:
                lines = ["time,value"]
                for i in range(nt):
                    label = t_labels[i] if i < len(t_labels) else f"{i:04d}"
                    lines.append(f"{label},{ts[i]:.6f}")
                self._safe_write_text(os.path.join(out_dir, f"{prefix}_{b_name}_ts.txt"), lines)
            if save_ts_mat:
                self._safe_savemat(
                    os.path.join(out_dir, f"{prefix}_{b_name}_ts.mat"),
                    {"time": t_labels, "t_years": t_years, "ts": ts},
                )

        if do_stats and ts is not None:
            self._set_scope_progress_pct("basin", _pct(0.4))
            try:
                stat = fit_seasonal_trend(t_years, ts)
                lines = [
                    "trend,amp_ann,phs_ann,amp_semi,const",
                    f"{stat.get('trend', np.nan):.6f},{stat.get('amp_ann', np.nan):.6f},{stat.get('phs_ann', np.nan):.6f},{stat.get('amp_semi', np.nan):.6f},{stat.get('const', np.nan):.6f}",
                ]
                self._safe_write_text(os.path.join(out_dir, f"{prefix}_{b_name}_stats.txt"), lines)
            except Exception:
                pass

        if do_grid:
            self._append_log(f"[BASIN] ({b_idx}/{n_basins}) {b_name}: computing spatial grids...")
            self._set_scope_progress_pct("basin", _pct(0.45))
            mean_grid = np.asarray(mean_grid_all, dtype=float)
            trend_grid = np.full((nlon, nlat), np.nan, dtype=float)
            amp_grid = np.full((nlon, nlat), np.nan, dtype=float)
            phase_grid = np.full((nlon, nlat), np.nan, dtype=float)
            if do_stats:
                idxs = np.argwhere(mask > 0)
                n_pts = int(idxs.shape[0]) if hasattr(idxs, "shape") else len(idxs)
                stride = max(1, n_pts // 25) if n_pts > 0 else 1
                use_par = False
                n_workers = 1
                try:
                    use_par = bool(getattr(self.cfg.parallel, "enable", False))
                    n_workers = int(getattr(self.cfg.parallel, "n_workers", 1))
                except Exception:
                    use_par = False
                    n_workers = 1

                if use_par and n_workers > 1 and n_pts >= 200:
                    n_workers = max(1, min(n_workers, n_pts))
                    self._append_log(f"[BASIN] ({b_idx}/{n_basins}) {b_name}: parallel stats workers={n_workers}")
                    chunk_size = max(24, n_pts // max(1, n_workers * 8))
                    chunks = [idxs[s:s + chunk_size] for s in range(0, n_pts, chunk_size)]

                    def _chunk_worker(chunk_arr):
                        rows = []
                        done_local = 0
                        for ij in chunk_arr:
                            if not self._check_pause_stop():
                                break
                            i = int(ij[0])
                            j = int(ij[1])
                            done_local += 1
                            series = grid3d[i, j, :]
                            if np.sum(np.isfinite(series)) < 6:
                                continue
                            try:
                                stat = fit_seasonal_trend(t_years, series)
                                rows.append(
                                    (
                                        i,
                                        j,
                                        float(stat.get("trend", np.nan)),
                                        float(stat.get("amp_ann", np.nan)),
                                        float(stat.get("phs_ann", np.nan)),
                                    )
                                )
                            except Exception:
                                continue
                        return rows, done_local

                    done_pts = 0
                    with ThreadPoolExecutor(max_workers=n_workers) as ex:
                        futures = [ex.submit(_chunk_worker, ch.copy()) for ch in chunks]
                        for fut in as_completed(futures):
                            if not self._check_pause_stop():
                                self._append_log("[BASIN] Stopped by user.", tag="stderr")
                                try:
                                    for ff in futures:
                                        ff.cancel()
                                except Exception:
                                    pass
                                return
                            try:
                                rows, done_local = fut.result()
                            except Exception:
                                rows, done_local = [], 0
                            done_pts += int(done_local)
                            for i, j, tr, am, ph in rows:
                                trend_grid[i, j] = tr
                                amp_grid[i, j] = am
                                phase_grid[i, j] = ph
                            local = 0.45 + 0.45 * (min(done_pts, n_pts) / max(1, n_pts))
                            self._set_scope_progress_pct("basin", _pct(local))
                            if done_pts >= n_pts or (done_pts % max(1, stride * 5)) < chunk_size:
                                self._append_log(f"[BASIN] ({b_idx}/{n_basins}) {b_name}: grid stats {min(done_pts, n_pts)}/{n_pts}")
                else:
                    for p_idx, (i, j) in enumerate(idxs, start=1):
                        if not self._check_pause_stop():
                            self._append_log("[BASIN] Stopped by user.", tag="stderr")
                            return
                        series = grid3d[i, j, :]
                        if np.sum(np.isfinite(series)) < 6:
                            continue
                        try:
                            stat = fit_seasonal_trend(t_years, series)
                            trend_grid[i, j] = stat.get("trend", np.nan)
                            amp_grid[i, j] = stat.get("amp_ann", np.nan)
                            phase_grid[i, j] = stat.get("phs_ann", np.nan)
                        except Exception:
                            continue
                        if n_pts > 0:
                            if p_idx == n_pts or (p_idx % stride) == 0:
                                local = 0.45 + 0.45 * (min(p_idx, n_pts) / n_pts)
                                self._set_scope_progress_pct("basin", _pct(local))
                                if p_idx == n_pts or (p_idx % (stride * 5)) == 0:
                                    self._append_log(f"[BASIN] ({b_idx}/{n_basins}) {b_name}: grid stats {min(p_idx, n_pts)}/{n_pts}")

            mean_grid = np.where(mask > 0, mean_grid, np.nan)
            trend_grid = np.where(mask > 0, trend_grid, np.nan)
            amp_grid = np.where(mask > 0, amp_grid, np.nan)
            phase_grid = np.where(mask > 0, phase_grid, np.nan)
            self._set_scope_progress_pct("basin", _pct(0.93))

            if save_grid_mat:
                self._safe_savemat(
                    os.path.join(out_dir, f"{prefix}_{b_name}_grid.mat"),
                    {
                        "lon": lon_vec,
                        "lat": lat_vec,
                        "mean": mean_grid,
                        "trend": trend_grid,
                        "amp_ann": amp_grid,
                        "phase_ann": phase_grid,
                        "mask": mask,
                    },
                )
            if save_grid_txt:
                self._save_grid_txt(os.path.join(out_dir, f"{prefix}_{b_name}_mean.txt"), lon_vec, lat_vec, mean_grid)
                self._save_grid_txt(os.path.join(out_dir, f"{prefix}_{b_name}_trend.txt"), lon_vec, lat_vec, trend_grid)
                self._save_grid_txt(os.path.join(out_dir, f"{prefix}_{b_name}_amp.txt"), lon_vec, lat_vec, amp_grid)
                self._save_grid_txt(os.path.join(out_dir, f"{prefix}_{b_name}_phase.txt"), lon_vec, lat_vec, phase_grid)

        self._set_scope_progress_pct("basin", _pct(1.0))
        self._append_log(f"[BASIN] ({b_idx}/{n_basins}) {b_name}: done.")
        try:
            self._save_scope_progress_throttled(
                "basin",
                sig,
                {"next_basin_idx": b_idx + 1, "n_basins": n_basins},
                min_interval_s=0.5,
                force=(b_idx == n_basins),
            )
        except Exception:
            pass

    self._set_scope_progress_pct("basin", 100.0, "100%")
    self._append_log(f"[BASIN] Completed. Output: {out_dir}")
    self._clear_scope_progress("basin")
    self._msg_info("Basin", f"Basin analysis complete. Output: {out_dir}")
