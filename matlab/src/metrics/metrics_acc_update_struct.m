function ACC = metrics_acc_update_struct(ACC, rec)
%METRICS_ACC_UPDATE_STRUCT Structured accumulator update for one month.
%
% rec fields:
%   t, method, Fo, Ft, lonVec, latVec, isLand, isOcean

    Fo = ensure_latlon_order(rec.Fo, rec.lonVec, rec.latVec);
    Ft = ensure_latlon_order(rec.Ft, rec.lonVec, rec.latVec);

    M = metrics_eval_global(Fo, Ft, rec.isLand, rec.isOcean);

    ACC.ts.(rec.method).CC(rec.t)     = M.CC;
    ACC.ts.(rec.method).NSC(rec.t)    = M.NSC;
    ACC.ts.(rec.method).RMSE(rec.t)   = M.RMSE;
    ACC.ts.(rec.method).MAE(rec.t)    = M.MAE;
    ACC.ts.(rec.method).PSNR(rec.t)   = M.PSNR;
    ACC.ts.(rec.method).SNR(rec.t)    = M.SNR;
    ACC.ts.(rec.method).Nvalid(rec.t) = M.Nvalid;

    v = isfinite(Fo) & isfinite(Ft);
    d = Fo - Ft;
    d(~v) = 0;

    ACC.sse.(rec.method)  = ACC.sse.(rec.method) + d.^2;
    ACC.nmap.(rec.method) = ACC.nmap.(rec.method) + double(v);
end
