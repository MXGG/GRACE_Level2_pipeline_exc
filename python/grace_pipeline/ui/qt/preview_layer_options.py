"""Place preview display switches inside the Layer Stack card."""

from __future__ import annotations

import contextlib

from grace_pipeline.ui.qt.preview_view_polish import _ensure_display_option_controls


def install_preview_layer_options(window) -> None:
    """Move coordinate-grid and color-scale switches into the layer card.

    The controls are created by preview_view_polish so they can drive rendering
    state.  This installer only changes their visual placement: they belong in
    the layer stack together with coastline, boundary and custom overlay toggles.
    """

    page = window.page_preview
    _ensure_display_option_controls(window)
    if hasattr(page, "table_overlay_layers"):
        return
    row = getattr(page, "preview_display_options_row", None)
    card = getattr(page, "card_layers", None)
    if row is None or card is None:
        return

    with contextlib.suppress(Exception):
        card.setVisible(True)

    body = getattr(card, "body", None)
    if body is None:
        return

    insert_at = body.count()
    with contextlib.suppress(Exception):
        grid_index = body.indexOf(page.chk_layer_grid)
        if grid_index >= 0:
            insert_at = grid_index + 1
    with contextlib.suppress(Exception):
        body.insertWidget(insert_at, row)
