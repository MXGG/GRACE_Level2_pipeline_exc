function perf = perf_tracker(action, varargin)
%PERF_TRACKER Lightweight performance tracker for pipeline steps.

    switch lower(action)
        case 'create'
            cfg = struct();
            if ~isempty(varargin)
                cfg = varargin{1};
            end
            perf = struct();
            perf.enable = getfield_default(cfg, 'enable', true); %#ok<GFLD>
            perf.show = getfield_default(cfg, 'show', false); %#ok<GFLD>
            perf.min_seconds = getfield_default(cfg, 'min_seconds', 0); %#ok<GFLD>
            perf.records = struct('label', {}, 'seconds', {});
        case 'add'
            perf = varargin{1};
            label = varargin{2};
            seconds = varargin{3};
            if ~isfield(perf, 'enable') || ~perf.enable
                return;
            end
            if seconds < perf.min_seconds
                return;
            end
            perf.records(end+1) = struct('label', label, 'seconds', seconds); %#ok<AGROW>
            if isfield(perf, 'show') && perf.show
                fprintf('[PERF] %s: %.3fs\n', label, seconds);
            end
        case 'finish'
            perf = varargin{1};
            if isfield(perf, 'show') && perf.show && isfield(perf, 'records') && ~isempty(perf.records)
                total = sum([perf.records.seconds]);
                fprintf('[PERF] Total tracked: %.3fs\n', total);
            end
        otherwise
            error('perf_tracker:UnknownAction', 'Unknown action: %s', action);
    end
end

function val = getfield_default(s, name, defaultVal)
    if isstruct(s) && isfield(s, name)
        val = s.(name);
    else
        val = defaultVal;
    end
end
