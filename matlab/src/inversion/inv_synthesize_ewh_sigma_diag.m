function [ewhSigma, ewhVar] = inv_synthesize_ewh_sigma_diag(sigmaC, sigmaS, syn)
%INV_SYNTHESIZE_EWH_SIGMA_DIAG Propagate SH formal errors to grid EWH sigma.
% Assumptions:
%   - diagonal-only variance propagation (no coefficient covariance)
%   - sigmaC/sigmaS are std of SH coefficients in C(l+1,m+1)/S(l+1,m+1)
%
% Output:
%   ewhSigma: [nLon x nLat], same linear unit as syn.scale
%   ewhVar  : [nLon x nLat], squared unit

    Lmax = syn.Lmax;
    L1 = Lmax + 1;
    if size(sigmaC,1) < L1 || size(sigmaS,1) < L1
        error('sigma degree smaller than syn.Lmax.');
    end

    sigmaC = sigmaC(1:L1, 1:L1);
    sigmaS = sigmaS(1:L1, 1:L1);

    % Replace missing values and enforce no S-term for m=0.
    sigmaC(~isfinite(sigmaC)) = 0;
    sigmaS(~isfinite(sigmaS)) = 0;
    sigmaS(:,1) = 0;

    sigmaC2 = sigmaC.^2;
    sigmaS2 = sigmaS.^2;

    Pnm = syn.Pnm;      % (L+1) x (L+1) x nLat
    cosM2 = syn.cosM.^2; % (L+1) x nLon
    sinM2 = syn.sinM.^2; % (L+1) x nLon

    loveN2 = (syn.loveN(:)').^2; % 1 x (L+1)
    scale2 = syn.scale^2;

    nLat = numel(syn.latVec);
    nLon = numel(syn.lonVec);
    ewhVarLatLon = zeros(nLat, nLon);

    for ii = 1:nLat
        P2 = Pnm(:,:,ii).^2; % (L+1) x (L+1)
        varC = (P2 .* sigmaC2) * cosM2; % (L+1) x nLon
        varS = (P2 .* sigmaS2) * sinM2; % (L+1) x nLon
        ewhVarLatLon(ii,:) = scale2 * (loveN2 * (varC + varS));
    end

    ewhVarLatLon(ewhVarLatLon < 0) = 0;
    ewhVar = ewhVarLatLon.';        % nLon x nLat
    ewhSigma = sqrt(ewhVar);
end
