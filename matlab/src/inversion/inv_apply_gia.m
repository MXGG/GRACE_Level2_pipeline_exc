function SH = inv_apply_gia(cfg, SH)
%INV_APPLY_GIA Subtract GIA Stokes coefficients from monthly SH.
%
% cfg.inversion.gia fields:
%   enable  : logical
%   file    : path to text file with columns [l m C S]
%   Lmax    : max degree/order to ingest (defaults to cfg.inversion.Lmax)
%
% The file may contain header lines; numeric lines are parsed with sscanf.

    if ~isfield(cfg,'inversion') || ~isfield(cfg.inversion,'gia') || ...
            ~cfg.inversion.gia.enable
        return;
    end

    giaCfg = cfg.inversion.gia;
    giaFile = giaCfg.file;
    if ~isfile(giaFile)
        error('GIA file not found: %s', giaFile);
    end

    Lmax = cfg.inversion.Lmax;
    if isfield(giaCfg,'Lmax') && ~isempty(giaCfg.Lmax)
        Lmax = min(Lmax, giaCfg.Lmax);
    end

    Cgia = zeros(Lmax+1, Lmax+1);
    Sgia = zeros(Lmax+1, Lmax+1);

    fid = fopen(giaFile,'r');
    if fid < 0
        error('Cannot open GIA file: %s', giaFile);
    end
    cleaner = onCleanup(@() fclose(fid)); %#ok<NASGU>

    while true
        ln = fgetl(fid);
        if ~ischar(ln); break; end
        tok = sscanf(ln, '%f %f %f %f');
        if numel(tok) ~= 4
            continue; % skip headers/blank lines
        end
        l = tok(1); m = tok(2);
        if l < 0 || m < 0 || m > l || l > Lmax
            continue;
        end
        Cgia(l+1, m+1) = tok(3);
        Sgia(l+1, m+1) = tok(4);
    end

    SH.C = SH.C - Cgia;
    SH.S = SH.S - Sgia;
    SH.meta.gia = struct('file', giaFile, 'Lmax', Lmax);
end
