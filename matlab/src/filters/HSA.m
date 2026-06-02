function Grid_mode = HSA(Grid_unfiltered, Ts, window_size, p, order, buffer)
%HSA Hankel Spectrum Analysis with robust bidirectional sliding windows.
% Keeps the same formulation but skips invalid windows to avoid NaN rows.

if nargin < 6 || isempty(buffer)
    buffer = 1;
end
if nargin < 5 || isempty(order)
    order = 6;
end

nLon = size(Grid_unfiltered, 1);
nLat = size(Grid_unfiltered, 2);
nT = size(Grid_unfiltered, 3);
Grid_mode = zeros(nLon, nLat, order, 'like', Grid_unfiltered);

for t = 1:nT
    for j = 1:nLat
        x = Grid_unfiltered(:, j, t);
        Ysum = zeros(order, nLon, 'like', Grid_unfiltered);
        w = zeros(1, nLon);

        % Forward windows
        for s = 1:buffer:(nLon - window_size + 1)
            idx = s:(s + window_size - 1);
            [Y, ok] = hsaf_rc_window(x(idx), Ts, p, order);
            if ~ok
                continue;
            end
            Ysum(:, idx) = Ysum(:, idx) + Y;
            w(idx) = w(idx) + 1;
        end

        % Backward windows
        for e = nLon:-buffer:window_size
            idx = (e - window_size + 1):e;
            [Y, ok] = hsaf_rc_window(x(idx), Ts, p, order);
            if ~ok
                continue;
            end
            Ysum(:, idx) = Ysum(:, idx) + Y;
            w(idx) = w(idx) + 1;
        end

        valid = w > 0;
        for n = 1:order
            if any(valid)
                Ysum(n, valid) = Ysum(n, valid) ./ w(valid);
            end
            Ysum(n, ~valid) = 0;
        end

        Grid_mode(:, j, :) = Ysum.';
    end
end
end

function [Y, ok] = hsaf_rc_window(x, Ts, p, order)
%HSAF_RC_WINDOW Run H_RCs on one window with finite-value guards.
    ok = false;
    Y = [];

    if any(~isfinite(x))
        x = fillmissing(x, 'linear', 'EndValues', 'nearest');
        x(~isfinite(x)) = 0;
    end

    try
        [~, ~, ~, ~, Y, ~] = H_RCs(x, Ts, p, order);
    catch
        return;
    end

    if isempty(Y) || size(Y,1) < order || any(~isfinite(Y(:)))
        return;
    end
    ok = true;
end
% function Grid_mode = HSA(Grid_unfiltered, Ts, window_size, p, order, buffer)
% % Hankel Spectrum Analysis (HSA) with Bidirectional Sliding Window
% % This function extracts meridional striping noise using HSA with a 
% % bidirectional sliding window approach.
% 
% % 鍒濆鍖栨护娉㈠悗缁撴灉
% Grid_mode = zeros(size(Grid_unfiltered,1), size(Grid_unfiltered,2), order);
% 
% for t = 1:size(Grid_unfiltered, 3)  % 閬嶅巻鏃堕棿姝?
%     for i = 1:size(Grid_unfiltered, 1)  % 閬嶅巻缁忓害鏂瑰悜
%         x1 = Grid_unfiltered(i, :, t);  % 鍙栨煇涓€鍒楋紙缁忓悜淇″彿锛?
%         Y1 = zeros(order, size(Grid_unfiltered, 2));  % 瀛樺偍涓嶅悓妯℃€佺殑婊ゆ尝缁撴灉
%         weight_sum = zeros(1, size(Grid_unfiltered, 2));  % 璁板綍姣忎釜鐐圭疮鍔犳潈閲?
% 
%         % **鍙岃竟婊戝姩绐楀彛澶勭悊**
%         % 浠庡ご閮ㄥ紑濮嬫粦鍔?(Forward pass)
%         for start_idx = 1:buffer:(size(Grid_unfiltered, 2) - window_size + 1)
%             x1_slice = x1(start_idx:(start_idx + window_size - 1));
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order); % Hankel 澶勭悊
%             % 鍙犲姞鍒?Y1锛屽苟璁板綍鏉冮噸
%             for n = 1:order
%                 Y1(n, start_idx:(start_idx + window_size - 1)) = ...
%                     Y1(n, start_idx:(start_idx + window_size - 1)) + Y(n, :);
%             end
%             weight_sum(start_idx:(start_idx + window_size - 1)) = ...
%                 weight_sum(start_idx:(start_idx + window_size - 1)) + 1;
%         end
% 
%         % 浠庡熬閮ㄥ紑濮嬫粦鍔?(Backward pass)
%         for end_idx = size(Grid_unfiltered, 2):-buffer:(window_size)
%             x1_slice = x1((end_idx - window_size + 1):end_idx);
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order);
%             % 鍙犲姞鍒?Y1锛屽苟璁板綍鏉冮噸
%             for n = 1:order
%                 Y1(n, (end_idx - window_size + 1):end_idx) = ...
%                     Y1(n, (end_idx - window_size + 1):end_idx) + Y(n, :);
%             end
%             weight_sum((end_idx - window_size + 1):end_idx) = ...
%                 weight_sum((end_idx - window_size + 1):end_idx) + 1;
%         end
% 
%         % **骞冲潎鍖栧鐞?*
%         for n = 1:order
%             valid_idx = weight_sum > 0;  % 閬垮厤闄ら浂閿欒
%             Y1(n, valid_idx) = Y1(n, valid_idx) ./ weight_sum(valid_idx);
%         end
% 
%         % 瀛樺叆鏈€缁堢粨鏋?
%         Grid_mode(i, :, :) = Y1';
%     end
% end
% end


