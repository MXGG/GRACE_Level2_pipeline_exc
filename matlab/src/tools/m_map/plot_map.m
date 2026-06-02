function plot_map(grid_data,Lon,Lat,resolution)
    %m_proj('Lambert','lon',[Lon(1)-resolution/2 Lon(end)+resolution/2],'lat',[Lat(1)-resolution/2 Lat(end)+resolution/2]);
    %m_proj('Equidistant Cylindrical','lon',[Lon(1)-resolution/2 Lon(end)+resolution/2],'lat',[Lat(1)-resolution/2 Lat(end)+resolution/2]);
    m_proj('Robinson','lon',[Lon(1) Lon(end)],'lat',[Lat(1) Lat(end)]);
    %m_proj('Robinson','lon',[Lon(1) Lon(end)],'lat',[Lat(1) Lat(end)]);
    [X,Y] = meshgrid(Lon(1):resolution:Lon(end), Lat(1):resolution:Lat(end));
    m_pcolor(X, Y, grid_data');
    %m_pcolor(X, Y, grid_data);
    hold on;
    m_coast('linewidth',1.0,'color','k');
    m_grid('box','on','tickdir','in','FontName','Times','fontsize',10,'fontweight','bold','linewidth',1.5,'xtick',4,'ytick',4);
    colormap("jet");
    %colorbar;
    clim([-15,15]);
%    title(inputname(1),"FontSize",12,"FontWeight","bold","FontName","Times","Interpreter","none");
end


% function plot_map(grid_data, Lon, Lat, resolution, lon_lim, lat_lim)
%     % 设置统一的地图投影边界（传入参数统一控制）
%     m_proj('Equidistant Cylindrical', 'lon', lon_lim, 'lat', lat_lim);
% 
%     [X,Y] = meshgrid(Lon, Lat);
%     m_pcolor(X, Y, grid_data'); % 注意转置
%     shading flat;
%     hold on;
% 
%     m_coast('linewidth',1.2,'color','k');
%     m_grid('box','on','tickdir','in', ...
%            'FontName','Times','fontsize',8, ...
%            'fontweight','bold','linewidth',1.0, ...
%            'xtick',4, 'ytick',4);  % 保持 tick 数目一致
% 
%     colormap("jet");
%     clim([-15,15]); % 固定色阶，便于对比
% end

% 
% function plot_map(grid_data, Lon, Lat, resolution, lon_range, lat_range)
%     % 确保输入的经纬度范围有效
%     if nargin < 5
%         lon_range = [min(Lon), max(Lon)];
%         lat_range = [min(Lat), max(Lat)];
%     end
% 
%     % 设置投影范围（使用传入的统一范围）
%     m_proj('Equidistant Cylindrical', 'lon', lon_range, 'lat', lat_range);
% 
%     % 创建网格（基于实际数据的经纬度范围）
%     [X, Y] = meshgrid(Lon(1):resolution:Lon(end), Lat(1):resolution:Lat(end));
%     m_pcolor(X, Y, grid_data');
%     hold on;
% 
%     % 绘制海岸线
%     m_coast('linewidth', 1.2, 'color', 'k');
% 
%     % 动态计算刻度间隔
%     lon_span = lon_range(2) - lon_range(1);
%     lat_span = lat_range(2) - lat_range(1);
%     % 每 5° 设置一个刻度（可根据需求调整）
%     xtick_interval = max(5, round(lon_span / 4 / 5) * 5); % 至少 4 个刻度
%     ytick_interval = max(5, round(lat_span / 4 / 5) * 5);
%     xticks = lon_range(1):xtick_interval:lon_range(2);
%     yticks = lat_range(1):ytick_interval:lat_range(2);
% 
%     % 绘制网格和刻度
%     m_grid('box', 'on', 'tickdir', 'in', 'FontName', 'Times', 'fontsize', 10, ...
%            'fontweight', 'bold', 'linewidth', 1.5, 'xtick', xticks, 'ytick', yticks);
% 
%     % 设置颜色和范围
%     colormap("jet");
%     clim([-15, 15]);
% end


% function plot_map(grid_data, Lon, Lat, resolution, lon_range, lat_range)
%     % 确保输入的经纬度范围有效
%     if nargin < 5
%         lon_range = [min(Lon), max(Lon)];
%         lat_range = [min(Lat), max(Lat)];
%     end
% 
%     % 设置投影范围（使用统一范围）
%     m_proj('Equidistant Cylindrical', 'lon', lon_range, 'lat', lat_range);
% 
%     % 创建网格（基于实际数据的经纬度范围）
%     [X, Y] = meshgrid(Lon(1):resolution:Lon(end), Lat(1):resolution:Lat(end));
%     m_pcolor(X, Y, grid_data');
%     hold on;
% 
%     % 绘制海岸线
%     m_coast('linewidth', 1.2, 'color', 'k');
% 
%     % 设置固定的刻度间隔（例如每 10° 一个刻度）
%     tick_interval = 10; % 可根据需求调整，例如 5° 或 15°
%     xticks = ceil(lon_range(1)/tick_interval)*tick_interval:tick_interval:floor(lon_range(2)/tick_interval)*tick_interval;
%     yticks = ceil(lat_range(1)/tick_interval)*tick_interval:tick_interval:floor(lat_range(2)/tick_interval)*tick_interval;
% 
%     % 绘制网格和刻度
%     m_grid('box', 'on', 'tickdir', 'in', 'FontName', 'Times', 'fontsize', 10, ...
%            'fontweight', 'bold', 'linewidth', 1.5, 'xtick', xticks, 'ytick', yticks);
% 
%     % 设置颜色和范围
%     colormap("jet");
%     clim([-15, 15]);
% end