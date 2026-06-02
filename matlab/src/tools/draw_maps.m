function draw_maps(CSR_EWH, csr_lon, csr_lat, Dir_images_output, month_names, start_idx)
%DRAW_MAPS Generate batch visualization of EWH maps for multiple methods.
%
% Description:
%   Creates and saves multi-panel map figures showing EWH grids for each
%   filtering method. Outputs are organized by year (12 months per figure).
%
% INPUT:
%   CSR_EWH          - Structure with fields for each method (e.g., 'Gaussian', 'P4M6')
%                      Each field contains [nLon x nLat x Nt] EWH grids
%   csr_lon          - Longitude vector
%   csr_lat          - Latitude vector
%   Dir_images_output - Output directory for PNG files
%   month_names      - Cell array of month labels (e.g., {'2003-01', '2003-02', ...})
%   start_idx        - Starting index for time series
%
% OUTPUT:
%   PNG files saved to Dir_images_output with naming:
%   {method}_CSR_EWH_{start_month}_{end_month}.png
%
% Author: GRACE Pipeline Team

    methods = fieldnames(CSR_EWH);
    time_steps = size(CSR_EWH.(methods{1}), 3);
    
    % Loop over each filtering method
    for i = 1:length(methods)
        method = methods{i};
        step_size = 12; % 12 months per figure (one year)
        
        % Set time range based on method
        if method == "Hankel"
            start_id = 1;
            end_id = time_steps;
        else
            start_id = start_idx;
            end_id = time_steps;
        end
        
        % Generate figures for each year
        for start_id = 1:step_size:time_steps
            end_idx = min(start_id + step_size - 1, time_steps);
            fig = figure();
            
            % Create multi-panel layout (3 rows x 4 columns)
            plot_map_layout_new(CSR_EWH.(method)(:,:,start_id:end_idx), csr_lon, csr_lat, 1, 3, 4, start_idx);
            
            % Add super title
            sgtitle(["CSR EWH " + method + " Solution (" + month_names(start_id) + " - " + month_names(end_idx) + ")"], 'FontSize', 20);
            set(fig, 'OuterPosition', [-6.2, 41.8, 1550.4, 830.4]);
            
            % Save figure
            filename = sprintf("%s_CSR_EWH_%s_%s_%s.png", method, month_names(start_id), month_names(end_idx));
            print(gcf, fullfile(Dir_images_output, filename), '-dpng', '-r600');
            close(fig);
        end
    end
end
