function [Products, ACC] = pipeline_eval_month_metrics(cfg, Products, ACC, k, Tk, refTag, lonVec, latVec, landMask)
%PIPELINE_EVAL_MONTH_METRICS Evaluate metrics for a single month.

    [Products, ACC] = metrics_eval_month(cfg, Products, ACC, k, Tk, refTag, lonVec, latVec, landMask);
end
