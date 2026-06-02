function G = leakage_build_unit_field(mask, unit_mm, mass_mode)
%LEAKAGE_BUILD_UNIT_FIELD Build synthetic unit field (mm) within mask.
%
% mass_mode:
%   'none'            -> outside mask is 0
%   'global_zero_mean'-> outside mask is constant so that global mean is 0

    if nargin < 2 || isempty(unit_mm); unit_mm = 10; end
    if nargin < 3 || isempty(mass_mode); mass_mode = 'none'; end

    mask = logical(mask);
    G = zeros(size(mask));
    G(mask) = unit_mm;

    switch lower(mass_mode)
        case 'none'
            % do nothing
        case 'global_zero_mean'
            n_in  = sum(mask(:));
            n_out = numel(mask) - n_in;
            if n_out <= 0
                return;
            end
            mean_in = mean(G(mask), 'omitnan');
            % choose constant outside so that global mean is zero
            c_out = -mean_in * (n_in / n_out);
            G(~mask) = c_out;
        otherwise
            error('Unknown mass_mode: %s', mass_mode);
    end
end
