function ProductRAW = inv_invert_month(cfg, Tk, meanSH, syn)
%INV_INVERT_MONTH Read monthly GSM, apply low-degree replacement, remove mean (optional),
% and synthesize raw EWH grid (no spatial filtering).
%
% Inputs:
%   meanSH: struct (single mean or mission-segmented mean)
%   syn: precomputed synthesis basis (from inv_prepare_synthesis)
%
% Output:
%   ProductRAW: struct with fields tag/time/grid/meta

    SH = inv_read_gsm_month(cfg, Tk);
    SH = inv_replace_low_degree(cfg, SH, Tk);

    if isfield(cfg.inversion,'remove_mean') && cfg.inversion.remove_mean
        if nargin < 3 || isempty(meanSH)
            error('remove_mean=true but meanSH not provided. Call inv_get_mean_sh first.');
        end
        [Cmean, Smean, meanTag] = inv_select_mean_sh(meanSH, Tk, cfg);
        if isempty(Cmean) || isempty(Smean)
            error('remove_mean=true but no suitable mean field found for %s.', Tk.ym);
        end
        SH.C = SH.C - Cmean;
        SH.S = SH.S - Smean;
        SH.meta.removed_mean = true;
        SH.meta.removed_mean_tag = meanTag;
    else
        SH.meta.removed_mean = false;
        SH.meta.removed_mean_tag = '';
    end

    ewh = inv_synthesize_ewh_fast(SH, syn);

    ProductRAW = struct();
    ProductRAW.tag = 'RAW';
    ProductRAW.time = Tk;
    ProductRAW.grid = struct('lat', syn.latVec, 'lon', syn.lonVec, 'ewh', ewh);
    ProductRAW.meta = SH.meta;
    ProductRAW.metrics = struct();
end
