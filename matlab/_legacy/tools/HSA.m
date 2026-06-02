function Grid_mode = HSA(Grid_unfiltered, Ts, window_size, p, order, buffer)
% Hankel Spectrum Analysis (HSA) with Bidirectional Sliding Window
% This function extracts meridional striping noise using HSA with a 
% bidirectional sliding window approach.

% 初始化滤波后结果
Grid_mode = zeros(size(Grid_unfiltered,1), size(Grid_unfiltered,2), order);

for t = 1:size(Grid_unfiltered, 3)  % 遍历时间步
    for i = 1:size(Grid_unfiltered, 2)  % 遍历经度方向
        x1 = Grid_unfiltered(:, i, t);  % 取某一列（经向信号）
        Y1 = zeros(order, size(Grid_unfiltered, 1));  % 存储不同模态的滤波结果
        weight_sum = zeros(1, size(Grid_unfiltered, 1));  % 记录每个点累加权重

        % **双边滑动窗口处理**
        % 从头部开始滑动 (Forward pass)
        for start_idx = 1:buffer:(size(Grid_unfiltered, 1) - window_size + 1)
            x1_slice = x1(start_idx:(start_idx + window_size - 1));
            [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order); % Hankel 处理
            % 叠加到 Y1，并记录权重
            for n = 1:order
                Y1(n, start_idx:(start_idx + window_size - 1)) = ...
                    Y1(n, start_idx:(start_idx + window_size - 1)) + Y(n, :);
            end
            weight_sum(start_idx:(start_idx + window_size - 1)) = ...
                weight_sum(start_idx:(start_idx + window_size - 1)) + 1;
        end

        % 从尾部开始滑动 (Backward pass)
        for end_idx = size(Grid_unfiltered, 1):-buffer:(window_size)
            x1_slice = x1((end_idx - window_size + 1):end_idx);
            [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order);
            % 叠加到 Y1，并记录权重
            for n = 1:order
                Y1(n, (end_idx - window_size + 1):end_idx) = ...
                    Y1(n, (end_idx - window_size + 1):end_idx) + Y(n, :);
            end
            weight_sum((end_idx - window_size + 1):end_idx) = ...
                weight_sum((end_idx - window_size + 1):end_idx) + 1;
        end

        % **平均化处理**
        for n = 1:order
            valid_idx = weight_sum > 0;  % 避免除零错误
            Y1(n, valid_idx) = Y1(n, valid_idx) ./ weight_sum(valid_idx);
        end

        % 存入最终结果
        Grid_mode(:, i, :) = Y1';
    end
end
end
% function Grid_mode = HSA(Grid_unfiltered, Ts, window_size, p, order, buffer)
% % Hankel Spectrum Analysis (HSA) with Bidirectional Sliding Window
% % This function extracts meridional striping noise using HSA with a 
% % bidirectional sliding window approach.
% 
% % 初始化滤波后结果
% Grid_mode = zeros(size(Grid_unfiltered,1), size(Grid_unfiltered,2), order);
% 
% for t = 1:size(Grid_unfiltered, 3)  % 遍历时间步
%     for i = 1:size(Grid_unfiltered, 1)  % 遍历经度方向
%         x1 = Grid_unfiltered(i, :, t);  % 取某一列（经向信号）
%         Y1 = zeros(order, size(Grid_unfiltered, 2));  % 存储不同模态的滤波结果
%         weight_sum = zeros(1, size(Grid_unfiltered, 2));  % 记录每个点累加权重
% 
%         % **双边滑动窗口处理**
%         % 从头部开始滑动 (Forward pass)
%         for start_idx = 1:buffer:(size(Grid_unfiltered, 2) - window_size + 1)
%             x1_slice = x1(start_idx:(start_idx + window_size - 1));
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order); % Hankel 处理
%             % 叠加到 Y1，并记录权重
%             for n = 1:order
%                 Y1(n, start_idx:(start_idx + window_size - 1)) = ...
%                     Y1(n, start_idx:(start_idx + window_size - 1)) + Y(n, :);
%             end
%             weight_sum(start_idx:(start_idx + window_size - 1)) = ...
%                 weight_sum(start_idx:(start_idx + window_size - 1)) + 1;
%         end
% 
%         % 从尾部开始滑动 (Backward pass)
%         for end_idx = size(Grid_unfiltered, 2):-buffer:(window_size)
%             x1_slice = x1((end_idx - window_size + 1):end_idx);
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order);
%             % 叠加到 Y1，并记录权重
%             for n = 1:order
%                 Y1(n, (end_idx - window_size + 1):end_idx) = ...
%                     Y1(n, (end_idx - window_size + 1):end_idx) + Y(n, :);
%             end
%             weight_sum((end_idx - window_size + 1):end_idx) = ...
%                 weight_sum((end_idx - window_size + 1):end_idx) + 1;
%         end
% 
%         % **平均化处理**
%         for n = 1:order
%             valid_idx = weight_sum > 0;  % 避免除零错误
%             Y1(n, valid_idx) = Y1(n, valid_idx) ./ weight_sum(valid_idx);
%         end
% 
%         % 存入最终结果
%         Grid_mode(i, :, :) = Y1';
%     end
% end
% end


