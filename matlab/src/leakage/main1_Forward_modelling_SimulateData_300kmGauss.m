% 利用模拟数据，评估forward_modelling算法精度（输入是300kmGauss）
clear;clc;close all;
%% 输入数据，滤波后的等效水高
HIS_EWH_dir='D:\Global Forward Modeling\2Simulation_Global_Signal_No_Error\Data\Out\Before_Forward_Modeling\60degree\200604\'; %经过Gauss滤波处理后的全球等效水高文件目录
HIS_file=dir([HIS_EWH_dir,'Global_HIS_Gau_EWH_*']);
nfiles=length(HIS_file);
%% 提前计算勒让德函数，减少计算时间
cor=zeros(180*360,2);
tag=0;
for lat=-89.5:89.5
    for lon=-179.5:179.5
        tag=tag+1;
        cor(tag,1)=lon;
        cor(tag,2)=lat;
    end
end
Pnm_init = Nlmx_v3(60,cor(:,2));
%% 每个数据文件分别迭代
for currentfile=1:nfiles
    current_HIS_file=HIS_file(currentfile).name;   %需要处理的文件名，输入文件的文件名
    HIS_time=current_HIS_file(20:25); %为后面文件名做准备，注意根据文件名修改
    filename=[HIS_EWH_dir,current_HIS_file];
    a=load(filename);
    b=reshape(a(:,3),360,180);
    sumg_grace_gauss500=rot90(b);
