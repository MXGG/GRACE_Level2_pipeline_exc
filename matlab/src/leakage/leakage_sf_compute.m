function SF = leakage_sf_compute(cfg, methodTag, mask, lonVec, latVec)
%LEAKAGE_SF_COMPUTE Compute static scale factor for a basin mask.
%
% Default mode: synthetic unit field (unit_mm) passed through same filter operator.

    L = leakage_merge_cfg(cfg);
    unit_mm = L.SF.unit_mm;

    Gunit = leakage_build_unit_field(mask, unit_mm, L.mass_conservation);
    Gf = leakage_apply_forward_operator(Gunit, lonVec, latVec, methodTag, cfg, L);

    mu = leakage_basin_mean(Gf, mask);
    SF = unit_mm / mu;
end
