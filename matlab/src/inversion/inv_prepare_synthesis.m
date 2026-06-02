function syn = inv_prepare_synthesis(cfg)
%INV_PREPARE_SYNTHESIS Precompute basis for fast EWH synthesis on a regular grid.
%
% syn fields:
%   Lmax, lonVec, latVec
%   Pnm: (Lmax+1)x(Lmax+1)x(nLat)
%   cosM, sinM: (Lmax+1)x(nLon) for m=0..Lmax
%   loveN: 1x(Lmax+1)
%   scale: scalar (unit depends on cfg.grid.unit)

    persistent cache
    if isempty(cache); cache = struct(); end

    Lmax = cfg.inversion.Lmax;
    [lonVec, latVec] = make_lonlat_vec(cfg); % from core/
    key = sprintf('L%d_%d_%d_%s', Lmax, numel(latVec), numel(lonVec), cfg.grid.unit);

    if isfield(cache, key)
        syn = cache.(key);
        return;
    end

    % ---- Love numbers table (load Love number k')
    % Default table used in many GRACE toolchains.
    % You may replace with your own file/table if needed.
    n_loveN  = [0,1,2,3,4,5,6,7,8,9,10,12,15,20,30,40,50,70,100,150,200];
    love_k0  = [0,0.027,-0.303,-0.194,-0.132,-0.104,-0.089,-0.081,-0.076,-0.072,-0.069,-0.064,-0.058,-0.051,-0.040,-0.033,-0.027,-0.020,-0.014,-0.010,-0.007];

    n = 0:Lmax;
    love_k = interp1(n_loveN, love_k0, n, 'linear', 'extrap');
    loveN  = (2*n+1) ./ (1 + love_k); % 1 x (Lmax+1)

    % ---- Scaling
    a      = 6.378136460E+06;  % m
    rho_e  = 5517.0;           % kg/m^3
    rho_w  = 1000.0;           % kg/m^3
    base   = a*rho_e/(3*rho_w); % meters

    switch lower(cfg.grid.unit)
        case {'mmeqh','mmewh','mm'}
            unitFactor = 1000.0; % m -> mm
        case {'cmeqh','cmewh','cm'}
            unitFactor = 100.0;  % m -> cm
        case {'m','meqh','mewh'}
            unitFactor = 1.0;
        otherwise
            warning('Unknown cfg.grid.unit = %s, fallback to mm.', cfg.grid.unit);
            unitFactor = 1000.0;
    end
    scale = base * unitFactor;

    % ---- Trig matrices
    lonRad = deg2rad(lonVec(:).');
    m = (0:Lmax).';
    cosM = cos(m * lonRad);
    sinM = sin(m * lonRad);

    % ---- Legendre matrices (normalized, real form for C/S)
    % Use internal fast generator compatible with real SH (m=0 -> 1, m>0 -> sqrt(2)).
    Pnm = inv_legendre_real_norm(Lmax, latVec);

    syn = struct();
    syn.Lmax = Lmax;
    syn.lonVec = lonVec;
    syn.latVec = latVec;
    syn.Pnm = Pnm;
    syn.cosM = cosM;
    syn.sinM = sinM;
    syn.loveN = loveN;
    syn.scale = scale;

    cache.(key) = syn;
end

function Pnm = inv_legendre_real_norm(Lmax, latVec)
% Fully-normalized associated Legendre + real SH factor.
% Pnm(l+1,m+1,ilat) where m<=l.

    latVec = latVec(:);
    kk = numel(latVec);
    Theta = 90 - latVec;  % colatitude (deg)
    x = cosd(Theta);

    Pnm = zeros(Lmax+1, Lmax+1, kk);

    for l = 0:Lmax
        cy = legendre(l, x.', 'norm'); % (m+1) x kk
        for m = 0:l
            row = squeeze(cy(m+1,:)); % 1 x kk
            if m == 0
                fac = 1.0;
            else
                fac = sqrt(2.0);
            end
            Pnm(l+1, m+1, :) = reshape(row * fac, [1 1 kk]);
        end
    end
end