% function Grid_mode = HSA(Grid_unfiltered, Ts, p,order, buffer)
% % === Hankel Spectrum Analysis with latitude-dependent window length ===
% %
% % INPUTS
% %   Grid_unfiltered : [lat, lon, time] grid
% %   Ts              : sampling interval (1 for 1° grid)
% %   p               : Hankel row dimension
% %   order           : # of RCs to output (固定即可)
% %   buffer          : sliding-step (e.g. round(N/4))
% %
% % OUTPUT
% %   Grid_mode       : [lat, lon, order] meridional RCs   (t 可另存)
% 
% [lat_size, lon_size, time_steps] = size(Grid_unfiltered);
% 
% %% -------- 1. 生成纬度-依赖窗口长度表 -------------------------
% % 这里假设纬度按 -89.5:1:+89.5 排列，行号 lat=1 是 -89.5°
% lat_deg = -90 + (0:lat_size-1) + 0.5;          % 行中心纬度
% window_size_map = arrayfun(@(phi) ...
%     adaptive_N(phi), lat_deg);                 % 逐纬度决定 N
% 
% %% -------- 2. 主循环 -----------------------------------------
% Grid_mode = zeros(lat_size, lon_size, order);  % 仅存 RCs，本次忽略 t
% 
% for t = 1:time_steps
%     for j = 1:lon_size                       % 对每一经度列
%         x_full = Grid_unfiltered(:, j, t);
% 
%         % 预分配本列 RC 累加矩阵
%         Y_all  = zeros(order, lat_size);
%         w_sum  = zeros(1,   lat_size);
% 
%         % -------- 双向滑动：Forward pass --------
%         start_idx = 1;
%         while start_idx <= lat_size
%             N = window_size_map(start_idx);       % 取头格纬度的 N
%             % pL = adaptive_p(N);     
%             if start_idx+N-1 > lat_size, break; end
%             x_slice = x_full(start_idx:start_idx+N-1);
% 
%             [~,~,~,~, Y, ~] = H_RCs(x_slice, Ts, p, order);
% 
%             Y_all(:, start_idx:start_idx+N-1) = Y_all(:, start_idx:start_idx+N-1) + Y;
%             w_sum (  start_idx:start_idx+N-1) = w_sum (  start_idx:start_idx+N-1) + 1;
% 
%             start_idx = start_idx + max(1, round(N/buffer)); % 步长随 N
%         end
% 
%         % -------- 反向滑动：Backward pass --------
%         end_idx = lat_size;
%         while end_idx >= 1
%             N = window_size_map(end_idx);
%             % pL = adaptive_p(N);     
%             if end_idx-N+1 < 1, break; end
%             x_slice = x_full(end_idx-N+1:end_idx);
% 
%             [~,~,~,~, Y, ~] = H_RCs(x_slice, Ts, p, order);
% 
%             Y_all(:, end_idx-N+1:end_idx) = Y_all(:, end_idx-N+1:end_idx) + Y;
%             w_sum (  end_idx-N+1:end_idx) = w_sum (  end_idx-N+1:end_idx) + 1;
% 
%             end_idx = end_idx - max(1, round(N/buffer));
%         end
% 
%         % -------- 平均化 --------
%         valid = w_sum > 0;
%         Y_all(:, valid) = Y_all(:, valid) ./ w_sum(valid);
% 
%         % -------- 写入结果 --------
%         Grid_mode(:, j, :) = Y_all.';
%     end
% end
% end   % ===== 函数结束 =====
% 
% %% -------- 3. 自定义 N-P 映射函数 -------------------------------
% function N = adaptive_N(phi)
% % phi: latitude in degree
% absphi = abs(phi);
% if absphi <= 20
%     N = 48;
% elseif absphi <= 40
%     N = 42;
% elseif absphi <= 60
%     N = 32;
% else
%     N = 24;
% end
% end

