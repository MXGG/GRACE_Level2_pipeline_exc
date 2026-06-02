function [Dc_f, Ds_f, varargout] = filter_sh_ddk(Dc, Ds, cfg_ddk, cfg_path, varargin)
%FILTER_SH_DDK Apply DDK filter via the GRACE-filter-master matrices.
%   This wrapper prefers the DDK binary matrices under GRACE-filter-master/data/DDK.
%
% Basic usage:
%   [Dc_f, Ds_f, meta] = filter_sh_ddk(Dc, Ds, cfg_ddk, cfg_path)
%
% Optional diagonal sigma propagation:
%   [Dc_f, Ds_f, sigC_f, sigS_f, meta] = filter_sh_ddk( ...
%       Dc, Ds, cfg_ddk, cfg_path, sigC, sigS)
%
% Notes:
%   - Sigma propagation follows GRACE-filter-master filterSH() diagonal mode.
%   - Existing 2/3-output call sites remain backward-compatible.

    if nargin < 3 || isempty(cfg_ddk); cfg_ddk = struct(); end
    if nargin < 4 || isempty(cfg_path); cfg_path = struct(); end

    meta = struct('type','DDK','ddk_type','','matrix','');
    cfg_ddk.type = getfield_default(cfg_ddk, 'type', 'DDK4');
    meta.ddk_type = cfg_ddk.type;

    ddkFiles = struct( ...
        'DDK1','Wbd_2-120.a_1d14p_4', ...
        'DDK2','Wbd_2-120.a_1d13p_4', ...
        'DDK3','Wbd_2-120.a_1d12p_4', ...
        'DDK4','Wbd_2-120.a_5d11p_4', ...
        'DDK5','Wbd_2-120.a_1d11p_4', ...
        'DDK6','Wbd_2-120.a_5d10p_4', ...
        'DDK7','Wbd_2-120.a_1d10p_4', ...
        'DDK8','Wbd_2-120.a_5d9p_4');

    typeKey = upper(cfg_ddk.type);
    if ~isfield(ddkFiles, typeKey)
        error('Unknown DDK type: %s', cfg_ddk.type);
    end

    dataDir = locate_ddk_dir(cfg_ddk, cfg_path);
    ddkFile = fullfile(dataDir, ddkFiles.(typeKey));
    if ~isfile(ddkFile)
        error('DDK matrix not found: %s', ddkFile);
    end

    meta.matrix = ddkFile;

    if exist('filterSH','file') ~= 2
        error('filterSH is not on the MATLAB path. Add GRACE-filter-master/src/matlab.');
    end

    persistent ddkCache
    if isempty(ddkCache)
        ddkCache = containers.Map('KeyType','char','ValueType','any');
    end

    if isKey(ddkCache, ddkFile)
        W = ddkCache(ddkFile);
    else
        W = read_BIN(ddkFile);
        ddkCache(ddkFile) = W;
    end
    hasSigmaInput = numel(varargin) >= 2 && ~isempty(varargin{1}) && ~isempty(varargin{2});
    if hasSigmaInput
        sigC = varargin{1};
        sigS = varargin{2};
        [Dc_f, Ds_f, sigC_f, sigS_f] = filterSH(W, Dc, Ds, sigC, sigS);
    else
        [Dc_f, Ds_f] = filterSH(W, Dc, Ds);
    end

    if hasSigmaInput
        if nargout >= 5
            varargout{1} = sigC_f;
            varargout{2} = sigS_f;
            varargout{3} = meta;
        elseif nargout == 4
            varargout{1} = sigC_f;
            varargout{2} = sigS_f;
        elseif nargout == 3
            varargout{1} = meta;
        end
    else
        if nargout >= 3
            varargout{1} = meta;
        end
    end
end

function val = getfield_default(S, name, defaultVal)
    if isfield(S, name) && ~isempty(S.(name))
        val = S.(name);
    else
        val = defaultVal;
    end
end

function dataDir = locate_ddk_dir(cfg_ddk, cfg_path)
    if isfield(cfg_ddk, 'data_dir') && ~isempty(cfg_ddk.data_dir) && isfolder(cfg_ddk.data_dir)
        dataDir = cfg_ddk.data_dir;
        return;
    end

    if isstruct(cfg_path)
        if isfield(cfg_path,'DDK') && ~isempty(cfg_path.DDK) && isfolder(cfg_path.DDK)
            dataDir = cfg_path.DDK;
            return;
        end
        if isfield(cfg_path,'AUX') && ~isempty(cfg_path.AUX)
            candidate = fullfile(cfg_path.AUX, 'DDK');
            if isfolder(candidate)
                dataDir = candidate;
                return;
            end
        end
    end

    envDir = getenv('IFILES');
    if ~isempty(envDir)
        candidate = fullfile(envDir, 'GRACE-filter-master', 'data', 'DDK');
        if isfolder(candidate)
            dataDir = candidate;
            return;
        end
    end

    error('DDK data directory not found; configure cfg.filter.ddk.data_dir.');
end
