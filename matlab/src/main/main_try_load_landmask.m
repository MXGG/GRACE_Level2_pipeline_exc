function landMask = main_try_load_landmask(cfg, lonVec, latVec)
%MAIN_TRY_LOAD_LANDMASK Load land mask if available (optional).

    landMask = [];

    if isfield(cfg,'path') && isfield(cfg.path,'AUX')
        candidates = {
            fullfile(cfg.path.AUX, 'land_mask.mat')
            fullfile(cfg.path.AUX, 'landmask.mat')
            fullfile(cfg.path.AUX, 'coast_mask.mat')
        };
        for i = 1:numel(candidates)
            fp = candidates{i};
            if isfile(fp)
                S = load(fp);
                fn = fieldnames(S);
                X = S.(fn{1});
                landMask = X;
                return;
            end
        end
    end

    % Fallback: if tools provide global coast mask builder, user may supply globalgrid
    % We keep landMask empty by default.
end
