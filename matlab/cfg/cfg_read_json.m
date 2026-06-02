function s = cfg_read_json(jsonPath)
%CFG_READ_JSON Read JSON file into a struct.

    if ~isfile(jsonPath)
        error('JSON file not found: %s', jsonPath);
    end
    txt = fileread(jsonPath);
    s = jsondecode(txt);
end
