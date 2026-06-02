function [Dc_w, Ds_w, w1] = apply_gaussian_filter(radius_km, Lmax, Dc, Ds)
%APPLY_GAUSSIAN_FILTER Gaussian smoothing in spectral domain (degree-only).
%
% Inputs:
%   radius_km : Gaussian radius (km). If <=0, returns input unchanged.
%   Lmax      : maximum degree
%   Dc, Ds    : SH coefficient arrays:
%               - 2D: (Lmax+1) x (Lmax+1)
%               - 3D: (Lmax+1) x (Lmax+1) x Nt
%
% Outputs:
%   Dc_w, Ds_w : filtered coefficients with same size as input
%   w1         : degree weights vector (Lmax+1)x1

    if radius_km <= 0
        Dc_w = Dc; Ds_w = Ds;
        w1 = ones(Lmax+1,1);
        return;
    end

    persistent weightCache
    if isempty(weightCache)
        weightCache = containers.Map('KeyType','char','ValueType','any');
    end

    cacheKey = sprintf('L%d_R%.8f', Lmax, radius_km);
    if isKey(weightCache, cacheKey)
        w1 = weightCache(cacheKey);
    else
        a  = 6.378136460e6;      % Earth radius (m)
        r1 = radius_km * 1000;   % km -> m
        b1 = log(2) / (1 - cos(r1/a));

        w = zeros(1, Lmax+1);
        w(1) = 1;
        if Lmax >= 1
            w(2) = (1 + exp(-2*b1)) / (1 - exp(-2*b1)) - 1/b1;
        end
        for l = 1:(Lmax-1)
            w(l+2) = -(2*l+1)/b1 * w(l+1) + w(l);
        end

        w1 = w(:); % (Lmax+1)x1
        weightCache(cacheKey) = w1;
    end

    % Apply along degree dimension (rows)
    % 使用 size 检查而非 ndims，因为 ndims 对于 2D 数组始终返回 2
    is3D = (numel(size(Dc)) >= 3 && size(Dc,3) > 1);
    if ~is3D
        Dc_w = Dc .* w1;
        Ds_w = Ds .* w1;
    else
        % broadcast along (deg, order, time)
        Dc_w = Dc .* reshape(w1, [Lmax+1, 1, 1]);
        Ds_w = Ds .* reshape(w1, [Lmax+1, 1, 1]);
    end
end
