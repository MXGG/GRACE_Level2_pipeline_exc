function [Dc_f, Ds_f, meta] = filter_sh_p4m6(Dc, Ds, Lmax, poly_deg, m_start)
%FILTER_SH_P4M6 Decorrelation filter PnMm (e.g., P4M6).
%
% Typical setting:
%   poly_deg = 4, m_start = 6  => P4M6
%
% Algorithm (common GRACE destriping approach):
%   For each order m >= m_start, separately for even/odd degrees:
%       Fit a polynomial of degree poly_deg to C(l,m) and S(l,m) vs degree l,
%       then subtract the fitted trend from the coefficients.
%
% Optimized: Reduced function call overhead, vectorized polynomial fitting.

    Dc_f = Dc;
    Ds_f = Ds;

    is3 = ndims(Dc) == 3;
    if is3
        Nt = size(Dc,3);
    else
        Nt = 1;
    end
    
    % Precompute degree indices for even/odd at each order
    % This avoids repeated computation inside loops
    order_data = cell(Lmax - m_start + 1, 1);
    for m = m_start:Lmax
        l_all = m:Lmax;
        idx_m = m - m_start + 1;
        
        % Even degrees
        l_even = l_all(mod(l_all, 2) == 0);
        % Odd degrees
        l_odd = l_all(mod(l_all, 2) == 1);
        
        order_data{idx_m} = struct(...
            'm', m, ...
            'col', m + 1, ...
            'l_even', l_even, ...
            'l_odd', l_odd, ...
            'need_even', numel(l_even) >= (poly_deg + 2), ...
            'need_odd', numel(l_odd) >= (poly_deg + 2));
    end

    for it = 1:Nt
        if is3
            C = Dc(:,:,it);
            S = Ds(:,:,it);
        else
            C = Dc;
            S = Ds;
        end

        % Process each order
        for idx_m = 1:numel(order_data)
            od = order_data{idx_m};
            col = od.col;
            
            % Even degrees
            if od.need_even
                [C, S] = remove_poly_trend_batch(C, S, od.l_even, col, poly_deg);
            end
            
            % Odd degrees
            if od.need_odd
                [C, S] = remove_poly_trend_batch(C, S, od.l_odd, col, poly_deg);
            end
        end

        if is3
            Dc_f(:,:,it) = C;
            Ds_f(:,:,it) = S;
        else
            Dc_f = C;
            Ds_f = S;
        end
    end

    meta = struct();
    meta.type = sprintf('P%dM%d', poly_deg, m_start);
    meta.poly_deg = poly_deg;
    meta.m_start = m_start;
end

function [C, S] = remove_poly_trend_batch(C, S, l, col, poly_deg)
%REMOVE_POLY_TREND_BATCH Remove polynomial trend from both C and S matrices.
% Optimized: Process C and S together with shared x values.

    x = l(:);
    y_c = C(l+1, col);
    y_s = S(l+1, col);

    % Find valid (non-NaN) indices - use union of both valid sets
    good_c = isfinite(y_c);
    good_s = isfinite(y_s);
    
    % Process C
    if any(good_c)
        x_c = x(good_c);
        y_c_valid = y_c(good_c);
        if numel(x_c) >= (poly_deg + 2)
            p_c = polyfit(x_c, y_c_valid, poly_deg);
            yfit_c = polyval(p_c, x_c);
            lgood_c = l(good_c);
            C(lgood_c+1, col) = C(lgood_c+1, col) - yfit_c;
        end
    end
    
    % Process S
    if any(good_s)
        x_s = x(good_s);
        y_s_valid = y_s(good_s);
        if numel(x_s) >= (poly_deg + 2)
            p_s = polyfit(x_s, y_s_valid, poly_deg);
            yfit_s = polyval(p_s, x_s);
            lgood_s = l(good_s);
            S(lgood_s+1, col) = S(lgood_s+1, col) - yfit_s;
        end
    end
end
