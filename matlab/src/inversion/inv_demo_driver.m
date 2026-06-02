function inv_demo_driver()
%INV_DEMO_DRIVER Minimal demo for inversion module (no filters).
% Assumes project root is current folder.

cfg = cfg_load(fullfile('config','user.json'), fullfile('config','default.json'));
setup_env(cfg);

T = build_time_index(cfg);
syn = inv_prepare_synthesis(cfg);

if cfg.inversion.remove_mean
    meanSH = inv_get_mean_sh(cfg, T);
else
    meanSH = [];
end

k = 1;
Praw = inv_invert_month(cfg, T(k), meanSH, syn);
disp(Praw.tag);
disp(size(Praw.grid.ewh));
end