% function Grid_mode = HSA(Grid_unfiltered, Ts, p,order, buffer)
% % === Hankel Spectrum Analysis with latitude-dependent window length ===
% %
% % INPUTS
% %   Grid_unfiltered : [lat, lon, time] grid
% %   Ts              : sampling interval (1 for 1掳 grid)
% %   p               : Hankel row dimension
% %   order           : # of RCs to output (鍥哄畾鍗冲彲)
% %   buffer          : sliding-step (e.g. round(N/4))
% %
% % OUTPUT
% %   Grid_mode       : [lat, lon, order] meridional RCs   (t 鍙彟瀛?
% 
% [lat_size, lon_size, time_steps] = size(Grid_unfiltered);
% 
% %% -------- 1. 鐢熸垚绾害-渚濊禆绐楀彛闀垮害琛?-------------------------
% % 杩欓噷鍋囪绾害鎸?-89.5:1:+89.5 鎺掑垪锛岃鍙?lat=1 鏄?-89.5掳
% lat_deg = -90 + (0:lat_size-1) + 0.5;          % 琛屼腑蹇冪含搴?
% window_size_map = arrayfun(@(phi) ...
%     adaptive_N(phi), lat_deg);                 % 閫愮含搴﹀喅瀹?N
% 
% %% -------- 2. 涓诲惊鐜?-----------------------------------------
% Grid_mode = zeros(lat_size, lon_size, order);  % 浠呭瓨 RCs锛屾湰娆″拷鐣?t
% 
% for t = 1:time_steps
%     for j = 1:lon_size                       % 瀵规瘡涓€缁忓害鍒?
%         x_full = Grid_unfiltered(:, j, t);
% 
%         % 棰勫垎閰嶆湰鍒?RC 绱姞鐭╅樀
%         Y_all  = zeros(order, lat_size);
%         w_sum  = zeros(1,   lat_size);
% 
%         % -------- 鍙屽悜婊戝姩锛欶orward pass --------
%         start_idx = 1;
%         while start_idx <= lat_size
%             N = window_size_map(start_idx);       % 鍙栧ご鏍肩含搴︾殑 N
%             % pL = adaptive_p(N);     
%             if start_idx+N-1 > lat_size, break; end
%             x_slice = x_full(start_idx:start_idx+N-1);
% 
%             [~,~,~,~, Y, ~] = H_RCs(x_slice, Ts, p, order);
% 
%             Y_all(:, start_idx:start_idx+N-1) = Y_all(:, start_idx:start_idx+N-1) + Y;
%             w_sum (  start_idx:start_idx+N-1) = w_sum (  start_idx:start_idx+N-1) + 1;
% 
%             start_idx = start_idx + max(1, round(N/buffer)); % 姝ラ暱闅?N
%         end
% 
%         % -------- 鍙嶅悜婊戝姩锛欱ackward pass --------
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
%         % -------- 骞冲潎鍖?--------
%         valid = w_sum > 0;
%         Y_all(:, valid) = Y_all(:, valid) ./ w_sum(valid);
% 
%         % -------- 鍐欏叆缁撴灉 --------
%         Grid_mode(:, j, :) = Y_all.';
%     end
% end
% end   % ===== 鍑芥暟缁撴潫 =====
% 
% %% -------- 3. 鑷畾涔?N-P 鏄犲皠鍑芥暟 -------------------------------
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
% % 鍒濆鍖栨护娉㈠悗缁撴灉
% Grid_mode = zeros(360, 180, order);
% 
% for t = 1:size(Grid_unfiltered, 3)  % 閬嶅巻鏃堕棿姝?
%     for i = 1:size(Grid_unfiltered, 2)  % 閬嶅巻缁忓害鏂瑰悜
%         x1 = Grid_unfiltered(:, i, t);  % 鍙栨煇涓€鍒楋紙缁忓悜淇″彿锛?
%         Y1 = zeros(order, size(Grid_unfiltered, 1));  % 瀛樺偍涓嶅悓妯℃€佺殑婊ゆ尝缁撴灉
%         weight_sum = zeros(1, size(Grid_unfiltered, 1));  % 璁板綍姣忎釜鐐圭疮鍔犳潈閲?
% 
%         % **鍙岃竟婊戝姩绐楀彛澶勭悊**
%         % 浠庡ご閮ㄥ紑濮嬫粦鍔?(Forward pass)
%         for start_idx = 1:buffer:(size(Grid_unfiltered, 1) - window_size + 1)
%             x1_slice = x1(start_idx:(start_idx + window_size - 1));
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order); % Hankel 澶勭悊
%             % 鍙犲姞鍒?Y1锛屽苟璁板綍鏉冮噸
%             for n = 1:order
%                 Y1(n, start_idx:(start_idx + window_size - 1)) = ...
%                     Y1(n, start_idx:(start_idx + window_size - 1)) + Y(n, :);
%             end
%             weight_sum(start_idx:(start_idx + window_size - 1)) = ...
%                 weight_sum(start_idx:(start_idx + window_size - 1)) + 1;
%         end
% 
%         % 浠庡熬閮ㄥ紑濮嬫粦鍔?(Backward pass)
%         for end_idx = size(Grid_unfiltered, 1):-buffer:(window_size)
%             x1_slice = x1((end_idx - window_size + 1):end_idx);
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, order);
% 
%             % 鍙犲姞鍒?Y1锛屽苟璁板綍鏉冮噸
%             for n = 1:order
%                 Y1(n, (end_idx - window_size + 1):end_idx) = ...
%                     Y1(n, (end_idx - window_size + 1):end_idx) + Y(n, :);
%             end
%             weight_sum((end_idx - window_size + 1):end_idx) = ...
%                 weight_sum((end_idx - window_size + 1):end_idx) + 1;
%         end
% 
%         % **骞冲潎鍖栧鐞?*
%         for n = 1:order
%             valid_idx = weight_sum > 0;  % 閬垮厤闄ら浂閿欒
%             Y1(n, valid_idx) = Y1(n, valid_idx) ./ weight_sum(valid_idx);
%         end
% 
%         % 瀛樺叆鏈€缁堢粨鏋?
%         Grid_mode(:, i, :) = Y1';
%     end
% end
% end


