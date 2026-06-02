function CCmap = metrics_cc_map_from_stack(A, B, lonVec, latVec, minCount)
%METRICS_CC_MAP_FROM_STACK Correlation map between stacks A and B.
% A,B: [nLon x nLat x Nt] (or [nLat x nLon x Nt]) with NaNs allowed.

    if nargin < 5 || isempty(minCount); minCount = 10; end

    nLon = numel(lonVec);
    nLat = numel(latVec);

    if isequal(size(A,1), nLat) && isequal(size(A,2), nLon)
        A = permute(A, [2,1,3]);
    end
    if isequal(size(B,1), nLat) && isequal(size(B,2), nLon)
        B = permute(B, [2,1,3]);
    end

    if size(A,1) ~= nLon || size(A,2) ~= nLat
        error('A grid size mismatch.');
    end
    if size(B,1) ~= nLon || size(B,2) ~= nLat
        error('B grid size mismatch.');
    end
    Nt = size(A,3);
    if size(B,3) ~= Nt
        error('A and B must have same Nt.');
    end

    a = reshape(A, [], Nt);
    b = reshape(B, [], Nt);

    v = isfinite(a) & isfinite(b);
    n = sum(v, 2);

    CC = nan(size(n));

    ok = n >= minCount;
    if any(ok)
        sumA  = sum(a  .* v, 2);
        sumB  = sum(b  .* v, 2);
        sumA2 = sum(a.^2 .* v, 2);
        sumB2 = sum(b.^2 .* v, 2);
        sumAB = sum(a .* b .* v, 2);

        muA = sumA ./ n;
        muB = sumB ./ n;

        denom = max(n-1, 1);
        covAB = (sumAB - n .* muA .* muB) ./ denom;
        varA  = (sumA2 - n .* (muA.^2)) ./ denom;
        varB  = (sumB2 - n .* (muB.^2)) ./ denom;

        CC(ok) = covAB(ok) ./ sqrt(varA(ok) .* varB(ok) + eps);
    end

    CCmap = reshape(CC, [nLon, nLat]);
end
