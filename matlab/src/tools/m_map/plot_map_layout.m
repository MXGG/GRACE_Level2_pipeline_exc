function plot_map_layout(grid,Lon,Lat,resolution,rows,cols)
%%% Display EWH monthly
% Input: Grid and Coordinates

tiledlayout(rows,cols,'Padding','compact',  'TileSpacing','compact');
for i=1:rows*cols
    if i>size(grid,3)
        break;
    end
    nexttile;
    plot_map(grid(:,:,i),Lon,Lat,resolution);
    hold on
    title(i,"FontSize",14,"FontWeight","bold","FontName","AvantGarde");
    clim([-30,30]);

end
sgtitle(inputname(1),"FontSize",22,"FontWeight","bold","FontName","Times",'Interpreter','None');