function grid_ddk_filter = DDKs_Filter(grid_ddk_unfiltered, type_filter, resolution, ddk_data_dir)
%DDKS_FILTER Apply DDK filter using GRACE-filter-master kernel matrices.
%
% grid_ddk_unfiltered : [nLon x nLat x Nt] or coefficient grid
% type_filter        : 'DDK1' .. 'DDK8'
% resolution         : grid spacing in degrees
% ddk_data_dir       : path to GRACE-filter-master/data/DDK

    if nargin < 4 || isempty(ddk_data_dir)
        rootDir = fileparts(fileparts(fileparts(mfilename('fullpath'))));
        ddk_data_dir = fullfile(rootDir, 'src', 'tools', 'GRACE-filter-master', 'data', 'DDK');
        if ~exist(ddk_data_dir, 'dir')
            if ~isempty(getenv('IFILES'))
                ddk_data_dir = fullfile(getenv('IFILES'), 'GRACE-filter-master', 'data', 'DDK');
            end
        end
        if ~exist(ddk_data_dir, 'dir')
            error('DDK data directory not found. Configure cfg.filter.ddk.data_dir or IFILES.');
        end
    end

    switch type_filter
        case 'DDK1'
            path = fullfile(ddk_data_dir,'Wbd_2-120.a_1d14p_4');
        case 'DDK2'
            path = fullfile(ddk_data_dir,'Wbd_2-120.a_1d13p_4');
        case 'DDK3'
            path = fullfile(ddk_data_dir,'Wbd_2-120.a_1d12p_4');
        case 'DDK4'
            path = fullfile(ddk_data_dir,'Wbd_2-120.a_5d11p_4');
        case 'DDK5'
            path = fullfile(ddk_data_dir,'Wbd_2-120.a_1d11p_4');
        case 'DDK6'
            path = fullfile(ddk_data_dir,'Wbd_2-120.a_5d10p_4');
        case 'DDK7'
            path = fullfile(ddk_data_dir,'Wbd_2-120.a_1d10p_4');
        case 'DDK8'
            path = fullfile(ddk_data_dir,'Wbd_2-120.a_5d9p_4');
        otherwise
            error('Unknown DDK type: %s', type_filter);
    end

    lmax = 60;
    W = read_BIN(path);
    cs_res = grid_ddk_unfiltered;
    for ii = 1:size(grid_ddk_unfiltered,3)
        sc = gmt_cs2sc(reshape(cs_res(ii,:,:), [lmax+1 lmax+1]));
        s = sc(:,1:lmax+1);
        s(:,end) = 0;
        s = fliplr(s);
        c = sc(:,61:end);
        [c_filt,s_filt] = filterSH(W, c, s);
        s_filt = fliplr(s_filt);
        sc_filt = [s_filt(:,1:end-1), c_filt];
        cs_filt = gmt_sc2cs(sc_filt);
        cs_res(ii,:,:) = cs_filt;
    end

    grid_ddk_filter = permute(gmt_cs2grid(cs_res, 0, resolution, 'NONE'), [2,1,3]);
end
