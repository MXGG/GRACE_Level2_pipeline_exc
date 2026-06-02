function plot_map_layout_basin(shpf,grid,Lon,Lat,resolution,rows,cols)
% 日期导入
start_date = datetime(2003, 1, 1);
end_date = datetime(2007, 12, 1);
dates = start_date:calmonths(1):end_date;
% 生成标题所需的月份字符串
month_names = string(datestr(dates, 'mmmm-yyyy'));
month_names(6)=[];
tiledlayout(rows,cols,'Padding','tight','TileSpacing','tight');
p=20:20:500;
for i=1:rows*cols
    nexttile;
    plot_map(grid(:,:,i),Lon,Lat,resolution);
    hold on;
    m_plot(shpf.X,shpf.Y);
    %title("p="+ i*20,"FontSize",12,"FontWeight","bold","FontName",'Times New Roman');
    title(month_names(i),"FontSize",12,"FontWeight","bold","FontName",'Times New Roman');
end
sgtitle(inputname(1),"FontSize",20,"FontWeight","bold","FontName",'Times New Roman','Interpreter','none');