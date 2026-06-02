% ================================
% GRACE滤波结果的泄漏误差校正流程总汇
% 包含内容：
% 1. Altimetry（GRLM, Hydroweb）数据读取与预处理
% 2. GLDAS数据读取与滤波，估算泄漏误差
% 3. 各方法scale factor计算（1cm合成场）
% 4. 应用scale factor校正后的GRACE平均时间序列
% ================================
% 区域掩膜构建（里海）
load G:\HSAF\Data\EWH_Output\matlab.mat
start_idx=19;
end_idx=150;
cap = shaperead('G:/HSAF/Data/zb452vm0926/XCA_adm0.shp');
[cap_x, cap_y, cap_mk] = mkmask(cap, 0.5);
csr_lon=-179.75:0.5:179.75;csr_lat=-89.75:0.5:89.75;
filter_methods = {'Gaussian','Gaussian_Decorrelation','Fan','Fan_Decorrelation','DDK4','Hankel'};
colors = lines(length(filter_methods));
% 按方法循环，计算区域平均时间序列与年周期分解
for i = 1:length(filter_methods)
    method = filter_methods{i};
    if method == "Hankel"
        idx_range = 1:time_size;
    else
        idx_range = start_idx:end_idx;
    end
    cap_ewh.(method) = EWH.(method)(find(csr_lon==cap_x(1)):find(csr_lon==cap_x(end)), find(csr_lat==cap_y(1)):find(csr_lat==cap_y(end)), idx_range);
    [~, ~, ~, ~, caps.(['time_series_', method]), caps.(['b_', method])] = Basin_Analysis(cap_ewh.(method).*cap_mk', years(idx_range)', cap_x, cap_y);
end
%% -----------------------------------------------------
%% Step 1: Altimetry 数据读取与预处理（GRLM / Hydroweb）
%% -----------------------------------------------------

% Hydroweb 插值处理（CS + KBG）
% GRACE 月尺度 decimal time
decimal_time_grace = year(dates) + (month(dates) - 0.5)/12;

% 读取 CS
fid = fopen('G:/HSAF/Data/Auxiliary_Data/hydroprd_L_caspian.txt', 'r');
decimal_year_cs = []; height_cs = [];
while ~feof(fid)
    line = fgetl(fid);
    if startsWith(strtrim(line), '#') || isempty(strtrim(line)), continue; end
    tokens = strsplit(strtrim(line), ';');
    if length(tokens) >= 4
        t = str2double(tokens{1}); h = str2double(tokens{4});
        if ~isnan(t) && ~isnan(h) && abs(h) < 9999
            decimal_year_cs(end+1,1) = t;
            height_cs(end+1,1) = h;
        end
    end
end
fclose(fid);
csl_alt_interp_cs = interp1(decimal_year_cs, height_cs, decimal_time_grace, 'linear');
csl_alt_interp_cs = (csl_alt_interp_cs - mean(csl_alt_interp_cs(1:72))) * 100;

% 读取 KBG
fid = fopen('G:/HSAF/Data/Auxiliary_Data/hydroprd_L_kara_bogaz_gol.txt', 'r');
decimal_year_k = []; height_k = [];
while ~feof(fid)
    line = fgetl(fid);
    if startsWith(strtrim(line), '#') || isempty(strtrim(line)), continue; end
    tokens = strsplit(strtrim(line), ';');
    if length(tokens) >= 4
        t = str2double(tokens{1}); h = str2double(tokens{4});
        if ~isnan(t) && ~isnan(h) && abs(h) < 9999
            decimal_year_k(end+1,1) = t;
            height_k(end+1,1) = h;
        end
    end
end
fclose(fid);
csl_alt_interp_k = interp1(decimal_year_k, height_k, decimal_time_grace, 'linear');
csl_alt_interp_k = (csl_alt_interp_k - mean(csl_alt_interp_k(1:72))) * 100;

% 面积加权合并
A_cs = 374000; A_k = 18400;
csl_alt_interp_combined = (A_cs * csl_alt_interp_cs + A_k * csl_alt_interp_k) / (A_cs + A_k);

% GRLM 插值处理
% 读取数据并剔除异常值
data = readmatrix('G:/HSAF/Data/Auxiliary_Data/lake000270.10d.2.txt', 'NumHeaderLines', 50);
ymd_raw = data(:,3); h_raw = data(:,15)*100;
valid = h_raw < 9999.99;
ymd = ymd_raw(valid); h = h_raw(valid);

