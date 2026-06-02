function L = leakage_default_cfg()
%LEAKAGE_DEFAULT_CFG Default leakage configuration (used if cfg.leakage missing fields).
    L = struct();

    L.method = 'SF';                 % 'SF' or 'FM'
    L.ref_tag = '';                  % reference product tag to correct (e.g., 'P4M6_Gaussian')
    L.Lmax = 60;                     % SH truncation degree
    L.grid_interval = 1;             % deg grid for gmt_cs2grid
    L.mass_conservation = 'none';    % 'none' | 'global_zero_mean'

    % SF options
    L.SF = struct();
    L.SF.mode = 'synthetic';         % 'synthetic' | 'model' (model mode requires model stack/ts)
    L.SF.unit_mm = 10;               % synthetic unit field amplitude (mm)
    L.SF.regression = 'origin';      % 'origin' or 'ratio_mean' (model mode)

    % FM options
    L.FM = struct();
    L.FM.nIter = 30;
    L.FM.tol_rmse_mm = 1e-3;         % stop if RMSE(residual in mask) < tol
    L.FM.update_mode = 'mask';       % 'mask' or 'global'
    L.FM.init_mode = 'obs';          % 'obs' or 'zeros'
end
