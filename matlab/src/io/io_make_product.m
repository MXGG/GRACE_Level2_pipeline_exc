function P = io_make_product(tag, Tk, lonVec, latVec, ewh, meta)
%IO_MAKE_PRODUCT Create a standard Product struct compatible with pipeline modules.

    if nargin < 6; meta = struct(); end

    P = struct();
    P.tag = char(tag);
    P.time = Tk;
    P.grid = struct('lon', lonVec(:).', 'lat', latVec(:).', 'ewh', ewh);
    P.meta = meta;
    P.metrics = struct();
end
