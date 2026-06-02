function [fig, ax] = plot_sc_spectrum(SC, opt)
%PLOT_SC_SPECTRUM Visualize SC spectrum matrix (L x (2L+1)).
% SC: [Lmax+1 x (2Lmax+1)] for one epoch
    if nargin < 2; opt = struct(); end
    if ~isfield(opt,'title'); opt.title = 'SC spectrum'; end

    fig = figure('Color','w');
    ax = axes(fig);
    imagesc(ax, SC);
    set(ax,'YDir','normal');
    xlabel(ax, 'Order index'); ylabel(ax, 'Degree');
    title(ax, opt.title, 'Interpreter','none');
    colorbar(ax);
    grid(ax,'on'); box(ax,'on');
end
