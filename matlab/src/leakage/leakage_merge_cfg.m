function L = leakage_merge_cfg(cfg)
%LEAKAGE_MERGE_CFG Merge cfg.leakage into defaults.
    L = leakage_default_cfg();
    if ~isfield(cfg,'leakage') || isempty(cfg.leakage)
        return;
    end
    U = cfg.leakage;
    L = merge_struct(L, U);

    % nested merge
    if isfield(U,'SF'); L.SF = merge_struct(L.SF, U.SF); end
    if isfield(U,'FM'); L.FM = merge_struct(L.FM, U.FM); end
end

function A = merge_struct(A, B)
    if isempty(B); return; end
    fn = fieldnames(B);
    for i = 1:numel(fn)
        A.(fn{i}) = B.(fn{i});
    end
end
