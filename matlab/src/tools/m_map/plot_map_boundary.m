function plot_map_boundary(data,data_lon,data_lat,shpf,unit)
    nexttile;
    plot_map(data,data_lon,data_lat,unit);
    hold on;
    m_plot(shpf.X,shpf.Y,'LineWidth',3.0,'color',[1,0,0]);
    cb=colorbar;
    cb.FontName='Times New Roman';
    cb.FontSize=16;
    cb.FontWeight="bold";
    cb.LineWidth=1.5;
    cb.Title.String=unit;
    cb.Location="eastoutside";
    title(inputname(1),"FontSize",20,"FontWeight","bold","FontName",'Times New Roman','Interpreter','none');