% 日期拆解与处理
yr = floor(ymd / 10000);
mth = floor(mod(ymd, 10000) / 100);
dy = mod(ymd, 100);
valid_date = (mth >= 1 & mth <= 12) & (dy >= 1 & dy <= 31);

yr = yr(valid_date); mth = mth(valid_date); dy = dy(valid_date); h = h(valid_date);
is_leap = mod(yr,4)==0 & (mod(yr,100)~=0 | mod(yr,400)==0);
days_in_year = 365 + is_leap;

% 每年累计天数向量
month_days = [0 31 59 90 120 151 181 212 243 273 304 334];
month_days_leap = [0 31 60 91 121 152 182 213 244 274 305 335];
day_of_year = zeros(size(yr));
for i = 1:length(yr)
    if is_leap(i)
        day_of_year(i) = month_days_leap(mth(i)) + dy(i);
    else
        day_of_year(i) = month_days(mth(i)) + dy(i);
    end
end

% decimal year 计算
decimal_year_grlm = yr + (day_of_year - 1) ./ days_in_year;

% 插值至 GRACE 时间尺度
precision = 1e-6;
[unique_yr, ~, idxu] = unique(round(decimal_year_grlm / precision) * precision);
h_avg = accumarray(idxu, h, [], @mean);
csl_grlm_interp = interp1(unique_yr, h_avg, decimal_time_grace, 'linear', 'extrap');
csl_grlm_interp = csl_grlm_interp - mean(csl_grlm_interp(1:72));

% 绘图对比 GRLM 与 Altimetry
figure; hold on;
plot(dates, csl_alt_interp_combined, 'k-', 'LineWidth', 1.5);
plot(dates, csl_grlm_interp, 'b--', 'LineWidth', 1.5);
legend('Hydroweb (CS + KBG)', 'GRLM');
xlabel('Time'); ylabel('CSL (cm)'); grid on;
title('Comparison of Hydroweb and GRLM CSL Time Series');

% 一致性指标输出
R = corr(csl_grlm_interp(:), csl_alt_interp_combined(:), 'rows', 'complete');
rmse = sqrt(mean((csl_grlm_interp - csl_alt_interp_combined).^2));
fprintf('\nComparison Results:\n');
fprintf('Pearson R = %.3f\n', R);
fprintf('RMSE = %.2f cm\n', rmse);


% ➜ 输出变量: csl_grlm_interp, decimal_time_grace

%% -----------------------------------------------------
%% Step 2: GLDAS 预处理与GRACE滤波匹配
%% -----------------------------------------------------
% 👉 提取 GLDAS 原始 TWS 并裁剪为里海区域
% 👉 构造 grid_gldas_template (360x180x132)
% 👉 对照 GRACE 的时间（dates）与 gldas_time 对齐
% 👉 储存为 cap_ewh.gldas

% === 输入路径和文件 ===
gldas_dir = 'G:\HSAF\Data\Auxiliary_Data\GLDAS\GLDAS_NOAH10_M_2.1-20250410_122232\';  % GLDAS数据路径
gldas_files = dir(fullfile(gldas_dir, '*.nc4'));  % 获取所有nc文件
% === 预分配 TWS (单位为 mm)，维度假设为 (lon, lat, time) = 360×180×N ===
n_time = length(gldas_files);
gldas_tws = nan(360,180,n_time);
% === 初始化 EWH 结构体中 GLDAS TWS ===
GLDAS_TWS_360x180 = nan(360, 180, n_time);  % 目标分辨率
GLDAS_LAT = -59.5:1:89.5;  % 原始纬度150
GLDAS_LON = 0.5:1:359.5;   % 原始经度360

% 经纬度目标

for i = 1:n_time
    file = fullfile(gldas_dir, gldas_files(i).name);

    % 读取各变量，单位：kg/m² ≈ mm
    sm1 = ncread(file, 'SoilMoi0_10cm_inst');
    sm2 = ncread(file, 'SoilMoi10_40cm_inst');
    sm3 = ncread(file, 'SoilMoi40_100cm_inst');
    sm4 = ncread(file, 'SoilMoi100_200cm_inst');
    swe = ncread(file, 'SWE_inst');
    can = ncread(file, 'CanopInt_inst');

    % 求和得到 TWS
    total = sm1 + sm2 + sm3 + sm4 + swe + can;
    gldas_tws(:,31:180,i) = total*0.1;  % 存储
