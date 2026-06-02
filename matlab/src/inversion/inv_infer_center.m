function center = inv_infer_center(Tk, SH)
%INV_INFER_CENTER Infer processing center from GFC filename.
% Returns: 'JPL', 'GFZ', 'CSR', or 'UNKNOWN'.

    if nargin < 2
        SH = struct();
    end

    center = 'UNKNOWN';
    names = {};
    if isfield(SH, 'meta') && isstruct(SH.meta) && isfield(SH.meta, 'file') && ~isempty(SH.meta.file)
        [~, nm, ext] = fileparts(SH.meta.file);
        names{end+1} = [nm ext]; %#ok<AGROW>
    end
    if isfield(Tk, 'file_guess') && ~isempty(Tk.file_guess)
        [~, nm, ext] = fileparts(Tk.file_guess);
        names{end+1} = [nm ext]; %#ok<AGROW>
    end

    for i = 1:numel(names)
        s = upper(names{i});
        if contains(s, 'JPLEM')
            center = 'JPL';
            return;
        end
        if contains(s, 'GFZOP')
            center = 'GFZ';
            return;
        end
        if contains(s, 'UTCSR') || contains(s, 'CSR')
            center = 'CSR';
            return;
        end
    end
end
