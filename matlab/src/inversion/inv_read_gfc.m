function SH = inv_read_gfc(gfcFile, Lmax)
%INV_READ_GFC Read ICGEM .gfc file and return SH coefficients up to Lmax.
% Output:
%   SH.C, SH.S: (Lmax+1) x (Lmax+1), with C(l+1,m+1)
%   SH.sigmaC, SH.sigmaS: formal std for C/S (if present in file)
%   SH.hasSigma: true when sigma columns are available
%   SH.meta: file, title, degree, etc.
%
% Notes:
% - Supports lines beginning with 'gfc'/'gfct' and 'GRCOF2'.
% - Skips header until 'end_of_head'.
% - Handles Fortran exponent format ('D'/'d') in numeric columns.

    if ~isfile(gfcFile)
        error('gfc file not found: %s', gfcFile);
    end

    fid = fopen(gfcFile,'r');
    if fid < 0
        error('Cannot open file: %s', gfcFile);
    end

    meta = struct();
    meta.file = gfcFile;
    meta.coeff_count = 0;

    % --- skip header
    while true
        ln = fgetl(fid);
        if ~ischar(ln)
            fclose(fid);
            error('Invalid gfc: end_of_head not found.');
        end
        if contains(lower(ln),'end_of_head')
            break;
        end
    end

    C = zeros(Lmax+1, Lmax+1);
    S = zeros(Lmax+1, Lmax+1);
    sigmaC = nan(Lmax+1, Lmax+1);
    sigmaS = nan(Lmax+1, Lmax+1);

    while true
        ln = fgetl(fid);
        if ~ischar(ln)
            break;
        end
        ln = strtrim(ln);
        if isempty(ln)
            continue;
        end

        parts = regexp(ln, '\s+', 'split');
        if numel(parts) < 5
            continue;
        end

        tok = lower(parts{1});
        if ~(startsWith(tok, 'gfc') || strcmp(tok, 'grcof2'))
            continue;
        end

        l = parse_num(parts{2});
        m = parse_num(parts{3});
        cVal = parse_num(parts{4});
        sVal = parse_num(parts{5});

        if any(isnan([l,m,cVal,sVal]))
            continue;
        end
        l = round(l);
        m = round(m);
        if l < 0 || m < 0 || m > l || l > Lmax
            continue;
        end

        C(l+1, m+1) = cVal;
        S(l+1, m+1) = sVal;
        meta.coeff_count = meta.coeff_count + 1;

        if numel(parts) >= 7
            sigCVal = parse_num(parts{6});
            sigSVal = parse_num(parts{7});
            if isfinite(sigCVal); sigmaC(l+1, m+1) = sigCVal; end
            if isfinite(sigSVal); sigmaS(l+1, m+1) = sigSVal; end
        end
    end

    fclose(fid);

    SH = struct();
    SH.Lmax = Lmax;
    SH.C = C;
    SH.S = S;
    SH.sigmaC = sigmaC;
    SH.sigmaS = sigmaS;
    SH.hasSigma = any(isfinite(sigmaC(:))) || any(isfinite(sigmaS(:)));
    SH.meta = meta;
    SH.replaced = struct();
end

function v = parse_num(tok)
    tok = strrep(tok, 'D', 'E');
    tok = strrep(tok, 'd', 'e');
    v = str2double(tok);
end
