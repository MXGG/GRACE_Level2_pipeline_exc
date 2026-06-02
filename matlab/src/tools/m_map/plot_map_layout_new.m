function plot_map_layout_new(grid,Lon,Lat,resolution,rows,cols,start_idx)
% 日期导入
load time.mat
% 生成标题所需的月份字符串
% month_names = string(datestr(dates, 'mmmm-yyyy'));
tiledlayout(rows,cols,'Padding','compact',  'TileSpacing','compact');
for i=1:rows*cols
    nexttile;
    plot_map(grid(:,:,i),Lon,Lat,resolution);
    hold on
    %title("order="+ (i+5),"FontSize",12,"FontWeight","bold","FontName",'Times New Roman');
    %title("p="+(i+2)*20,"FontSize",12,"FontWeight","bold","FontName",'Times New Roman');
    title(month_names(start_idx+i-1),"FontSize",14,"FontWeight","bold","FontName",'Times');
    fontname("AvantGarde");
    %title("order="+i,"FontSize",12,"FontWeight","bold","FontName",'Times New Roman');
    %title("mode="+i,"FontSize",12,"FontWeight","bold","FontName",'Times New Roman');
end
sgtitle(inputname(1),"FontSize",22,"FontWeight","bold","FontName","Times",'Interpreter','None');