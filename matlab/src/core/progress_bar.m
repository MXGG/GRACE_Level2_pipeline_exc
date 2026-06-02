function pb = progress_bar(action, varargin)
%PROGRESS_BAR Advanced progress bar with ETA, ETC, and percentage display.
%
% Usage:
%   pb = progress_bar('create', N, 'Tag', 'Processing')  % Create progress bar
%   pb = progress_bar('update', pb, k)                   % Update progress
%   pb = progress_bar('update', pb, k, 'substep', substep_msg)
%   progress_bar('finish', pb)                           % Finish and show summary
%   progress_bar('reset')                                % Reset all persistent state
%
% Features:
%   - Visual progress bar [=====>       ] 45.3%
%   - ETC (Elapsed Time Cost): Time spent so far
%   - ETA (Estimated Time of Arrival): Remaining time
%   - Supports nested progress (main + submodule progress)
%   - Automatic refresh rate limiting for performance
%
% Output format:
%   [Tag] [===========>           ] 45.3% | ETC: 01:23 | ETA: 01:45 | 45/100
%
% Example:
%   N = 100;
%   pb = progress_bar('create', N, 'Tag', 'Processing data');
%   for k = 1:N
%       % do work...
%       pb = progress_bar('update', pb, k);
%   end
%   progress_bar('finish', pb);
%
% Author: Auto-optimized for GRACE pipeline
% Date: 2026-01

    if nargin < 1
        action = 'help';
    end
    
    pb = [];
    
    switch lower(action)
        case 'create'
            pb = create_progress_bar(varargin{:});
        case 'update'
            pb = update_progress_bar(varargin{:});
        case 'finish'
            finish_progress_bar(varargin{:});
        case 'reset'
            reset_persistent_state();
        case 'help'
            help progress_bar;
        otherwise
            error('progress_bar: Unknown action "%s"', action);
    end
end

%% ========================================================================
%  CREATE
%% ========================================================================
function pb = create_progress_bar(N, varargin)
    p = inputParser;
    p.addRequired('N', @(x) isnumeric(x) && x > 0);
    p.addParameter('Tag', 'Progress', @ischar);
    p.addParameter('BarWidth', 40, @isnumeric);
    p.addParameter('RefreshInterval', 0.5, @isnumeric); % Min seconds between updates
    p.addParameter('ShowSubstep', true, @islogical);
    p.addParameter('Verbose', true, @islogical);
    p.parse(N, varargin{:});
    
    pb = struct();
    pb.N = p.Results.N;
    pb.tag = p.Results.Tag;
    pb.bar_width = p.Results.BarWidth;
    pb.refresh_interval = p.Results.RefreshInterval;
    pb.show_substep = p.Results.ShowSubstep;
    pb.verbose = p.Results.Verbose;
    
    pb.start_time = tic;
    pb.current = 0;
    pb.last_update_time = 0;
    pb.last_print_len = 0;
    pb.substep_msg = '';
    
    % Print header
    if pb.verbose
        fprintf('\n[%s] Started at %s\n', pb.tag, datestr(now, 'HH:MM:SS'));
        fprintf('[%s] Total items: %d\n', pb.tag, pb.N);
    end
end

%% ========================================================================
%  UPDATE
%% ========================================================================
function pb = update_progress_bar(pb, k, varargin)
    if isempty(pb)
        return;
    end
    
    p = inputParser;
    p.addRequired('pb', @isstruct);
    p.addRequired('k', @isnumeric);
    p.addParameter('substep', '', @ischar);
    p.addParameter('force', false, @islogical);
    p.parse(pb, k, varargin{:});
    
    substep_msg = p.Results.substep;
    force = p.Results.force;
    
    pb.current = k;
    pb.substep_msg = substep_msg;
    
    elapsed = toc(pb.start_time);
    
    % Rate limiting: only update display at certain intervals
    if ~force && (elapsed - pb.last_update_time) < pb.refresh_interval && k < pb.N
        return;
    end
    pb.last_update_time = elapsed;
    
    % Calculate progress
    pct = 100 * k / pb.N;
    
    % ETA calculation (with smoothing for first few iterations)
    if k > 0
        avg_time_per_item = elapsed / k;
        eta_sec = avg_time_per_item * (pb.N - k);
    else
        eta_sec = 0;
    end
    
    % Build progress bar string
    filled = round(pb.bar_width * k / pb.N);
    bar_str = [repmat('=', 1, max(0, filled-1)), ...
               char('>' * (filled > 0)), ...
               repmat(' ', 1, pb.bar_width - filled)];
    
    % Format times
    etc_str = format_duration(elapsed);
    eta_str = format_duration(eta_sec);
    
    % Build output line
    if pb.show_substep && ~isempty(substep_msg)
        line = sprintf('[%s] [%s] %5.1f%% | ETC: %s | ETA: %s | %d/%d | %s', ...
            pb.tag, bar_str, pct, etc_str, eta_str, k, pb.N, substep_msg);
    else
        line = sprintf('[%s] [%s] %5.1f%% | ETC: %s | ETA: %s | %d/%d', ...
            pb.tag, bar_str, pct, etc_str, eta_str, k, pb.N);
    end
    
    % Clear previous line and print new one
    if pb.last_print_len > 0
        fprintf(repmat('\b', 1, pb.last_print_len));
    end
    fprintf('%s', line);
    pb.last_print_len = length(line);
    
    % Force newline at completion
    if k == pb.N
        fprintf('\n');
        pb.last_print_len = 0;
    end
end

%% ========================================================================
%  FINISH
%% ========================================================================
function finish_progress_bar(pb)
    if isempty(pb)
        return;
    end
    
    elapsed = toc(pb.start_time);
    
    if pb.verbose
        fprintf('[%s] Completed at %s\n', pb.tag, datestr(now, 'HH:MM:SS'));
        fprintf('[%s] Total time: %s (%.2f sec/item)\n', ...
            pb.tag, format_duration(elapsed), elapsed / max(pb.N, 1));
    end
end

%% ========================================================================
%  RESET
%% ========================================================================
function reset_persistent_state()
    % For future use if we add persistent state
end

%% ========================================================================
%  HELPER: Format duration in HH:MM:SS or MM:SS
%% ========================================================================
function str = format_duration(seconds)
    if ~isfinite(seconds) || seconds < 0
        str = '--:--';
        return;
    end
    
    seconds = round(seconds);
    hours = floor(seconds / 3600);
    minutes = floor(mod(seconds, 3600) / 60);
    secs = mod(seconds, 60);
    
    if hours > 0
        str = sprintf('%02d:%02d:%02d', hours, minutes, secs);
    else
        str = sprintf('%02d:%02d', minutes, secs);
    end
end
