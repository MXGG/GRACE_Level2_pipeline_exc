"""UI tab builders."""

from grace_pipeline.ui.tabs.basin import build_basin_tab
from grace_pipeline.ui.tabs.common import build_common_tab
from grace_pipeline.ui.tabs.filters import build_filters_tab
from grace_pipeline.ui.tabs.leakage import build_leakage_tab
from grace_pipeline.ui.tabs.plot import build_plot_tab

__all__ = [
    "build_common_tab",
    "build_basin_tab",
    "build_leakage_tab",
    "build_filters_tab",
    "build_plot_tab",
]