%% VER 3.0
% function Grid_filtered= HSA(Grid_unfiltered, Ts, window_size, p, buffer)
% % Hankel Spectrum Analysis (HSA) with Adaptive Order Selection Based on Latitude
% % This function applies a bidirectional sliding window with latitude-based order adjustment.
% 
% % 鍒濆鍖栨护娉㈠悗缁撴灉
% [lon_size, lat_size, time_steps] = size(Grid_unfiltered);
% Grid_filtered = zeros(lon_size, lat_size);  % 鍙栨渶澶?order 纭繚瀛樺偍瓒冲鐨勬ā鎬?
% 
% % 瀹氫箟绾害瀵瑰簲鐨?order
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
% % 閬嶅巻鏃堕棿姝?
% for t = 1:time_steps  
%     for i = 1:lat_size  % 閬嶅巻缁忓害鏂瑰悜
%         x1 = Grid_unfiltered(:, i, t);  % 鍙栨煇涓€鍒楋紙缁忓悜淇″彿锛?
%         Y1 = zeros(max([4,6,8,10]), lon_size);  % 瀛樺偍婊ゆ尝鍚庣殑淇″彿
%         weight_sum = zeros(1, lon_size);  % 璁板綍姣忎釜鐐圭殑绱姞鏉冮噸
% 
%         % **鍙岃竟婊戝姩绐楀彛澶勭悊**
%         % 浠庡ご閮ㄥ紑濮嬫粦鍔?(Forward pass)
%         for start_idx = 1:buffer:(lon_size - window_size + 1)
%             local_order = order_map(i);  % 鏍规嵁绾害閫夋嫨 order
%             x1_slice = x1(start_idx:(start_idx + window_size - 1));
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, local_order); % Hankel 澶勭悊
%             % 鍙犲姞鍒?Y1锛屽苟璁板綍鏉冮噸
%             for n = 1:local_order
%                 Y1(n, start_idx:(start_idx + window_size - 1)) = ...
%                     Y1(n, start_idx:(start_idx + window_size - 1)) + Y(n, :);
%             end
%             weight_sum(start_idx:(start_idx + window_size - 1)) = ...
%                 weight_sum(start_idx:(start_idx + window_size - 1)) + 1;
%         end
% 
%         % 浠庡熬閮ㄥ紑濮嬫粦鍔?(Backward pass)
%         for end_idx = lon_size:-buffer:(window_size)
%             local_order = order_map(i);
%             x1_slice = x1((end_idx - window_size + 1):end_idx);
%             [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, local_order);
%             % 鍙犲姞鍒?Y1锛屽苟璁板綍鏉冮噸
%             for n = 1:local_order
%                 Y1(n, (end_idx - window_size + 1):end_idx) = ...
%                     Y1(n, (end_idx - window_size + 1):end_idx) + Y(n, :);
%             end
%             weight_sum((end_idx - window_size + 1):end_idx) = ...
%                 weight_sum((end_idx - window_size + 1):end_idx) + 1;
%         end
% 
%         % **骞冲潎鍖栧鐞?*
%         valid_idx = weight_sum > 0;  % 閬垮厤闄ら浂閿欒
%         Y1(:, valid_idx) = Y1(:, valid_idx) ./ weight_sum(valid_idx);
% 
%         % **妯℃€佺瓫閫?*
%         Y_filtered = zeros(lon_size, 1);
% 
%         local_order = order_map(i);
%         if local_order == 4
%             Y_noise=Y1(1,:)+Y1(4,:);
%             Y_filtered=Grid_unfiltered(:,i,t)-Y_noise';
%             %Y_filtered = sum(Y1(2:3, :));  % 淇濈暀鎵€鏈夋ā鎬?
%         elseif local_order == 6
%             Y_noise=Y1(1,:)+Y1(2,:)+Y1(5,:)+Y1(6,:);
%             Y_filtered=Grid_unfiltered(:,i,t)-Y_noise';
%             %Y_filtered = sum(Y1(3:4, :));  % 淇濈暀 3,4 妯℃€?
%         % elseif local_order == 8
%         %     Y_noise=Y1(1,:)+Y1(2,:)+Y1(7,:)+Y1(8,:);
%         %     Y_filtered=Grid_unfiltered(:,i,t)-Y_noise';
%              % Y_filtered = sum(Y1(4:6, :));  % 淇濈暀 3,4,5,6 妯℃€?
%         % elseif local_order == 10
%         %     Y_filtered = sum(Y1(4:6, :));  % 淇濈暀 4,5,6,7 妯℃€?
%         end
% 
% 
%         % 瀛樺叆鏈€缁堢粨鏋?
%         Grid_filtered(:, i, t) = Y_filtered;
%     end
% end
% end

