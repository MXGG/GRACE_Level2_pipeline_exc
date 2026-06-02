function ewh = inv_synthesize_ewh_fast(SH, syn)
%INV_SYNTHESIZE_EWH_FAST Synthesize EWH grid from SH coefficients using precomputed basis.
%
% Inputs:
%   SH.C, SH.S size (Lmax+1)x(Lmax+1)
%   syn from inv_prepare_synthesis()
%
% Output:
%   ewh size (nLon x nLat) in cfg.grid.unit (as used in syn.scale)
%
% Optimized: Fully vectorized using pagemtimes (R2020b+) or fallback loop.

    C = SH.C;
    S = SH.S;

    Lmax = syn.Lmax;
    if size(C,1) < Lmax+1 || size(S,1) < Lmax+1
        error('SH degree smaller than syn.Lmax.');
    end

    Pnm  = syn.Pnm;     % (Lmax+1) x (Lmax+1) x nLat
    cosM = syn.cosM;    % (Lmax+1) x nLon
    sinM = syn.sinM;    % (Lmax+1) x nLon
    loveN = syn.loveN;  % (Lmax+1) x 1 or 1 x (Lmax+1)
    scale = syn.scale;

    nLat = numel(syn.latVec);
    nLon = numel(syn.lonVec);
    L1 = Lmax + 1;
    
    % Ensure loveN is a row vector for matrix multiply
    loveN = loveN(:)';  % 1 x (L+1)
    
    % Truncate C and S to L1 x L1 if needed
    C = C(1:L1, 1:L1);
    S = S(1:L1, 1:L1);
    
    % ==== OPTIMIZED VERSION ====
    % Use pagemtimes if available (MATLAB R2020b+), otherwise use optimized loop
    
    use_pagemtimes = exist('pagemtimes', 'builtin') || exist('pagemtimes', 'file');
    
    if use_pagemtimes
        % Vectorized using pagemtimes for batch matrix operations
        % Pnm: (L+1) x (L+1) x nLat
        
        % Expand C, S to 3D and compute A, B
        C3 = repmat(C, [1, 1, nLat]);
        S3 = repmat(S, [1, 1, nLat]);
        
        A = Pnm .* C3;  % (L+1) x (L+1) x nLat
        B = Pnm .* S3;  % (L+1) x (L+1) x nLat
        
        % Compute T = A * cosM + B * sinM for each latitude
        % cosM, sinM: (L+1) x nLon, need to expand to 3D
        cosM3 = repmat(cosM, [1, 1, nLat]);  % (L+1) x nLon x nLat
        sinM3 = repmat(sinM, [1, 1, nLat]);
        
        % Use pagemtimes: result is (L+1) x nLon x nLat
        T = pagemtimes(A, cosM3) + pagemtimes(B, sinM3);
        
        % Apply love numbers and scale
        % T is (L+1) x nLon x nLat, loveN is 1 x (L+1)
        % ewh(lat, lon) = scale * sum_l [loveN(l) * T(l, lon, lat)]
        loveN3 = repmat(loveN', [1, nLon, nLat]);  % (L+1) x nLon x nLat
        ewh_3d = scale * sum(loveN3 .* T, 1);  % 1 x nLon x nLat
        ewh = permute(squeeze(ewh_3d), [2, 1]);  % nLat x nLon
        ewh = ewh.'; % return nLon x nLat
        
    else
        % Fallback: optimized loop with precomputed products
        % Precompute PC = P .* C and PS = P .* S for all latitudes
        % Then single matrix multiply per latitude
        
        ewh = zeros(nLat, nLon);
        
        % Precompute loveN scaled
        loveN_scaled = scale * loveN;  % 1 x (L+1)
        
        for ii = 1:nLat
            P = Pnm(:,:,ii);
            % Compute A = P .* C, B = P .* S
            A = P .* C;
            B = P .* S;
            % T = A * cosM + B * sinM: (L+1) x nLon
            T = A * cosM + B * sinM;
            % Apply love numbers: ewh(ii,:) = loveN_scaled * T
            ewh(ii,:) = loveN_scaled * T;
        end
        ewh = ewh.'; % return nLon x nLat
    end
end
