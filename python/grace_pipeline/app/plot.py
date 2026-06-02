"""Plot service extracted from GUI layer."""

import numpy as np
import tkinter as tk
from tkinter import messagebox
def _plot_stack(self, region=False):
    if not self._ensure_plot_panel():
        raise RuntimeError("Plot panel not initialized.")
    try:
        # Reset projection scaling each plot
        self._proj_scale = None
        self._proj_x0 = None
        data = self._get_stack_data()
        ewh = data['ewh']
        lon = np.asarray(data['lon']).astype(float).squeeze()
        lat = np.asarray(data['lat']).astype(float).squeeze()
        idx = int(self.var_time_idx.get())
        if idx < 0 or idx >= ewh.shape[2]:
            raise ValueError(f"Index out of range (0..{ewh.shape[2]-1}).")
        grid = ewh[:, :, idx]

        # Ensure grid is [nLon x nLat]
        if grid.shape[0] != lon.size and grid.shape[1] == lon.size:
            grid = grid.T

        proj = self.var_proj.get() if hasattr(self, "var_proj") else "PlateCarree"
        lon_mode = self._infer_plot_lon_mode(lon)
        self._plot_lon_mode = lon_mode

        # Optional boundary overlay / auto region
        boundary_path = ""
        boundaries = []
        boundary_bbox = None
        try:
            if hasattr(self, "var_plot_boundary"):
                boundary_path = self.var_plot_boundary.get().strip()
        except Exception:
            boundary_path = ""
        if boundary_path:
            try:
                boundaries = self._read_boundary_file(boundary_path)
                boundary_bbox = self._boundary_bbox(boundaries)
            except Exception:
                boundaries = []
                boundary_bbox = None

        # Region crop
        apply_region = region or self._region_is_custom()
        try:
            if (not apply_region) and boundary_bbox and (bool(self.var_plot_auto_region.get()) if hasattr(self, "var_plot_auto_region") else True):
                apply_region = True
        except Exception:
            pass
        if apply_region:
            if boundary_bbox and (bool(self.var_plot_auto_region.get()) if hasattr(self, "var_plot_auto_region") else True):
                lon_min, lon_max, lat_min, lat_max = boundary_bbox
            else:
                lon_min = float(self.var_r_lon_min.get())
                lon_max = float(self.var_r_lon_max.get())
                lat_min = float(self.var_r_lat_min.get())
                lat_max = float(self.var_r_lat_max.get())
            if lat_min > lat_max:
                lat_min, lat_max = lat_max, lat_min

            # Detect full-range selection
            span = lon_max - lon_min
            full_lon = (
                abs(span) >= 359.0
                or (abs(lon_min) < 1e-6 and abs(lon_max - 360.0) < 1e-6)
                or (abs(lon_min + 180.0) < 1e-6 and abs(lon_max - 180.0) < 1e-6)
            )

            if full_lon:
                lon_mask = np.ones_like(lon, dtype=bool)
            else:
                if lon_mode == "0_360":
                    lon_min_w = lon_min % 360.0
                    lon_max_w = lon_max % 360.0
                else:
                    lon_min_w = self._normalize_lon_input(lon_min)
                    lon_max_w = self._normalize_lon_input(lon_max)
                if lon_min_w <= lon_max_w:
                    lon_mask = (lon >= lon_min_w) & (lon <= lon_max_w)
                else:
                    # Wrap across dateline
                    lon_mask = (lon >= lon_min_w) | (lon <= lon_max_w)

            lat_mask = (lat >= lat_min) & (lat <= lat_max)
            grid = grid[np.ix_(lon_mask, lat_mask)]
            lon = lon[lon_mask]
            lat = lat[lat_mask]

        # Keep file-provided longitude values, but ensure the axis is left-to-right.
        if lon.ndim == 1 and lon.size > 1:
            lon_diff = np.diff(lon)
            if np.all(np.isfinite(lon_diff)) and np.all(lon_diff < 0):
                lon = lon[::-1]
                if grid.ndim >= 2 and grid.shape[0] == lon.size:
                    grid = grid[::-1, :]
            # Drop duplicated wrap endpoint (e.g. both 0 and 360) to avoid seam artifacts.
            try:
                first = float(lon[0])
                last = float(lon[-1])
                same_meridian = abs(((last - first + 180.0) % 360.0) - 180.0) <= 1e-6
                if same_meridian and grid.ndim >= 2 and grid.shape[0] == lon.size and lon.size > 2:
                    lon = lon[:-1]
                    grid = grid[:-1, :]
            except Exception:
                pass

        # Align grid to [lat x lon] for plotting
        try:
            nlon = lon.size if hasattr(lon, "size") else len(lon)
            nlat = lat.size if hasattr(lat, "size") else len(lat)
        except Exception:
            nlon = grid.shape[0]
            nlat = grid.shape[1] if grid.ndim > 1 else 0
        if grid.ndim == 2:
            if grid.shape == (nlon, nlat):
                grid_plot = grid.T
            elif grid.shape == (nlat, nlon):
                grid_plot = grid
            else:
                grid_plot = grid
        else:
            grid_plot = grid

        # Ensure latitude ascending for plotting
        if lat.ndim == 1 and lat.size > 1:
            lat_order = np.argsort(lat)
            if not np.all(lat_order == np.arange(lat.size)):
                lat = lat[lat_order]
                if grid.shape[1] == lat_order.size:
                    grid = grid[:, lat_order]
                if grid_plot.shape[0] == lat_order.size:
                    grid_plot = grid_plot[lat_order, :]

        # Region bbox for coastlines/graticule
        bbox = None
        if apply_region:
            try:
                bbox = (float(np.nanmin(lon)), float(np.nanmax(lon)), float(np.nanmin(lat)), float(np.nanmax(lat)))
            except Exception:
                bbox = None

        # Projection center/params
        if apply_region:
            lon0, lat0 = self._get_proj_center(lon, lat)
        else:
            lon0 = 180.0 if lon_mode == "0_360" else 0.0
            lat0 = 0.0
        try:
            lat_min = float(np.nanmin(lat))
            lat_max = float(np.nanmax(lat))
        except Exception:
            lat_min, lat_max = -60.0, 60.0
        lat1, lat2 = self._get_conic_parallels(lat_min, lat_max)

        # For projected maps, reorder by wrapped longitude around center
        if proj not in ("PlateCarree", "Equirectangular"):
            lon_proj = self._wrap_delta_lon(lon, lon0)
            order = np.argsort(lon_proj)
            lon = lon[order]
            if grid.shape[0] == order.size:
                grid = grid[order, :]
            if grid_plot.shape[1] == order.size:
                grid_plot = grid_plot[:, order]

        # Use embedded plot panel
        if not hasattr(self, "plot_fig") or self.plot_fig is None:
            raise RuntimeError("Plot panel not initialized.")
        # Recreate axes with fixed layout to avoid shrinking across redraws
        self.plot_fig.clear()
        if proj in ("PlateCarree", "Equirectangular"):
            axes_rect = [0.08, 0.08, 0.74, 0.84]
            cax_rect = [0.84, 0.16, 0.02, 0.68]
        else:
            axes_rect = [0.06, 0.06, 0.78, 0.88]
            cax_rect = [0.86, 0.14, 0.02, 0.72]
        self.plot_ax = self.plot_fig.add_axes(axes_rect)
        cax = self.plot_fig.add_axes(cax_rect)
        from matplotlib import colors

        cmap = self.var_cmap.get() if hasattr(self, "var_cmap") else "RdBu_r"
        # Color scaling (optional fixed range)
        cmin = self._parse_float(self.var_cmin.get()) if hasattr(self, "var_cmin") else None
        cmax = self._parse_float(self.var_cmax.get()) if hasattr(self, "var_cmax") else None
        if cmin is None and cmax is None:
            finite = np.isfinite(grid_plot)
            if finite.any():
                vmax = float(np.nanmax(np.abs(grid_plot[finite])))
                vmax = vmax if vmax > 0 else 1.0
            else:
                vmax = 1.0
            norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
        else:
            if cmin is None:
                cmin = -abs(float(cmax)) if cmax is not None else -1.0
            if cmax is None:
                cmax = abs(float(cmin)) if cmin is not None else 1.0
            if cmin == cmax:
                cmax = cmin + 1.0
            if cmin < 0 < cmax:
                norm = colors.TwoSlopeNorm(vmin=cmin, vcenter=0.0, vmax=cmax)
            else:
                norm = colors.Normalize(vmin=cmin, vmax=cmax)

        if lon.ndim == 1 and lat.ndim == 1:
            lon2d, lat2d = np.meshgrid(lon, lat)
        else:
            lon2d, lat2d = lon, lat

        target_ratio = self._get_axes_ratio()

        with np.errstate(invalid="ignore", divide="ignore"):
            if proj == "Robinson":
                x, y = self._proj_robinson(lon2d, lat2d, lon0=lon0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="Robinson", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="Robinson", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                # Tight limits to reduce blank space
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "Mollweide":
                x, y = self._proj_mollweide(lon2d, lat2d, lon0=lon0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="Mollweide", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="Mollweide", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "EqualEarth":
                x, y = self._proj_equalearth(lon2d, lat2d, lon0=lon0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="EqualEarth", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="EqualEarth", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "WinkelTripel":
                x, y = self._proj_winkeltripel(lon2d, lat2d, lon0=lon0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="WinkelTripel", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="WinkelTripel", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "EckertIV":
                x, y = self._proj_eckert4(lon2d, lat2d, lon0=lon0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="EckertIV", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="EckertIV", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "Miller":
                x, y = self._proj_miller(lon2d, lat2d, lon0=lon0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="Miller", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="Miller", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "Mercator":
                x, y = self._proj_mercator(lon2d, lat2d, lon0=lon0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="Mercator", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="Mercator", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "Sinusoidal":
                x, y = self._proj_sinusoidal(lon2d, lat2d, lon0=lon0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="Sinusoidal", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="Sinusoidal", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "Orthographic":
                x, y = self._proj_orthographic(lon2d, lat2d, lon0=lon0, lat0=lat0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="Orthographic", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="Orthographic", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "AzimuthalEquidistant":
                x, y = self._proj_aeqd(lon2d, lat2d, lon0=lon0, lat0=lat0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="AzimuthalEquidistant", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="AzimuthalEquidistant", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "Stereographic":
                x, y = self._proj_stereographic(lon2d, lat2d, lon0=lon0, lat0=lat0)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="Stereographic", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="Stereographic", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "LambertConformal":
                x, y = self._proj_lambert_conformal(lon2d, lat2d, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="LambertConformal", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="LambertConformal", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            elif proj == "AlbersEqualArea":
                x, y = self._proj_albers(lon2d, lat2d, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                if not np.isfinite(x).any():
                    raise ValueError("Projection produced no valid points.")
                x, y = self._scale_projection(x, y, target_ratio=target_ratio)
                im = self._pcolor_proj(self.plot_ax, x, y, grid_plot, cmap, norm)
                self.plot_ax.set_axis_off()
                self.plot_ax.set_aspect('equal', adjustable='box')
                self._draw_coastlines(self.plot_ax, proj="AlbersEqualArea", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
                self._draw_graticule(self.plot_ax, proj="AlbersEqualArea", lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2)
                self.plot_ax.set_xlim(np.nanmin(x), np.nanmax(x))
                self.plot_ax.set_ylim(np.nanmin(y), np.nanmax(y))
            else:
                im = self.plot_ax.pcolormesh(lon2d, lat2d, grid_plot, shading='auto', cmap=cmap, norm=norm, edgecolors='none', linewidth=0, antialiased=False)
                self.plot_ax.set_xlabel("Longitude")
                self.plot_ax.set_ylabel("Latitude")
                self.plot_ax.set_aspect('equal', adjustable='box')
                self.plot_ax.tick_params(axis='both', labelsize=8, pad=2)
                if apply_region:
                    self.plot_ax.set_xlim(lon.min(), lon.max())
                    self.plot_ax.set_ylim(lat.min(), lat.max())
                self._draw_graticule(self.plot_ax, proj="PlateCarree", lon0=0.0, lat0=lat0, lat1=lat1, lat2=lat2)
                self._draw_coastlines(self.plot_ax, proj="PlateCarree", lon0=0.0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)

        # Boundary overlay
        try:
            if boundaries:
                self._draw_boundaries(self.plot_ax, boundaries, proj=proj, lon0=lon0, lat0=lat0, lat1=lat1, lat2=lat2, bbox=bbox)
        except Exception:
            pass

        # Colorbar
        self._cbar = self.plot_fig.colorbar(im, cax=cax)
        self.plot_ax.set_title(f"Stack slice {idx}")
        self.plot_canvas.draw_idle()
    except Exception as e:
        messagebox.showerror("Plot", f"Plot failed: {e}")