%     figure;imagesc(sumg_grace_gauss500);colormap(jet);set(gca,'clim',[-50 50]); %原始的值
    sumg_iteration=sumg_grace_gauss500; %用作迭代的初始值
    Parameter_address         =   'D:\Global Forward Modeling\2Simulation_Global_Signal_No_Error\Data\Parameter\Global_Forward_Modeling_Simulation_Gauss300km.txt';
    C20_address               =   'D:\Global Forward Modeling\2Simulation_Global_Signal_No_Error\Data\C20\TN-07_C20_SLR.txt';
    C20_Flag                  =   0; %1-default replace by SLR C20
    sum_iteration = 99; %forward_modellling迭代的次数
    %-----------------------------------进入迭代环节---------------------------------
    %-----------------------------------进入迭代环节---------------------------------
    %-----------------------------------进入迭代环节---------------------------------
    for iteration=1:sum_iteration
        disp('iteration');
        iteration
        f_iter=num2str(iteration);
        if(iteration<10)
            f_iter=['0',f_iter];
        end
        Output_data_address       =   ['D:\Global Forward Modeling\2Simulation_Global_Signal_No_Error\Data\Out\Forward_Modelling\300kmGauss\',HIS_time,'_input_300kmGauss\iteration',f_iter,'\']; %中间结果的输出路径
        Output_final_address      =   ['D:\Global Forward Modeling\2Simulation_Global_Signal_No_Error\Data\Out\Forward_Modelling\300kmGauss\',HIS_time,'_input_300kmGauss\']; %最终结果的输出路径
        load('D:\Global Forward Modeling\2Simulation_Global_Signal_No_Error\Data\GlobalCoast\globalgrid_1degree.mat'); %边界文件
        
        if ~exist(Output_data_address)
            mkdir(Output_data_address);
        end
        getparameter
        
        global_coast=zeros(180,360);
%         global_coast(180,1:360)=1;
%         global_coast(1:179,1:359)=globalgrid;
%         global_coast(2:180,2:360)=globalgrid;
        global_coast=globalgrid;
        
        %% 分别给陆地和海洋区域赋值
        land_ewh=sumg_iteration.*global_coast; %只保留陆地区域信号
        mean_land(iteration)=mean(reshape(land_ewh,180*360,1)); %求陆地区域信号的平均值
        ocean_ewh=mean_land(iteration)*(global_coast-1); %海洋区域赋值为陆地平均值的负值
        sumg_grace_gauss500_mask=land_ewh+ocean_ewh;
%         figure;imagesc(sumg_grace_gauss500_mask);colormap(jet);set(gca,'clim',[-50 50]); %画海洋区域赋值为陆地信号负值后的图
        %% 存储，用于球谐分析
        filename=[Output_data_address,'gmt_grace_iteration',f_iter,'_',HIS_time,'.txt'];
        fid=fopen(filename,'w');
        sumg_grace_gauss500_mask_3d=zeros(180*360,3); %存储，用于球谐分析
        tag=0;
        for lat=-89.5:89.5
            for lon=-179.5:179.5
                tag=tag+1;
                sumg_grace_gauss500_mask_3d(tag,1)=lon;
                sumg_grace_gauss500_mask_3d(tag,2)=lat;
                sumg_grace_gauss500_mask_3d(tag,3)=sumg_grace_gauss500_mask(-lat+90.5,lon+180.5);
                fprintf(fid,'%10.3f %10.3f %10.3f \n',lon,lat,sumg_grace_gauss500_mask(-lat+90.5,lon+180.5));
            end
        end
        fclose(fid);
        %% 利用mask（边界外的值赋值为0）后的等效水高值，进行球谐分析和Gauss滤波
        %step1-球谐分析
        Pnm=zeros(61,61,180*360);
        Pnm=Pnm_init;
        SH_model_mask = SHanalysis4EWH(sumg_grace_gauss500_mask_3d,Pnm,60,1.0);
        save SH_model_mask.mat SH_model_mask;
        [m n]=size(SH_model_mask);
        filename=[Output_data_address,'SIM_SH','_iteration',f_iter,'_',HIS_time,'.txt'];
        fid=fopen(filename,'w');
        for i=1:m
            fprintf(fid,'%6d %6d %25.15e %25.15e\n',SH_model_mask(i,1:4));
        end
        fclose(fid);
        %step2-球谐综合，获取等效水高(500km高斯滤波)
        getparameter
        [ceta,fir,n_c,n_f,cetax,firx,nceta,nfir]=region_grid(minlat,maxlat,minlon,maxlon,Res_lonlat);
        disp('Region Gridded is ready!')
        Pnm=Nlmx_v3(Lmax,ceta);
        disp('Legendre polynom is ready!')
        [DeltaGC,DeltaGS,Data_number,Data_time]=readdata(Data_type,Output_data_address,Lmax,C20_address,C20_Flag);
        [GRACE_all,sumg_grace_gauss500_iteration1]=CS2EWH(Data_type,DeltaGC,DeltaGS,Data_number,Pnm,De_filter,Filter_index,Lmax,De_P,De_M,Gaussian_r,Fan_r1,Fan_r2,fir,n_c,n_f,nceta,nfir);
        sumg_grace_gauss500_iteration1=flipud(sumg_grace_gauss500_iteration1);
%         figure;imagesc(sumg_grace_gauss500_iteration1);colormap(jet);set(gca,'clim',[-50 50]); %画球谐分析+500km高斯滤波产生的新的信号
        %step3-计算增量
        err_gauss500_iteration1=sumg_grace_gauss500-sumg_grace_gauss500_iteration1;
        filename=[Output_data_address,'gmt_grace_err_iteration',f_iter,'_',HIS_time,'.txt'];
        fid=fopen(filename,'w');
        for lat=-89.5:89.5
            for lon=-179.5:179.5
                fprintf(fid,'%10.3f %10.3f %10.3f \n',lon,lat,err_gauss500_iteration1(-lat+90.5,lon+180.5));
            end
        end
        fclose(fid);
%         figure;imagesc(err_gauss500_iteration1);colormap(jet);set(gca,'clim',[-50 50]); %画高斯滤波产生的泄露误差
        mean_err(iteration)=mean(reshape(err_gauss500_iteration1,180*360,1));
        %step4-计算参与循环的量
        sumg_iteration=sumg_iteration+err_gauss500_iteration1;
    end
    %-----------------------------------结束迭代环节---------------------------------
    %-----------------------------------结束迭代环节---------------------------------
    %-----------------------------------结束迭代环节---------------------------------
    final_grace=sumg_grace_gauss500_mask; %最终结果为对应的mask后的等效水高
    filename_gmt=[Output_final_address,'gmt_grace_forward_modelling_',HIS_time,'.txt'];    %最终的等效水高，输出成gmt格式
    filename_mat=[Output_final_address,'matlab_grace_forward_modelling_',HIS_time,'.txt']; %最终的等效水高，输出成matlab格式
    fid=fopen(filename_gmt,'w');
    fid1=fopen(filename_mat,'w');
    for lat=-89.5:89.5
        for lon=-179.5:179.5
            fprintf(fid,'%10.3f %10.3f %10.3f \n',lon,lat,sumg_grace_gauss500_mask(-lat+90.5,lon+180.5));
            fprintf(fid1,'%10.3f ',sumg_grace_gauss500_mask(-lat+90.5,lon+180.5));
        end
        fprintf(fid1,'\n');
    end
    fclose(fid);
    fclose(fid1);
    filename_ocean_mass=[Output_final_address,'mean_mass_ocean_with_different_iterations_',HIS_time,'.txt']; %随迭代次数变化，海洋质量的变化
    filename_ewh_err=[Output_final_address,'mean_ewh_err_with_different_iterations_',HIS_time,'.txt']; %随迭代次数变化，误差量的平均值
    fid=fopen(filename_ocean_mass,'w');
    fid1=fopen(filename_ewh_err,'w');
    for i=1:sum_iteration
        fprintf(fid,'%4d %10.3f \n',i,-mean_land(i));
        fprintf(fid1,'%4d %10.3f \n',i,mean_err(i));
    end
    fclose(fid);
    fclose(fid1);
end