end
% 生成时间轴（从2003.01起，每月一次）
gldas_time = datetime(2000,1,1) + calmonths(0:n_time-1);

% 截取 GLDAS 区域
lon_idx = find(csr_lon == cap_x(1)):find(csr_lon == cap_x(end));
lat_idx = find(csr_lat == cap_y(1)):find(csr_lat == cap_y(end));
EWH.GLDAS_NOAH = gldas_tws-mean(gldas_tws(:,:,find(gldas_time=='2004-01-01'):find(gldas_time=='2009-12-01')),3);
% Step 1: 构建 year-month 向量
gldas_ym = year(gldas_time)*100 + month(gldas_time);   % e.g. 200101, 200102...
grace_ym = year(dates)*100 + month(dates);             % 同样方式转化 GRACE 时间

% Step 2: 查找 GRACE 时间在 GLDAS 中的索引
[~, idx] = ismember(grace_ym, gldas_ym);  % 找到 GRACE 时间在 GLDAS 中的位置

% Step 3: 检查是否全部匹配成功
if any(idx == 0)
    warning('Some GRACE dates not matched in GLDAS!');
end

grid_gldas_template=EWH.GLDAS_NOAH(:,:,idx);


% 原始1°经纬度向量
lon1 = -179.5:1:179.5;    % 360
lat1 = -89.5:1:89.5;      % 180

% 目标0.5°网格
lon2 = -179.75:0.5:179.75;  % 720
lat2 = -89.75:0.5:89.75;    % 360
[LON2, LAT2] = meshgrid(lon2, lat2); % 注意：这里是纬度为行，纬度变化在 y 方向