%% VER 2.0

% function Grid_mode = HSA(Grid_unfiltered, Ts, window_size, p, order, buffer)
% % Hankel Spectrum Analysis (HSA) with Bidirectional Sliding Window
% % This function extracts meridional striping noise using HSA with a
% % bidirectional sliding window approach.
% 
% % 初始化滤波后结果
% Grid_mode = zeros(360, 180, order);
% 
% for t = 1:size(Grid_unfiltered, 3)  % 遍历时间步
%     for i = 1:size(Grid_unfiltered, 2)  % 遍历经度方向
%         x1 = Grid_unfiltered(:, i, t);  % 取某一列（经向信号）
%         Y1 = zeros(order, size(Grid_unfiltered, 1));  % 存储不同模态的滤波结果
%         weight_sum = zeros(1, size(Grid_unfiltered, 1));  % 记录每个点累加权重
% 
%         % **双边滑动窗口处理**
%         % 从头部开始滑动 (Forward pass)
%         for start_idx = 1:buffer:(size(Grid_unfiltered, 1) - window_size + 1)
%             x1_slice = x1(start_idx:(start_idx + window_size - 1));
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order); % Hankel 处理
%             % 叠加到 Y1，并记录权重
%             for n = 1:order
%                 Y1(n, start_idx:(start_idx + window_size - 1)) = ...
%                     Y1(n, start_idx:(start_idx + window_size - 1)) + Y(n, :);
%             end
%             weight_sum(start_idx:(start_idx + window_size - 1)) = ...
%                 weight_sum(start_idx:(start_idx + window_size - 1)) + 1;
%         end
% 
%         % 从尾部开始滑动 (Backward pass)
%         for end_idx = size(Grid_unfiltered, 1):-buffer:(window_size)
%             x1_slice = x1((end_idx - window_size + 1):end_idx);
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order);
% 
%             % 叠加到 Y1，并记录权重
%             for n = 1:order
%                 Y1(n, (end_idx - window_size + 1):end_idx) = ...
%                     Y1(n, (end_idx - window_size + 1):end_idx) + Y(n, :);
%             end
%             weight_sum((end_idx - window_size + 1):end_idx) = ...
%                 weight_sum((end_idx - window_size + 1):end_idx) + 1;
%         end
% 
%         % **平均化处理**
%         for n = 1:order
%             valid_idx = weight_sum > 0;  % 避免除零错误
%             Y1(n, valid_idx) = Y1(n, valid_idx) ./ weight_sum(valid_idx);
%         end
% 
%         % 存入最终结果
%         Grid_mode(:, i, :) = Y1';
%     end
% end
% end


