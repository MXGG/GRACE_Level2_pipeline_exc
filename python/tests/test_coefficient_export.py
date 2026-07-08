from pathlib import Path

import numpy as np
import pytest

from grace_pipeline.core.config import CoefficientExportConfig
from grace_pipeline.io.coefficients import FilteredMonthlyProduct, export_monthly_coefficients


def _product_with_cs() -> FilteredMonthlyProduct:
    c = np.zeros((3, 3), dtype=float)
    s = np.zeros((3, 3), dtype=float)
    c[2, 0] = -4.84e-4
    c[2, 1] = 1.0e-10
    s[2, 1] = -2.0e-10
    return FilteredMonthlyProduct(
        year_month="2002-04",
        center="CSR",
        release="RL06",
        method="GAUSS",
        source_domain="spherical_harmonic",
        cs_available=True,
        clm=c,
        slm=s,
        grid_available=False,
        grid=None,
        grid_unit="mmEWH",
        lon=None,
        lat=None,
        max_degree=2,
        metadata={"baseline": "2004-01_to_2009-12"},
    )


def test_icgem_gfc_export_writes_header_and_triangle(tmp_path: Path):
    config = CoefficientExportConfig(enabled=True, max_degree=2)
    manifest = export_monthly_coefficients(_product_with_cs(), config, tmp_path)

    assert manifest is not None
    out = Path(manifest["gfc_file"])
    text = out.read_text(encoding="utf-8")
    assert "begin_of_head" in text
    assert "product_type gravity_field" in text
    assert "errors no" in text
    assert "norm fully_normalized" in text
    assert "# coefficient_content anomaly" in text
    assert "# source_domain spherical_harmonic" in text
    assert "gfc     2     2" in text
    assert "gfc     1     2" not in text


def test_full_export_requires_reference(tmp_path: Path):
    config = CoefficientExportConfig(enabled=True, coefficient_content="full", max_degree=2)
    with pytest.raises(ValueError, match="requires reference coefficients"):
        export_monthly_coefficients(_product_with_cs(), config, tmp_path)


def test_grid_export_rejects_regional_grid(tmp_path: Path):
    config = CoefficientExportConfig(enabled=True, max_degree=2)
    product = FilteredMonthlyProduct(
        year_month="2002-04",
        center="CSR",
        release="RL06",
        method="HSAF",
        source_domain="grid",
        cs_available=False,
        clm=None,
        slm=None,
        grid_available=True,
        grid=np.zeros((4, 4), dtype=float),
        grid_unit="mmEWH",
        lon=np.array([100.0, 101.0, 102.0, 103.0]),
        lat=np.array([20.0, 21.0, 22.0, 23.0]),
        max_degree=2,
        metadata={},
    )
    with pytest.raises(ValueError, match="regional grid"):
        export_monthly_coefficients(product, config, tmp_path)