nmonths = size(grid_gldas_template, 3);
grid_gldas_template_interp=nan(720,360);
for k = 1:nmonths
    grid_gldas_template_interp(:,:,k) = interp2(lon1, lat1, grid_gldas_template(:,:,k)', LON2, LAT2, 'linear')';
end
grid_gldas_template=grid_gldas_template_interp;

nmonths = size(EWH.GLDAS_NOAH(:,:,idx), 3);
grid_gldas_template_interp=nan(720,360);
for k = 1:nmonths
    grid_gldas_template_interp(:,:,k) = interp2(lon1, lat1, EWH.GLDAS_NOAH(:,:,idx(k))', LON2, LAT2, 'linear')';
end
EWH.GLDAS_NOAH=grid_gldas_template_interp;
%% -----------------------------------------------------
%% Step 3: GLDAS滤波 + 从GRACE中扣除周边影响
%% -----------------------------------------------------
methods = {'Gaussian', 'Gaussian_Decorrelation','Fan','Fan_Decorrelation','DDK4','Hankel'};
n_months = 132;
Lmax = 60;window_size=60;p=20;order=6;
grid_interval=0.5;
radius_gaussian = 300;  % km
radius_fan_l = 300;
radius_fan_m = 300;
ddk_type='DDK4';
% === 初始化缓存 cell（并行写入结构体）
n_methods = length(methods);
results = cell(n_methods, n_months);  % 每个 cell 存 11×14 差值

% === parfor 外层时间循环 ===
parfor t = 1:n_months
    grid_gldas = grid_gldas_template(:,:,t);
    Ts_local = Ts;  % 避免广播变量错误
    temp_result = cell(1, n_methods);  % 当前时间点每种方法结果
    for i = 1:n_methods
        method = methods{i};
        switch method
            case 'Gaussian'
                cs = gmt_grid2cs(grid_gldas', Lmax);
                grid_filtered = gmt_cs2grid(cs, radius_gaussian, grid_interval, 'NONE')';
            case 'Fan'
                cs = gmt_grid2cs(grid_gldas',  Lmax);
                cs_filtered = gmt_fan_filter(cs, radius_fan_l, radius_fan_m);
                grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';
            case 'Gaussian_Decorrelation'
                cs = gmt_grid2cs(grid_gldas', Lmax);
                cs_filtered = gmt_gaussian_filter(cs, radius_gaussian);
                grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'CHENP4M6')';
            case 'Fan_Decorrelation'
                cs = gmt_grid2cs(grid_gldas', Lmax);
                cs_filtered = gmt_fan_filter(cs, radius_fan_l, radius_fan_m);
                grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'CHENP4M6')';
            case 'DDK4'
                grid_filtered = DDKs_Filter(grid_gldas, ddk_type, grid_interval);
            case 'Hankel'
                cs = gmt_grid2cs(grid_gldas', Lmax);
                grid_dc = gmt_cs2grid(cs, 0, grid_interval, 'CHENP4M6')';
                Hankel_Mode = HSA(grid_dc, Ts_local, window_size, p, order, buffer);
                grid_filtered = grid_dc - (sum(Hankel_Mode(:,:,1:6),3) - sum(Hankel_Mode(:,:,3:4),3));
        end
        % 扣除泄漏影响
        gldas_t_filtered = grid_filtered(lon_idx, lat_idx);
        diff_ewh = cap_ewh.(method)(:,:,t) - gldas_t_filtered;
        % 保存结果
        temp_result{i} = diff_ewh;
    end
    % 写入全局结果
    results(:, t) = temp_result;
end
% === 合并结果到 cap_ewh.([method '_corr']) 中 ===
methods = {'Gaussian', 'Gaussian_Decorrelation','Fan','Fan_Decorrelation','DDK4','Hankel'};
for i = 1:n_methods
    method = methods{i};
    %cap_ewh.([method '_corr']) = nan(size(cap_x,2), size(cap_y,2), n_months);
    for t = 1:n_months
        cap_ewh.([method '_corr'])(:,:,t) = results{i, t};
    end
end
%% -----------------------------------------------------
%% Step 4: 计算每种滤波方法的 scale factor（1 cm 合成湖泊）
%% -----------------------------------------------------

% === 参数准备 ===
Lmax = 60;window_size=60;p=20;order=6;
radius_gaussian = 300;  % km
radius_fan_l = 300;
radius_fan_m = 300;          % 网格分辨率（1 degree）
destrip = 'CHENP4M6';
ddk_type = 'DDK4';
grid_size = [size(EWH.Gaussian,1), size(EWH.Gaussian,2)];
grid_interval = 0.5;

% === 构造 1 cm 合成输入场 ===
cap_mask_global = zeros(length(csr_lon), length(csr_lat));
ix_start = find(csr_lon == cap_x(1));
ix_end   = find(csr_lon == cap_x(end));
iy_start = find(csr_lat == cap_y(1));
iy_end   = find(csr_lat == cap_y(end));
cap_mask_global(ix_start:ix_end, iy_start:iy_end) = cap_mk';
cap_mask_global(isnan(cap_mask_global)) = 0;
cap_mask_global(cap_mask_global ~= 0) = 1;
cap_mask_global = logical(cap_mask_global);

grid_template = zeros(grid_size);
grid_template(cap_mask_global) = 1;  % Caspian Sea 区域设为 1 cm

% === 初始化输出结构体 ===
SFs = struct();

% === 方法循环 ===
methods = {'Gaussian', 'Gaussian_Decorrelation','Fan','Fan_Decorrelation','DDK4','Hankel'};
for i = 1:length(methods)
    method = methods{i};
    fprintf('Processing method: %s\n', method);

    % Step 1: 网格 → SH 展开
    cs = gmt_grid2cs(grid_template', Lmax);

    % Step 2: 滤波
    switch method
        case 'Gaussian'
            cs_filtered = gmt_gaussian_filter(cs, radius_gaussian);
            grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';

        case 'Fan'
            cs_filtered = gmt_fan_filter(cs, radius_fan_l, radius_fan_m);
            grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';

        case 'Gaussian_Decorrelation'
            cs_destrip = gmt_destriping(cs, destrip);
            cs_filtered = gmt_gaussian_filter(cs_destrip, radius_gaussian);
            grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';

        case 'Fan_Decorrelation'
            cs_destrip = gmt_destriping(cs, destrip);
            cs_filtered = gmt_fan_filter(cs_destrip, radius_fan_l, radius_fan_m);
            grid_filtered = gmt_cs2grid(cs_filtered, 0, grid_interval, 'NONE')';

        case 'DDK4'
            grid_filtered = DDKs_Filter(grid_template, ddk_type, 0.5);
            grid_filtered = grid_filtered;

        case 'Hankel'
            grid_dc = gmt_cs2grid(cs, 0, grid_interval, 'CHENP4M6')';
            Hankel_Mode = HSA(grid_dc, Ts, window_size, p, order, buffer);
            grid_filtered = grid_dc - (sum(Hankel_Mode(:,:,1:6),3) - sum(Hankel_Mode(:,:,3:4),3));
    end

    % Step 3: 区域平均并求尺度因子
    filtered_mean = mean(grid_filtered(cap_mask_global), 'omitnan');
    SFs.(method) = 1.0 / filtered_mean;
    fprintf('SF (%s) = %.3f\n', method, SFs.(method));
end

disp('==== Final Scale Factors ====');
disp(SFs);

%% -----------------------------------------------------
%% Step 5: 应用尺度因子后的GRACE平均时间序列构建
%% Step 6: 与测高数据对比、绘图、计算指标（R, RMSE）
%% -----------------------------------------------------
methods = {'Gaussian', 'Gaussian_Decorrelation','Fan','Fan_Decorrelation','DDK4','Hankel'};
colors = lines(length(methods));  % 自动配色

figure; hold on; box on; grid on;

% 绘制测高时间序列
plot(dates, csl_alt_interp_combined, 'k--o', 'LineWidth', 1.8, ...
     'DisplayName', 'Altimetry (Combined)', 'MarkerSize', 5, ...
     'MarkerFaceColor', 'w', 'MarkerEdgeColor', 'k');

% 初始化结果存储
R_all = struct();
RMSE_all = struct();

% 绘制每种滤波结果
for i = 1:length(methods)
    method = methods{i};
    [~, ~, ~, ~, caps.(['time_series_', method]), caps.(['b_', method])] = Basin_Analysis(cap_ewh.([method '_corr']).*cap_mk', years(idx_range)', cap_x, cap_y);

    ts = caps.(['time_series_', method]).*SFs.(method);

    % 绘图：线型+颜色统一
    plot(dates, ts, '-', 'LineWidth', 1.8, ...
        'DisplayName', method, 'Color', colors(i, :));

    % 相关系数
    R_all.(method) = corr(ts(:), csl_alt_interp_combined(:), 'rows', 'complete');

    % 均方根误差
    RMSE_all.(method) = sqrt(mean((ts(:) - csl_alt_interp_combined(:)).^2));
end

% 图例
legend('Location', 'northeast', 'FontName', 'Times New Roman', ...
    'FontSize', 12, 'FontWeight', 'bold', 'Box', 'on', 'LineWidth', 1.2,'Interpreter','none');

% 标题和坐标轴
title('Caspian Sea Level Change by Altimeter and GRACE TWSA by SF LC', ...
    'FontName', 'Times New Roman', 'FontSize', 14, 'FontWeight', 'bold');

ylabel('CSL (cm)', 'FontSize', 13, 'FontWeight', 'bold', 'FontName', 'Times New Roman');
% 坐标刻度字体设置
set(gca, 'FontName', 'Times New Roman', 'FontSize', 12, ...
    'LineWidth', 1.2, 'XGrid', 'on', 'YGrid', 'on');

% 横坐标时间格式美化
datetick('x', 'yyyy', 'keeplimits');  % 按年份显示，保持范围不变
xtickformat('yyyy-MM-dd');                % 如果支持中文显示

% 打印指标结果
fprintf('\n%-25s | %-6s | %-6s\n', 'Method', 'R', 'RMSE');
fprintf('--------------------------------------------\n');
for i = 1:length(methods)
    method = methods{i};
    fprintf('%-25s | %.2f | %.2f\n', method, R_all.(method), RMSE_all.(method));
end


%% 统计信息输出


methods = {'Gaussian', 'Gaussian_Decorrelation','Fan','Fan_Decorrelation','DDK4','Hankel'};

% Altimetry 时间向量
t_decimal = year(dates) + (month(dates)-0.5)/12;
t_base = t_decimal(:);

% 构建设计矩阵
X = [ones(length(t_base), 1), ...
     t_base, ...
     cos(2*pi*t_base), sin(2*pi*t_base), ...
     cos(4*pi*t_base), sin(4*pi*t_base)];

% 最小二乘拟合
beta = X \ csl_alt_interp_combined(:);
Y_fit = X * beta;
residual = csl_alt_interp_combined(:) - Y_fit;

% 提取统计信息
trend = beta(2);
annual_amp = hypot(beta(3), beta(4));
semiannual_amp = hypot(beta(5), beta(6));

% 打印 Altimetry 结果
fprintf('\n%-25s | AnnualAmp | SemiAmp | Trend\n', 'Method');
fprintf('---------------------------------------------------------------\n');
fprintf('%-25s | %9.2f | %8.2f | %6.2f \n', ...
    'Altimetry (CS + KBG)', annual_amp, semiannual_amp, trend);

% GRACE 方法遍历
for i = 1:length(methods)
    method = methods{i};
    [~, ~, ~, ~, caps.(['time_series_', method]), caps.(['b_', method])] = ...
        Basin_Analysis(cap_ewh.([method]).*cap_mk', years(idx_range)', cap_x, cap_y);

    ts = caps.(['time_series_', method]) .* SFs.(method);

    t_decimal = years(start_idx:end_idx);
    t_base = t_decimal(:);

    X = [ones(length(t_base), 1), ...
         t_base, ...
         cos(2*pi*t_base), sin(2*pi*t_base), ...
         cos(4*pi*t_base), sin(4*pi*t_base)];

    beta = X \ ts(:);
    Y_fit = X * beta;
    residual = ts(:) - Y_fit;

    trend = beta(2);
    annual_amp = hypot(beta(3), beta(4));
    semiannual_amp = hypot(beta(5), beta(6));

    fprintf('%-25s | %9.2f | %8.2f | %6.2f \n', ...
        method, annual_amp, semiannual_amp, trend);
end

%% 绘制不同滤波方法里海EWH时间序列
filter_methods = {'Gaussian','Gaussian_Decorrelation','Fan','Fan_Decorrelation','DDK4','Hankel'};
colors = lines(length(filter_methods));
% 按方法循环，计算区域平均时间序列与年周期分解
for i = 1:length(filter_methods)
    method = filter_methods{i};
    if method == "Hankel"
        idx_range = 1:time_size;
    else
        idx_range = start_idx:end_idx;
    end
    cap_ewh.(method) = EWH.(method)(find(csr_lon==cap_x(1)):find(csr_lon==cap_x(end)), find(csr_lat==cap_y(1)):find(csr_lat==cap_y(end)), idx_range);
    [~, ~, ~, ~, caps.(['time_series_', method]), caps.(['b_', method])] = Basin_Analysis(cap_ewh.(method).*cap_mk', years(idx_range)', cap_x, cap_y);
end

%% 绘制 GRACE 不同滤波方法区域平均结果
figure; hold on; box on; grid on;

% 绘制测高时间序列
plot(dates, csl_alt_interp_combined, 'k--o', 'LineWidth', 1.8, ...
     'DisplayName', 'Altimetry (Combined)', 'MarkerSize', 5, ...
     'MarkerFaceColor', 'w', 'MarkerEdgeColor', 'k');
for i = 1:length(filter_methods)
    method = filter_methods{i};
    plot(dates, caps.(['time_series_', method]), 'LineWidth', 1.5, 'DisplayName', method, 'Color', colors(i,:));
end
% 图例
legend('Location', 'northeast', 'FontName', 'Times New Roman', ...
    'FontSize', 12, 'FontWeight', 'bold', 'Box', 'on', 'LineWidth', 1.2,'Interpreter','none');

% 标题和坐标轴
title('Caspian Sea Level Change by Altimeter and GRACE TWSA by SF LC', ...
    'FontName', 'Times New Roman', 'FontSize', 14, 'FontWeight', 'bold');

ylabel('CSL (cm)', 'FontSize', 13, 'FontWeight', 'bold', 'FontName', 'Times New Roman');
% 坐标刻度字体设置
set(gca, 'FontName', 'Times New Roman', 'FontSize', 12, ...
    'LineWidth', 1.2, 'XGrid', 'on', 'YGrid', 'on');

% 横坐标时间格式美化
datetick('x', 'yyyy', 'keeplimits');  % 按年份显示，保持范围不变
xtickformat('yyyy-MM');                % 如果支持中文显示