%% VER 3.0
% function Grid_filtered= HSA(Grid_unfiltered, Ts, window_size, p, buffer)
% % Hankel Spectrum Analysis (HSA) with Adaptive Order Selection Based on Latitude
% % This function applies a bidirectional sliding window with latitude-based order adjustment.
% 
% % 初始化滤波后结果
% [lon_size, lat_size, time_steps] = size(Grid_unfiltered);
% Grid_filtered = zeros(lon_size, lat_size);  % 取最大 order 确保存储足够的模态
% 
% % 定义纬度对应的 order
% order_map = zeros(lat_size, 1);
% for lat = 1:lat_size
%     if lat <= 20 || lat >= 161
%         order_map(lat) = 4;
%     elseif (lat > 20 && lat <= 40) || (lat >= 141 && lat < 161)
%         order_map(lat) = 6;
%     elseif (lat > 40 && lat <= 60) || (lat >= 121 && lat < 141)
%         order_map(lat) = 6;
%     else
%         order_map(lat) = 6;
%     end
% end
% 
% % 遍历时间步
% for t = 1:time_steps  
%     for i = 1:lat_size  % 遍历经度方向
%         x1 = Grid_unfiltered(:, i, t);  % 取某一列（经向信号）
%         Y1 = zeros(max([4,6,8,10]), lon_size);  % 存储滤波后的信号
%         weight_sum = zeros(1, lon_size);  % 记录每个点的累加权重
% 
%         % **双边滑动窗口处理**
%         % 从头部开始滑动 (Forward pass)
%         for start_idx = 1:buffer:(lon_size - window_size + 1)
%             local_order = order_map(i);  % 根据纬度选择 order
%             x1_slice = x1(start_idx:(start_idx + window_size - 1));
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, local_order); % Hankel 处理
%             % 叠加到 Y1，并记录权重
%             for n = 1:local_order
%                 Y1(n, start_idx:(start_idx + window_size - 1)) = ...
%                     Y1(n, start_idx:(start_idx + window_size - 1)) + Y(n, :);
%             end
%             weight_sum(start_idx:(start_idx + window_size - 1)) = ...
%                 weight_sum(start_idx:(start_idx + window_size - 1)) + 1;
%         end
% 
%         % 从尾部开始滑动 (Backward pass)
%         for end_idx = lon_size:-buffer:(window_size)
%             local_order = order_map(i);
%             x1_slice = x1((end_idx - window_size + 1):end_idx);
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, local_order);
%             % 叠加到 Y1，并记录权重
%             for n = 1:local_order
%                 Y1(n, (end_idx - window_size + 1):end_idx) = ...
%                     Y1(n, (end_idx - window_size + 1):end_idx) + Y(n, :);
%             end
%             weight_sum((end_idx - window_size + 1):end_idx) = ...
%                 weight_sum((end_idx - window_size + 1):end_idx) + 1;
%         end
% 
%         % **平均化处理**
%         valid_idx = weight_sum > 0;  % 避免除零错误
%         Y1(:, valid_idx) = Y1(:, valid_idx) ./ weight_sum(valid_idx);
% 
%         % **模态筛选**
%         Y_filtered = zeros(lon_size, 1);
% 
%         local_order = order_map(i);
%         if local_order == 4
%             Y_noise=Y1(1,:)+Y1(4,:);
%             Y_filtered=Grid_unfiltered(:,i,t)-Y_noise';
%             %Y_filtered = sum(Y1(2:3, :));  % 保留所有模态
%         elseif local_order == 6
%             Y_noise=Y1(1,:)+Y1(2,:)+Y1(5,:)+Y1(6,:);
%             Y_filtered=Grid_unfiltered(:,i,t)-Y_noise';
%             %Y_filtered = sum(Y1(3:4, :));  % 保留 3,4 模态
%         % elseif local_order == 8
%         %     Y_noise=Y1(1,:)+Y1(2,:)+Y1(7,:)+Y1(8,:);
%         %     Y_filtered=Grid_unfiltered(:,i,t)-Y_noise';
%              % Y_filtered = sum(Y1(4:6, :));  % 保留 3,4,5,6 模态
%         % elseif local_order == 10
%         %     Y_filtered = sum(Y1(4:6, :));  % 保留 4,5,6,7 模态
%         end
% 
% 
%         % 存入最终结果
%         Grid_filtered(:, i, t) = Y_filtered;
%     end
% end
% end

%% VER 4.0

