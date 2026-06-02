function h = cfg_hash(cfg)
%CFG_HASH Create a stable MD5 hash for a configuration struct.
%
% Description:
%   Generates a unique hash based on configuration content. Used for:
%   - Checkpoint/resume validation
%   - Cache invalidation
%   - Configuration comparison
%
% Usage:
%   h = cfg_hash(cfg)
%
% Input:
%   cfg - Configuration struct
%
% Output:
%   h   - 32-character hexadecimal MD5 hash string
%
% Notes:
%   - Hash changes if ANY configuration field changes
%   - Sensitive to field ordering in structs
%   - Uses Java MessageDigest for MD5 computation
%
% Example:
%   cfg = cfg_load('user.json', 'default.json');
%   h = cfg_hash(cfg);
%   % h = '5d41402abc4b2a76b9719d911017c592'

    % Create deterministic string representation
    try
        % jsonencode provides consistent ordering
        raw = jsonencode(cfg);
    catch
        % Fallback for complex structs that fail jsonencode
        raw = struct_to_string(cfg);
    end
    
    % Compute MD5 hash
    h = md5_string(raw);
end

function h = md5_string(s)
%MD5_STRING Compute MD5 hash of a string.
    try
        md = java.security.MessageDigest.getInstance('MD5');
        md.update(uint8(s));
        h = sprintf('%.2x', typecast(md.digest(), 'uint8'));
    catch
        % Fallback if Java is not available
        h = fallback_hash(s);
    end
end

function h = fallback_hash(s)
%FALLBACK_HASH Simple hash when Java MD5 is unavailable.
    % Use MATLAB's built-in DataHash if available
    if exist('DataHash', 'file') == 2
        h = DataHash(s, 'MD5', 'hex');
    else
        % Simple checksum fallback
        bytes = uint8(s);
        h = sprintf('%08x%08x%08x%08x', ...
            mod(sum(bytes(1:4:end)) * 17, 2^32), ...
            mod(sum(bytes(2:4:end)) * 31, 2^32), ...
            mod(sum(bytes(3:4:end)) * 47, 2^32), ...
            mod(sum(bytes(4:4:end)) * 67, 2^32));
    end
end

function s = struct_to_string(obj)
%STRUCT_TO_STRING Convert nested struct to deterministic string.
    if isstruct(obj)
        fn = sort(fieldnames(obj));
        parts = cell(numel(fn), 1);
        for i = 1:numel(fn)
            parts{i} = sprintf('%s=%s', fn{i}, struct_to_string(obj.(fn{i})));
        end
        s = ['{' strjoin(parts, ',') '}'];
    elseif iscell(obj)
        parts = cellfun(@struct_to_string, obj, 'UniformOutput', false);
        s = ['[' strjoin(parts, ',') ']'];
    elseif ischar(obj)
        s = ['"' obj '"'];
    elseif isstring(obj)
        s = ['"' char(obj) '"'];
    elseif isnumeric(obj)
        s = mat2str(obj);
    elseif islogical(obj)
        if obj
            s = 'true';
        else
            s = 'false';
        end
    else
        s = class(obj);
    end
end
