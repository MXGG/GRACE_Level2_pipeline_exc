function global_coast = build_global_coast_auto(globalgrid, lonVec, latVec, LAT_ORDER_IN_MATRIX)
%BUILD_GLOBAL_COAST_AUTO Auto-align a 360x720 land mask to lon/lat vectors.
% Output: global_coast (nLon x nLat), 1=land, 0=ocean

    G = double(globalgrid);
    if any(size(G) ~= [360, 720])
        error('globalgrid size is %dx%d, expected 360x720.', size(G,1), size(G,2));
    end

    G0 = G > 0.5; % binarize

    tests = [
        10.25   20.25   1;
        300.25  -5.25   1;
        135.25  -25.25  1;
        90.25   30.25   1;
        320.25  72.25   1;
        200.25   0.25   0;
        240.25  -30.25  0;
        330.25   0.25   0;
        80.25   -20.25  0;
    ];

    nlon = numel(lonVec);
    latAsc = latVec(:);
    if strcmpi(LAT_ORDER_IN_MATRIX, 'desc')
        latUse = flipud(latAsc);
    else
        latUse = latAsc;
    end

    ix = zeros(size(tests,1),1);
    iy = zeros(size(tests,1),1);
    for k = 1:size(tests,1)
        [~, ix(k)] = min(abs(lonVec - tests(k,1)));
        [~, iy(k)] = min(abs(latUse - tests(k,2)));
    end
    yExpected = logical(tests(:,3));

    bestScore = -inf;
    best = struct('flipLat',0,'flipLon',0,'shift',0,'invert',0);

    for flipLat = 0:1
        for flipLon = 0:1
            A = G0;
            if flipLat, A = flipud(A); end
            if flipLon, A = fliplr(A); end

            for invert = 0:1
                B = A;
                if invert, B = ~B; end

                for sh = 0:(nlon-1)
                    C = circshift(B, [0, sh]);
                    yPred = false(size(yExpected));
                    for k = 1:numel(yExpected)
                        yPred(k) = C(iy(k), ix(k));
                    end
                    score = sum(yPred == yExpected);
                    if score > bestScore
                        bestScore = score;
                        best.flipLat = flipLat;
                        best.flipLon = flipLon;
                        best.shift = sh;
                        best.invert = invert;
                        if bestScore == numel(yExpected)
                            % perfect match
                        end
                    end
                end
            end
        end
    end

    M = G0;
    if best.flipLat, M = flipud(M); end
    if best.flipLon, M = fliplr(M); end
    if best.invert, M = ~M; end
    M = circshift(M, [0, best.shift]);

    global_coast = double(M.');

    fprintf('Coast mask auto-alignment: score %d/%d | flipLat=%d flipLon=%d shift=%d invert=%d\n', ...
        bestScore, numel(yExpected), best.flipLat, best.flipLon, best.shift, best.invert);
end
