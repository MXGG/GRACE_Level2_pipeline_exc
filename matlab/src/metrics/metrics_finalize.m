function OUT = metrics_finalize(ACC)
%METRICS_FINALIZE Finalize SRMSE maps etc.

    OUT = struct();
    OUT.methods = ACC.methods;
    OUT.lon = ACC.lon;
    OUT.lat = ACC.lat;
    OUT.ts  = ACC.ts;

    for i = 1:numel(ACC.methods)
        m = ACC.methods{i};
        n = ACC.nmap.(m);
        sse = ACC.sse.(m);

        srmse = nan(size(sse));
        ok = n > 0;
        srmse(ok) = sqrt(sse(ok) ./ n(ok));

        OUT.srmse.(m) = srmse;
        OUT.nmap.(m)  = n;
    end
end
