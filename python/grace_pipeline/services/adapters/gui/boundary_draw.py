"""Compatibility shim for canonical ui.plotting.boundaries."""

from grace_pipeline.ui.plotting.boundaries import boundary_bbox, draw_boundaries, plot_line, read_boundary_file, split_dateline

__all__ = ["plot_line", "split_dateline", "read_boundary_file", "boundary_bbox", "draw_boundaries"]
