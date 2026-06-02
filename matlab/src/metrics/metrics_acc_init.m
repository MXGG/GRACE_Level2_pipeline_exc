function ACC = metrics_acc_init(methods, lonVec, latVec, Nt)
%METRICS_ACC_INIT Initialize accumulator for time-series metrics and SRMSE map.

    nLon = numel(lonVec);
    nLat = numel(latVec);

    ACC = struct();
    ACC.methods = methods(:);
    ACC.Nt = Nt;
    ACC.lon = lonVec(:).';
    ACC.lat = latVec(:).';

    for i = 1:numel(methods)
        m = methods{i};

        ACC.ts.(m).CC   = nan(Nt,1);
        ACC.ts.(m).NSC  = nan(Nt,1);
        ACC.ts.(m).RMSE = nan(Nt,1);
        ACC.ts.(m).MAE  = nan(Nt,1);
        ACC.ts.(m).PSNR = nan(Nt,1);
        ACC.ts.(m).SNR  = nan(Nt,1);
        ACC.ts.(m).Nvalid = zeros(Nt,1);

        ACC.sse.(m)  = zeros(nLon, nLat); % sum of squared error per cell
        ACC.nmap.(m) = zeros(nLon, nLat); % count per cell
    end
end
