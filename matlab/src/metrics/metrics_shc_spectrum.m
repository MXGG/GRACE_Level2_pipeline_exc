function OUT = metrics_shc_spectrum(EWH, Lmax)
%METRICS_SHC_SPECTRUM Convert grid EWH (mm, lon x lat) to SC spectrum via gmt toolbox (optional).
% Requires: gmt_grid2cs, gmt_mc2gc, gmt_cs2sc.

    need = {'gmt_grid2cs','gmt_mc2gc','gmt_cs2sc'};
    for i = 1:numel(need)
        if exist(need{i},'file') ~= 2
            error('Missing dependency: %s (from GRACE gmt toolbox).', need{i});
        end
    end
    if nargin < 2 || isempty(Lmax); Lmax = 60; end

    is3 = ndims(EWH) == 3;
    Nt = 1;
    if is3; Nt = size(EWH,3); end

    SC = nan(Lmax+1, 2*Lmax+1, Nt);

    for t = 1:Nt
        if is3
            G = EWH(:,:,t);
        else
            G = EWH;
        end
        cs = gmt_grid2cs(G' / 1000, Lmax); % mm -> m ; transpose to toolbox convention
        gc = gmt_mc2gc(cs);
        sc = gmt_cs2sc(gc);
        SC(:,:,t) = sc;
    end

    OUT = struct('Lmax',Lmax,'SC',SC);
end
