function name = main_infer_basin_name(boundaryFile)
%MAIN_INFER_BASIN_NAME Infer basin name from boundary file name.
    [~,name,~] = fileparts(boundaryFile);
    name = regexprep(name, '\s+', '_');
end
