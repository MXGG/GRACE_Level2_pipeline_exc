function M = metrics_eval_global(Fo, Ft, isLand, isOcean)
%METRICS_EVAL_GLOBAL Compute global scalar metrics between Fo (test) and Ft (reference).
%
% Inputs:
%   Fo, Ft : [nLon x nLat] grids (mmEWH), NaNs allowed
%   isLand/isOcean : logical masks (optional). If empty, SNR is NaN.
%
% Output fields:
%   CC, NSC, RMSE, MAE, PSNR, SNR, Nvalid

    Fo = Fo(:); Ft = Ft(:);
    v = isfinite(Fo) & isfinite(Ft);
    N = sum(v);

    M = struct('CC',NaN,'NSC',NaN,'RMSE',NaN,'MAE',NaN,'PSNR',NaN,'SNR',NaN,'Nvalid',N);
    if N < 5
        return;
    end

    fo = Fo(v); ft = Ft(v);
    mfo = mean(fo); mft = mean(ft);

    % CC (Pearson)
    num = sum((fo - mfo).*(ft - mft));
    den = sqrt(sum((fo - mfo).^2) * sum((ft - mft).^2));
    if den > 0
        M.CC = num / den;
    end

    % NSC (Nash–Sutcliffe)
    numN = sum((fo - ft).^2);
    denN = sum((ft - mft).^2);
    if denN > 0
        M.NSC = 1 - numN/denN;
    end

    % RMSE / MAE
    mse = mean((fo - ft).^2);
    M.RMSE = sqrt(mse);
    M.MAE  = mean(abs(fo - ft));

    % PSNR (matching your legacy definition)
    maxFt2 = (max(ft))^2;
    M.PSNR = 10 * log10(maxFt2 / (mse + eps));

    % SNR (land RMS / ocean RMS)
    if nargin >= 3 && ~isempty(isLand) && ~isempty(isOcean)
        isLandV  = isLand(:);
        isOceanV = isOcean(:);

        land = Fo(isLandV  & isfinite(Fo));
        ocea = Fo(isOceanV & isfinite(Fo));

        RMS_land  = sqrt(mean(land.^2,  'omitnan'));
        RMS_ocean = sqrt(mean(ocea.^2,  'omitnan'));

        if isfinite(RMS_land) && isfinite(RMS_ocean)
            M.SNR = 10 * log10(RMS_land / (RMS_ocean + eps));
        end
    end
end
