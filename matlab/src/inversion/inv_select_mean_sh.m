function [Cmean, Smean, meanTag] = inv_select_mean_sh(meanSH, Tk, cfg)
%INV_SELECT_MEAN_SH Select the mean field to remove for a given month.
% Supports legacy single-mean struct and mission-segmented mean structs.

    Cmean = [];
    Smean = [];
    meanTag = '';
    if nargin < 3
        cfg = struct();
    end
    if isempty(meanSH) || ~isstruct(meanSH)
        return;
    end

    mode = "";
    if isfield(meanSH, 'mode') && ~isempty(meanSH.mode)
        mode = lower(string(meanSH.mode));
    end

    if mode == "mission_full_period" && isfield(meanSH, 'by_mission') && isstruct(meanSH.by_mission)
        mission = inv_infer_mission(Tk, cfg);
        key = mission_to_key(mission);
        if isfield(meanSH.by_mission, key)
            blk = meanSH.by_mission.(key);
            if isfield(blk, 'cnt') && blk.cnt > 0 && isfield(blk, 'C') && isfield(blk, 'S')
                Cmean = blk.C;
                Smean = blk.S;
                meanTag = key;
                return;
            end
        end
    end

    if isfield(meanSH, 'C') && isfield(meanSH, 'S')
        Cmean = meanSH.C;
        Smean = meanSH.S;
        meanTag = 'global';
    end
end

function key = mission_to_key(mission)
    m = upper(string(mission));
    if m == "GRACE-FO"
        key = 'grace_fo';
    elseif m == "GRACE"
        key = 'grace';
    else
        key = 'unknown';
    end
end