% function Grid_filtered = HSA(Grid_unfiltered, Ts, window_size, p, buffer)
% % Hankel Spectrum Analysis (HSA) with Fixed Order per Latitude Band
% % This function applies a bidirectional sliding window with fixed order per latitude.
% 
% % 初始化滤波后结果
% [lon_size, lat_size, time_steps] = size(Grid_unfiltered);
% Grid_filtered = zeros(lon_size, lat_size, time_steps);
% 
% % 假设 lon_size = 360
% if lon_size ~= 360
%     warning('lon_size is not 360, please verify the input dimensions.');
% end
% 
% % 遍历时间步
% parfor t = 1:time_steps  
%     for i = 1:lat_size  % 遍历纬度方向
%         x1 = Grid_unfiltered(:, i, t);  % 取某一列（经向信号）
%         Y_filtered_full = zeros(lon_size, 1);  % 存储该纬度带的最终滤波信号
%         weight_sum = zeros(1, lon_size);       % 记录每个点的累加权重
%         % 确定该纬度带的固定order（基于整个x1信号）
%         % 双边滑动窗口处理
%         % 从头部开始滑动 (Forward pass)
%         for start_idx = 1:buffer:(lon_size - window_size + 1)
%             x1_slice = x1(start_idx:(start_idx + window_size - 1));
%             local_order = determine_order(x1_slice,p);
%             fprintf('Latitude %d, local_order = %d\n', i, local_order); % 调试信息
%             try
%                 [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, local_order); % 使用固定order
%                 % 立即进行模态组合与滤波
%                 [Y_noise, Y_filtered] = modal_combination(Y, local_order, x1_slice);
%                 % 叠加到全局滤波结果
%                 Y_filtered_full(start_idx:(start_idx + window_size - 1)) = ...
%                     Y_filtered_full(start_idx:(start_idx + window_size - 1)) + Y_filtered;
%                 weight_sum(start_idx:(start_idx + window_size - 1)) = ...
%                     weight_sum(start_idx:(start_idx + window_size - 1)) + 1;
%             catch ME
%                 fprintf('Error at forward pass, start_idx=%d: %s\n', start_idx, ME.message);
%                 rethrow(ME);
%             end
%         end
% 
%         % 从尾部开始滑动 (Backward pass)
%         for end_idx = lon_size:-buffer:(window_size)
%             x1_slice = x1((end_idx - window_size + 1):end_idx);
%             local_order = determine_order(x1_slice,p);
%             try
%                 [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, local_order);
%                 % 立即进行模态组合与滤波
%                 [Y_noise, Y_filtered] = modal_combination(Y, local_order, x1_slice);
%                 % 叠加到全局滤波结果
%                 Y_filtered_full((end_idx - window_size + 1):end_idx) = ...
%                     Y_filtered_full((end_idx - window_size + 1):end_idx) + Y_filtered;
%                 weight_sum((end_idx - window_size + 1):end_idx) = ...
%                     weight_sum((end_idx - window_size + 1):end_idx) + 1;
%             catch ME
%                 fprintf('Error at backward pass, end_idx=%d: %s\n', end_idx, ME.message);
%                 rethrow(ME);
%             end
%         end
% 
%         % 平均化处理
%         valid_idx = weight_sum > 0;  % 避免除零错误
%         Y_filtered_full(valid_idx) = Y_filtered_full(valid_idx) ./ weight_sum(valid_idx)';
% 
%         % 存入最终结果
%         Grid_filtered(:, i, t) = Y_filtered_full;
%     end
% end
% end
% 
% % 自适应order选择函数（基于整个纬度带信号）
% function order = determine_order(x,p)
%     % 构建Hankel矩阵
%     N=length(x);
%     L=N+1-p;
%     H=hankel(x(1:L), x(L:N));
% 
%     % 奇异值分解
%     [~, S, ~] = svd(H);
%     singular_values = diag(S);
% 
%     % 自适应选择order（奇异值>0.001）
%     order = sum(singular_values > 0.01);
%     % 限制order不超过window_size的一半，且不超过10（根据错误提示）
%     order = min(order, 10);
%     order = max(order, 3);  % 至少保留1个模态
% end
% 
% 
% % function order = determine_order(x)
% %     % 构建Hankel矩阵
% %     N = length(x);
% %     L = floor(N / 2);  % 窗口长度
% %     K = N - L + 1;     % 列数
% %     H = zeros(L, K);
% %     for i = 1:L
% %         H(i, :) = x(i:i+K-1)';
% %     end
% % 
% %     % 奇异值分解
% %     [~, S, ~] = svd(H, 'econ');
% %     singular_values = diag(S);
% % 
% %     % 自适应选择order（奇异值>0.001）
% %     order = sum(singular_values > 0.001);
% %     order = min(order, min(L, K));  % 确保不超过矩阵维度
% %     order = max(order, 1);          % 至少保留1个模态
% % end
% 
% 
% % 模态组合与滤波函数
% function [Y_noise, Y_filtered] = modal_combination(Y, local_order, x_slice)
%     % 输入Y的维度为 local_order × window_size
%     % 根据local_order组合噪声模态
%     % if local_order >= 7
%     %     Y_noise = sum(Y([1:3, 7:8], :), 1)';  % 噪声模态：1,2,3,6,7
%     % elseif local_order == 6
%     %     Y_noise = sum(Y([1:2, 5:6], :), 1)';  % 噪声模态：1,2,5,6
%     % else
%     %     Y_noise = Y(1, :)' + Y(4, :)';        % 噪声模态：1,4
%     % end
%     if local_order==3
%         Y_noise=Y(1,:)'+Y(3,:)';
%     elseif local_order==4
%         Y_noise=Y(1,:)'+Y(4,:)';
%     elseif local_order==5
%         Y_noise=sum(Y([1:2,4:5],:),1)';
%     elseif local_order==6
%         Y_noise=sum(Y([1:2,5:6],:),1)';
%     elseif local_order==7
%         Y_noise=sum(Y([1:2,6:7],:),1)';
%     elseif local_order==8
%         Y_noise=sum(Y([1:3,6:8],:),1)';
%     elseif local_order==9
%         Y_noise=sum(Y([1:3,7:9],:),1)';
%     elseif local_order==10
%         Y_noise=sum(Y([1:3,8:10],:),1)';
%     end
%     % 计算滤波信号
%     Y_filtered = x_slice - Y_noise;
% end
% % 
% % % 原有的H_RCs函数
% % function [Amp, alfa, freq, theta, Y, Ex] = H_RCs(x, Ts, p, k)
% %     % Harmonic reconstruction components
% %     [Amp, alfa, freq, theta, Ex] = HTLS_PM(x, Ts, p, k);
% %     [freq, ix] = sort(freq); % 按照频率进行排序
% %     Amp = Amp(ix);   % 振幅
% %     alfa = alfa(ix); % 衰减因子
% %     theta = theta(ix); % 相位
% % 
% %     N = length(x);
% %     n = 0:N-1;
% %     n = repmat(n, [k 1]);
% %     k_exp = exp(repmat(alfa, [1 N]) .* n * Ts);
% %     k_exp(isinf(k_exp)) = realmax * sign(k_exp(isinf(k_exp)));
% %     Y = (repmat(Amp, [1 N]) .* k_exp) .* ...
% %         cos(2*pi*Ts * repmat(freq, [1 N]) .* n + repmat(theta, [1 N]));
% % end

