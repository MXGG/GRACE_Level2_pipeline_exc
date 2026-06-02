function SH = inv_replace_low_degree(cfg, SH, Tk)
%INV_REPLACE_LOW_DEGREE Replace low-degree terms using TN-13/TN-14 inputs.
%
% The replacement strategy follows common RL06 practice:
%   - C20 from TN-14 SLR
%   - Degree-1 (C10/C11/S11) from TN-13 geocenter
%   - C30 from TN-14 for configured mission scope when enabled

    if isfield(cfg, 'inv') && isfield(cfg.inv, 'lowdeg') ...
            && isfield(cfg.inv.lowdeg, 'enable') && cfg.inv.lowdeg.enable
        ld = cfg.inv.lowdeg;
    elseif isfield(cfg, 'inversion') && isfield(cfg.inversion, 'lowdeg') ...
            && isfield(cfg.inversion.lowdeg, 'enable') && cfg.inversion.lowdeg.enable
        ld = cfg.inversion.lowdeg;
    else
        return;
    end

    dt = datetime(Tk.ym, 'InputFormat', 'yyyy-MM');
    yy = year(dt);
    mm = month(dt);
    rep = SH.replaced;

    replaceDegree1 = false;
    if isfield(ld, 'replace_degree1') && ~isempty(ld.replace_degree1)
        replaceDegree1 = logical(ld.replace_degree1);
    elseif isfield(ld, 'replace_C10') && ~isempty(ld.replace_C10)
        replaceDegree1 = logical(ld.replace_C10);
    end

    replaceC30 = false;
    if isfield(ld, 'replace_C30') && ~isempty(ld.replace_C30)
        replaceC30 = logical(ld.replace_C30);
    end

    if isfield(ld, 'replace_C20') && logical(ld.replace_C20)
        if ~isfield(ld, 'files') || ~isfield(ld.files, 'C20')
            error('cfg.inversion.lowdeg.files.C20 missing (TN-14 path).');
        end
        [spanStart, spanEnd] = lowdeg_replacement_span(Tk, dt);
        [c20, c30, c20Match] = inv_read_lowdeg_tn14_c20(ld.files.C20, yy, mm, spanStart, spanEnd);
        SH.C(2+1, 0+1) = c20;
        rep.C20 = 'TN-14/SLR';
        rep.C20_match = c20Match;

    c30StartYm = "2018-06";
    if isfield(ld, 'c30_start_ym') && ~isempty(ld.c30_start_ym)
        c30StartYm = string(ld.c30_start_ym);
    end
    currentYm = string(sprintf('%04d-%02d', yy, mm));
    mission = inv_infer_mission(Tk, cfg);
    c30Scope = "grace_fo";
    if isfield(ld, 'c30_scope') && ~isempty(ld.c30_scope)
        c30Scope = lower(strrep(string(ld.c30_scope), '-', '_'));
    end
    applyByMission = (c30Scope == "all") ...
        || (c30Scope == "grace_fo" && upper(string(mission)) == "GRACE-FO") ...
        || (c30Scope == "grace" && upper(string(mission)) == "GRACE");

    if replaceC30 && applyByMission && currentYm >= c30StartYm && isfinite(c30) && size(SH.C, 1) >= 4
        SH.C(3+1, 0+1) = c30;
        rep.C30 = 'TN-14/SLR';
    end
    end

    if replaceDegree1
        degree1File = resolve_degree1_file(ld, Tk, SH);
        [c10, c11, s11] = inv_read_lowdeg_tn13_degree1(degree1File, yy, mm);
        SH.C(1+1, 0+1) = c10;
        rep.C10 = 'TN-13/GEOC';

        if size(SH.C, 1) >= 2 && size(SH.C, 2) >= 2
            SH.C(1+1, 1+1) = c11;
            SH.S(1+1, 1+1) = s11;
            rep.C11 = 'TN-13/GEOC';
            rep.S11 = 'TN-13/GEOC';
            rep.Degree1 = 'TN-13/GEOC';
        end
    end

    if isfield(ld, 'replace_S20') && logical(ld.replace_S20)
        if isfield(ld, 'files') && isfield(ld.files, 'S20')
            s20 = inv_read_lowdeg_scalar(ld.files.S20, yy, mm, 'S20');
            SH.S(2+1, 0+1) = s20;
            rep.S20 = 'AUX';
        else
            warning('replace_S20 enabled but cfg.inversion.lowdeg.files.S20 not provided. Skipped.');
        end
    end

    SH.replaced = rep;
end

function [spanStart, spanEnd] = lowdeg_replacement_span(Tk, monthDt)
    spanStart = dateshift(monthDt, 'start', 'month');
    spanEnd = dateshift(monthDt, 'end', 'month');
    if isfield(Tk, 'gfc_start_dt') && isdatetime(Tk.gfc_start_dt) && ~isnat(Tk.gfc_start_dt)
        spanStart = Tk.gfc_start_dt;
    end
    if isfield(Tk, 'gfc_end_dt') && isdatetime(Tk.gfc_end_dt) && ~isnat(Tk.gfc_end_dt)
        spanEnd = Tk.gfc_end_dt;
    end
    if spanEnd < spanStart
        spanStart = dateshift(monthDt, 'start', 'month');
        spanEnd = dateshift(monthDt, 'end', 'month');
    end
end

function fp = resolve_degree1_file(ld, Tk, SH)
    if ~isfield(ld, 'files') || ~isstruct(ld.files)
        error('cfg.inversion.lowdeg.files is missing.');
    end

    files = ld.files;
    center = inv_infer_center(Tk, SH);

    switch upper(center)
        case 'JPL'
            candidates = {'DEGREE1_JPL', 'DEGREE1'};
        case 'GFZ'
            candidates = {'DEGREE1_GFZ', 'DEGREE1'};
        case 'CSR'
            candidates = {'DEGREE1_CSR', 'DEGREE1'};
        otherwise
            candidates = {'DEGREE1', 'DEGREE1_JPL', 'DEGREE1_GFZ', 'DEGREE1_CSR'};
    end

    fp = '';
    for i = 1:numel(candidates)
        key = candidates{i};
        if isfield(files, key) && ~isempty(files.(key))
            fp = files.(key);
            break;
        end
    end

    if isempty(fp)
        error('No TN-13 degree1 file configured. Provide files.DEGREE1 or center-specific DEGREE1_*.');
    end
end
