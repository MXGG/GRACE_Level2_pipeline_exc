function Products = main_compute_products_month(cfg, Tk, SH, syn, plan, Products, lonVec, latVec)
%MAIN_COMPUTE_PRODUCTS_MONTH Compute RAW + spectral filters + HSAF for one month.

    Lmax = cfg.inversion.Lmax;
    C0 = SH.C;
    S0 = SH.S;

    cache = struct();

    pd = cfg.filter.p4m6.poly_deg;
    ms = cfg.filter.p4m6.m_start;
    rGauss = cfg.filter.gaussian.radius_km;
    rFan1 = cfg.filter.fan.radius1_km;
    rFan2 = cfg.filter.fan.radius2_km;
    Ts = mean(diff(lonVec));
    if isfield(cfg,'filter') && isfield(cfg.filter,'hankel')
        if isfield(cfg.filter.hankel,'Ts') && ~isempty(cfg.filter.hankel.Ts)
            Ts = cfg.filter.hankel.Ts;
        elseif isfield(cfg.filter.hankel,'params') && isfield(cfg.filter.hankel.params,'Ts') ...
                && ~isempty(cfg.filter.hankel.params.Ts)
            Ts = cfg.filter.hankel.params.Ts;
        end
    end

    want = struct();
    want.RAW = ismember('RAW', plan.order);
    want.P4M6 = ismember('P4M6', plan.order) || ismember('P4M6_GAUSS', plan.order) || ismember('P4M6_FAN', plan.order);
    want.GAUSS = ismember('GAUSS', plan.order) || ismember('P4M6_GAUSS', plan.order);
    want.FAN = ismember('FAN', plan.order) || ismember('P4M6_FAN', plan.order);
    if isfield(plan, 'ddk_tags') && ~isempty(plan.ddk_tags)
        ddkTags = plan.ddk_tags;
    elseif ismember('DDK', plan.order)
        ddkTags = {'DDK4'};
    else
        ddkTags = {};
    end
    want.DDK = ~isempty(ddkTags);
    want.HSAF = ismember('HSAF', plan.order);

    if want.RAW
        ewh = inv_synthesize_ewh_fast(SH, syn);
        Products.RAW = io_make_product('RAW', Tk, lonVec, latVec, ewh, SH.meta);
    end

    if want.P4M6
        if ~isfield(cache, 'P4M6')
            [C,S,metaF] = filter_sh_p4m6(C0, S0, Lmax, pd, ms);
            cache.P4M6 = struct('C',C,'S',S,'meta',metaF);
        end
        SHp = attach_sh(SH, cache.P4M6);
        if ismember('P4M6', plan.order)
            ewh = inv_synthesize_ewh_fast(SHp, syn);
            Products.P4M6 = io_make_product('P4M6', Tk, lonVec, latVec, ewh, SHp.meta);
        end
    end

    if want.GAUSS
        if ~isfield(cache, 'GAUSS')
            [C,S,metaF] = filter_sh_gaussian(C0, S0, Lmax, rGauss);
            cache.GAUSS = struct('C',C,'S',S,'meta',metaF);
        end
        SHg = attach_sh(SH, cache.GAUSS);
        if ismember('GAUSS', plan.order)
            ewh = inv_synthesize_ewh_fast(SHg, syn);
            Products.GAUSS = io_make_product('GAUSS', Tk, lonVec, latVec, ewh, SHg.meta);
        end
    end

    if want.FAN
        if ~isfield(cache, 'FAN')
            [C,S,metaF] = filter_sh_fan(C0, S0, Lmax, rFan1, rFan2);
            cache.FAN = struct('C',C,'S',S,'meta',metaF);
        end
        SHf = attach_sh(SH, cache.FAN);
        if ismember('FAN', plan.order)
            ewh = inv_synthesize_ewh_fast(SHf, syn);
            Products.FAN = io_make_product('FAN', Tk, lonVec, latVec, ewh, SHf.meta);
        end
    end

    if ismember('P4M6_GAUSS', plan.order)
        if ~isfield(cache, 'P4M6')
            [C,S,metaF] = filter_sh_p4m6(C0, S0, Lmax, pd, ms);
            cache.P4M6 = struct('C',C,'S',S,'meta',metaF);
        end
        [C2,S2,meta2] = filter_sh_gaussian(cache.P4M6.C, cache.P4M6.S, Lmax, rGauss);
        SHx = attach_sh(SH, struct('C',C2,'S',S2,'meta',struct('stage1',cache.P4M6.meta,'stage2',meta2)));
        ewh = inv_synthesize_ewh_fast(SHx, syn);
        Products.P4M6_GAUSS = io_make_product('P4M6_GAUSS', Tk, lonVec, latVec, ewh, SHx.meta);
    end

    if ismember('P4M6_FAN', plan.order)
        if ~isfield(cache, 'P4M6')
            [C,S,metaF] = filter_sh_p4m6(C0, S0, Lmax, pd, ms);
            cache.P4M6 = struct('C',C,'S',S,'meta',metaF);
        end
        [C2,S2,meta2] = filter_sh_fan(cache.P4M6.C, cache.P4M6.S, Lmax, rFan1, rFan2);
        SHx = attach_sh(SH, struct('C',C2,'S',S2,'meta',struct('stage1',cache.P4M6.meta,'stage2',meta2)));
        ewh = inv_synthesize_ewh_fast(SHx, syn);
        Products.P4M6_FAN = io_make_product('P4M6_FAN', Tk, lonVec, latVec, ewh, SHx.meta);
    end

    if want.DDK
        for i = 1:numel(ddkTags)
            tag = ddkTags{i};
            cfgDDK = cfg.filter.ddk;
            cfgDDK.type = tag;
            [C,S,metaF] = filter_sh_ddk(C0, S0, cfgDDK, cfg.path);
            SHd = attach_sh(SH, struct('C',C,'S',S,'meta',metaF));
            ewh = inv_synthesize_ewh_fast(SHd, syn);
            Products.(tag) = io_make_product(tag, Tk, lonVec, latVec, ewh, SHd.meta);
        end
    end

    if want.HSAF
        hin = plan.hankel_input_tag;
        if ~isfield(Products, hin)
            warning('HSAF input "%s" not found; fallback to RAW.', hin);
            hin = 'RAW';
        end
        E0 = Products.(hin).grid.ewh;
        [E1, info] = filter_grid_hsaf(E0, lonVec, latVec, cfg.filter.hankel, Ts);
        metaH = struct('input',hin,'info',info);
        Products.HSAF = io_make_product('HSAF', Tk, lonVec, latVec, E1, metaH);
    end
end

function SHx = attach_sh(SH, filt)
    SHx = SH;
    SHx.C = filt.C;
    SHx.S = filt.S;
    SHx.meta.filter = filt.meta;
end