%% VER 4.0

% function Grid_filtered = HSA(Grid_unfiltered, Ts, window_size, p, buffer)
% % Hankel Spectrum Analysis (HSA) with Fixed Order per Latitude Band
% % This function applies a bidirectional sliding window with fixed order per latitude.
% 
% % 鍒濆鍖栨护娉㈠悗缁撴灉
% [lon_size, lat_size, time_steps] = size(Grid_unfiltered);
% Grid_filtered = zeros(lon_size, lat_size, time_steps);
% 
% % 鍋囪 lon_size = 360
% if lon_size ~= 360
%     warning('lon_size is not 360, please verify the input dimensions.');
% end
% 
% % 閬嶅巻鏃堕棿姝?
% parfor t = 1:time_steps  
%     for i = 1:lat_size  % 閬嶅巻绾害鏂瑰悜
%         x1 = Grid_unfiltered(:, i, t);  % 鍙栨煇涓€鍒楋紙缁忓悜淇″彿锛?
%         Y_filtered_full = zeros(lon_size, 1);  % 瀛樺偍璇ョ含搴﹀甫鐨勬渶缁堟护娉俊鍙?
%         weight_sum = zeros(1, lon_size);       % 璁板綍姣忎釜鐐圭殑绱姞鏉冮噸
%         % 纭畾璇ョ含搴﹀甫鐨勫浐瀹歰rder锛堝熀浜庢暣涓獂1淇″彿锛?
%         % 鍙岃竟婊戝姩绐楀彛澶勭悊
%         % 浠庡ご閮ㄥ紑濮嬫粦鍔?(Forward pass)
%         for start_idx = 1:buffer:(lon_size - window_size + 1)
%             x1_slice = x1(start_idx:(start_idx + window_size - 1));
%             local_order = determine_order(x1_slice,p);
%             fprintf('Latitude %d, local_order = %d\n', i, local_order); % 璋冭瘯淇℃伅
%             try
%                 [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, local_order); % 浣跨敤鍥哄畾order
%                 % 绔嬪嵆杩涜妯℃€佺粍鍚堜笌婊ゆ尝
%                 [Y_noise, Y_filtered] = modal_combination(Y, local_order, x1_slice);
%                 % 鍙犲姞鍒板叏灞€婊ゆ尝缁撴灉
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
%         % 浠庡熬閮ㄥ紑濮嬫粦鍔?(Backward pass)
%         for end_idx = lon_size:-buffer:(window_size)
%             x1_slice = x1((end_idx - window_size + 1):end_idx);
%             local_order = determine_order(x1_slice,p);
%             try
%                 [~, ~, ~, ~, Y, ~] = H_RCs(x1_slice, Ts, p, local_order);
%                 % 绔嬪嵆杩涜妯℃€佺粍鍚堜笌婊ゆ尝
%                 [Y_noise, Y_filtered] = modal_combination(Y, local_order, x1_slice);
%                 % 鍙犲姞鍒板叏灞€婊ゆ尝缁撴灉
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
%         % 骞冲潎鍖栧鐞?
%         valid_idx = weight_sum > 0;  % 閬垮厤闄ら浂閿欒
%         Y_filtered_full(valid_idx) = Y_filtered_full(valid_idx) ./ weight_sum(valid_idx)';
% 
%         % 瀛樺叆鏈€缁堢粨鏋?
%         Grid_filtered(:, i, t) = Y_filtered_full;
%     end
% end
% end
% 
% % 鑷€傚簲order閫夋嫨鍑芥暟锛堝熀浜庢暣涓含搴﹀甫淇″彿锛?
% function order = determine_order(x,p)
%     % 鏋勫缓Hankel鐭╅樀
%     N=length(x);
%     L=N+1-p;
%     H=hankel(x(1:L), x(L:N));
% 
%     % 濂囧紓鍊煎垎瑙?
%     [~, S, ~] = svd(H);
%     singular_values = diag(S);
% 
%     % 鑷€傚簲閫夋嫨order锛堝寮傚€?0.001锛?
%     order = sum(singular_values > 0.01);
%     % 闄愬埗order涓嶈秴杩噖indow_size鐨勪竴鍗婏紝涓斾笉瓒呰繃10锛堟牴鎹敊璇彁绀猴級
%     order = min(order, 10);
%     order = max(order, 3);  % 鑷冲皯淇濈暀1涓ā鎬?
% end
% 
% 
% % function order = determine_order(x)
% %     % 鏋勫缓Hankel鐭╅樀
% %     N = length(x);
% %     L = floor(N / 2);  % 绐楀彛闀垮害
% %     K = N - L + 1;     % 鍒楁暟
% %     H = zeros(L, K);
% %     for i = 1:L
% %         H(i, :) = x(i:i+K-1)';
% %     end
% % 
% %     % 濂囧紓鍊煎垎瑙?
% %     [~, S, ~] = svd(H, 'econ');
% %     singular_values = diag(S);
% % 
% %     % 鑷€傚簲閫夋嫨order锛堝寮傚€?0.001锛?
% %     order = sum(singular_values > 0.001);
% %     order = min(order, min(L, K));  % 纭繚涓嶈秴杩囩煩闃电淮搴?
% %     order = max(order, 1);          % 鑷冲皯淇濈暀1涓ā鎬?
% % end
% 
% 
% % 妯℃€佺粍鍚堜笌婊ゆ尝鍑芥暟
% function [Y_noise, Y_filtered] = modal_combination(Y, local_order, x_slice)
%     % 杈撳叆Y鐨勭淮搴︿负 local_order 脳 window_size
%     % 鏍规嵁local_order缁勫悎鍣０妯℃€?
%     % if local_order >= 7
%     %     Y_noise = sum(Y([1:3, 7:8], :), 1)';  % 鍣０妯℃€侊細1,2,3,6,7
%     % elseif local_order == 6
%     %     Y_noise = sum(Y([1:2, 5:6], :), 1)';  % 鍣０妯℃€侊細1,2,5,6
%     % else
%     %     Y_noise = Y(1, :)' + Y(4, :)';        % 鍣０妯℃€侊細1,4
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
%     % 璁＄畻婊ゆ尝淇″彿
%     Y_filtered = x_slice - Y_noise;
% end
% % 
% % % 鍘熸湁鐨凥_RCs鍑芥暟
% % function [Amp, alfa, freq, theta, Y, Ex] = H_RCs(x, Ts, p, k)
% %     % Harmonic reconstruction components
% %     [Amp, alfa, freq, theta, Ex] = HTLS_PM(x, Ts, p, k);
% %     [freq, ix] = sort(freq); % 鎸夌収棰戠巼杩涜鎺掑簭
% %     Amp = Amp(ix);   % 鎸箙
% %     alfa = alfa(ix); % 琛板噺鍥犲瓙
% %     theta = theta(ix); % 鐩镐綅
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
% %HSA_Auto  Fully self鈥慳daptive Hankel Spectrum Analysis filter for GRACE striping鈥憂oise removal.
% %
% %   [Grid_filtered] = HSA_Auto(Grid_unfiltered, Ts, buffer, energy_thres, ...)
% %
% %   INPUTS
% %       Grid_unfiltered : 3鈥慏 array [lat, lon, time] 鈥?raw gridded field
% %       Ts              : sampling interval in grid points (default 1)
% %       buffer          : sliding鈥憌indow stride divisor (default 4 鈫?step鈮圢/4)
% %       energy_thres    : cumulative SV energy for order selection (0.99)
% %       k_min, k_max    : lower/upper bounds for order k   (3,10)
% %
% %   OUTPUT
% %       Grid_filtered   : same size as input, stripe鈥憂oise filtered
% %
% %   The routine automatically adapts
% %          鈥?window length  N  (latitude dependent)
% %          鈥?Hankel row dim p  (鈮?.4路N)
% %          鈥?decomposition order k  (SV energy threshold)
% %   and performs a bidirectional sliding鈥憌indow average.
% %
% %   --------------------------------------------------------------------
% %   Author : ChatGPT鈥慓RACE helper  |  v1.0  |  2025鈥?7鈥?1
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
% % ---- latitude鈥慸ependent window length ---------------------------------
% lat_deg = -90 + (0:lat_size-1) + 0.5;          % row鈥慶entre latitudes
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
%             Y  = slice_HSA(x_slice, Ts, pL, kL);           % RCs (kL脳N)
%             y_filt = combine_modes(x_slice, Y, kL);        % noise鈥憆emoved slice
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
% % latitude鈥慸ependent window length (1掳 grid)
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
% % row dimension p 鈮?0.4路N, bounded
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
% % return k脳N RC matrix for a slice
% [~,~,~,~,Y,~] = H_RCs(x, Ts, p, k);
% end
% 
% function y_filt = combine_modes(x_slice, Y, k)
% % simple 20 % high鈥慺requency truncation
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
% [RD,ED,UD]=svd(D12); %瀵瑰簲YEV
% U12=UD(1:k,k+1:k+k);
% U22=UD(k+1:k+k,k+1:k+k);
% fai=-U12*pinv(U22);%U12鍗充负W12
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
% ck=Z\x; %h涓篶k锛?x涓鸿緭鍏ュ簭鍒楋紝Z涓?
% 
% Amp=abs(ck); %鎸箙
% theta=atan2(imag(ck), real(ck));%鐩镐綅
% end