% function [Grid_filtered] = HSA(Grid_unfiltered, Ts, buffer, energy_thres, k_min, k_max)
% %HSA_Auto  Fully self‑adaptive Hankel Spectrum Analysis filter for GRACE striping‑noise removal.
% %
% %   [Grid_filtered] = HSA_Auto(Grid_unfiltered, Ts, buffer, energy_thres, ...)
% %
% %   INPUTS
% %       Grid_unfiltered : 3‑D array [lat, lon, time] – raw gridded field
% %       Ts              : sampling interval in grid points (default 1)
% %       buffer          : sliding‑window stride divisor (default 4 → step≈N/4)
% %       energy_thres    : cumulative SV energy for order selection (0.99)
% %       k_min, k_max    : lower/upper bounds for order k   (3,10)
% %
% %   OUTPUT
% %       Grid_filtered   : same size as input, stripe‑noise filtered
% %
% %   The routine automatically adapts
% %          – window length  N  (latitude dependent)
% %          – Hankel row dim p  (≈0.4·N)
% %          – decomposition order k  (SV energy threshold)
% %   and performs a bidirectional sliding‑window average.
% %
% %   --------------------------------------------------------------------
% %   Author : ChatGPT‑GRACE helper  |  v1.0  |  2025‑07‑11
% %   --------------------------------------------------------------------
% 
% % ---- default arguments ------------------------------------------------
% if nargin < 2 || isempty(Ts),           Ts = 1;      end
% if nargin < 3 || isempty(buffer),       buffer = 1;  end
% if nargin < 4 || isempty(energy_thres), energy_thres = 0.99; end
% if nargin < 5 || isempty(k_min),        k_min = 3;   end
% if nargin < 6 || isempty(k_max),        k_max = 10;  end
% 
% [lat_size, lon_size, time_steps] = size(Grid_unfiltered);
% Grid_filtered = zeros(lat_size, lon_size, time_steps, 'like', Grid_unfiltered);
% 
% % ---- latitude‑dependent window length ---------------------------------
% lat_deg = -90 + (0:lat_size-1) + 0.5;          % row‑centre latitudes
% window_size_map = arrayfun(@adaptive_N, lat_deg);
% 
% % ---- main loop over time & longitude ----------------------------------
% for t = 1:time_steps
%     for j = 1:lon_size
%         x_full  = Grid_unfiltered(:, j, t);
%         y_accum = zeros(lat_size,1, 'like', x_full);   % sum of filtered slices
%         w_sum   = zeros(lat_size,1);                   % #contributions
% 
%         % ---- forward pass ---------------------------------------------
%         idx0 = 1;
%         while idx0 <= lat_size
%             N = window_size_map(idx0);
%             if idx0+N-1 > lat_size, break; end
%             idx = idx0:idx0+N-1;
%             x_slice = x_full(idx);
% 
%             pL = adaptive_p(N);
%             kL = adaptive_k(x_slice, pL, energy_thres, k_min, k_max);
% 
%             Y  = slice_HSA(x_slice, Ts, pL, kL);           % RCs (kL×N)
%             y_filt = combine_modes(x_slice, Y, kL);        % noise‑removed slice
% 
%             y_accum(idx) = y_accum(idx) + y_filt;
%             w_sum(idx)   = w_sum(idx)   + 1;
% 
%             idx0 = idx0 + max(1, round(N/buffer));
%         end
% 
%         % ---- backward pass --------------------------------------------
%         idx1 = lat_size;
%         while idx1 >= 1
%             N = window_size_map(idx1);
%             if idx1-N+1 < 1, break; end
%             idx = idx1-N+1:idx1;
%             x_slice = x_full(idx);
% 
%             pL = adaptive_p(N);
%             kL = adaptive_k(x_slice, pL, energy_thres, k_min, k_max);
% 
%             Y  = slice_HSA(x_slice, Ts, pL, kL);
%             y_filt = combine_modes(x_slice, Y, kL);
% 
%             y_accum(idx) = y_accum(idx) + y_filt;
%             w_sum(idx)   = w_sum(idx)   + 1;
% 
%             idx1 = idx1 - max(1, round(N/buffer));
%         end
% 
%         % ---- normalise & store ----------------------------------------
%         valid = w_sum > 0;
%         y_accum(valid) = y_accum(valid) ./ w_sum(valid);
%         Grid_filtered(:, j, t) = y_accum;
%     end
% end
% 
% end % =================== main function end =============================
% 
% 
% %=======================================================================
% %  Local utility functions
% %=======================================================================
% function N = adaptive_N(phi)
% % latitude‑dependent window length (1° grid)
% absphi = abs(phi);
% if absphi <= 20
%     N = 48;
% elseif absphi <= 40
%     N = 42;
% elseif absphi <= 60
%     N = 32;
% else
%     N = 24;
% end
% end
% 
% function p = adaptive_p(N)
% % row dimension p ≈ 0.4·N, bounded
% p = round(0.4 * N);
% p = max(8, p);
% p = min(N-2, p);
% end
% 
% function k = adaptive_k(x, p, energy_thres, k_min, k_max)
% % choose order k by cumulative SV energy
% N = length(x);
% L = N + 1 - p;
% H = hankel(x(1:L), x(L:N));
% sv = svd(H, 'econ');
% energy = cumsum(sv.^2) / sum(sv.^2);
% k = find(energy >= energy_thres, 1, 'first');
% if isempty(k), k = k_min; end
% k = max(k_min, min([k, k_max, p-1]));
% end
% 
% function Y = slice_HSA(x, Ts, p, k)
% % return k×N RC matrix for a slice
% [~,~,~,~,Y,~] = H_RCs(x, Ts, p, k);
% end
% 
% function y_filt = combine_modes(x_slice, Y, k)
% % simple 20 % high‑frequency truncation
% n_cut = max(1, round(0.2 * k));
% if 2*n_cut >= k
%     keep = ceil(k/2);            % fallback: keep one middle mode
% else
%     keep = (n_cut+1):(k-n_cut);
% end
% noise = sum(Y(setdiff(1:k, keep), :), 1)';
% y_filt = x_slice - noise;
% end
% 
% %=======================================================================
% %  H_RCs & HTLS_PM (parametric harmonic decomposition)
% %=======================================================================
% function [Amp, alfa, freq, theta, Y, Ex] = H_RCs(x, Ts, p, k)
% % Harmonic Reconstruction components (plus RC matrix)
% [Amp, alfa, freq, theta, Ex] = HTLS_PM(x, Ts, p, k);
% [freq, ix] = sort(freq);
% Amp   = Amp(ix);
% alfa  = alfa(ix);
% theta = theta(ix);
% 
% N = length(x);
% n = 0:N-1;
% Nmat = repmat(n, [k 1]);
% Kexp = exp(repmat(alfa, [1 N]) .* Nmat * Ts);
% Kexp(isinf(Kexp)) = realmax * sign(Kexp(isinf(Kexp)));
% Y = (repmat(Amp, [1 N]) .* Kexp) .* cos(2*pi*Ts * repmat(freq,[1 N]).* Nmat + repmat(theta,[1 N]));
% end
% 
% 
% 
% function [Amp, alfa, freq, theta,Ex,Ex_flag]=HTLS_PM(x,Ts,p,k)
% %----Results----
% % {Amp, alfa, freq, theta}
% % Ex-Singular value
% 
% %%
% N=length(x);
% L=N+1-p;
% %X=zeros(L,p);
%  X=hankel(x(1:L), x(L:N));
% X1=hankel(x(1:p),x(p:N));
% [Vx,Ex,Ux]=svd(X1);
% % [Vx,Ex,Ux]=econ(X);
% Ex=diag(Ex);
% Ex_flag=length(find(Ex(:)>0.001));
% Us=Ux(:,1:k);
% 
% [m,n]=size(Ux);
% U1=Us(1:m-1,:);
% U2=Us(2:m,:);
% D12=[U1,U2];
% [RD,ED,UD]=svd(D12); %对应YEV
% U12=UD(1:k,k+1:k+k);
% U22=UD(k+1:k+k,k+1:k+k);
% fai=-U12*pinv(U22);%U12即为W12
% l=eig(fai); %z
% 
% alfa=log(abs(l))/Ts; %% damping factor
% freq=atan2(imag(l), real(l))/(2*pi*Ts);%%  frequency
% 
% %%
% Z=zeros(N,k);
% for i=1: length(l)
%     Z(:, i)= transpose(l(i).^(0: N-1));
% end
% ck=Z\x; %h为ck， x为输入序列，Z为
% 
% Amp=abs(ck); %振幅
% theta=atan2(imag(ck), real(ck));%相位
% end