function P = io_load_product_mat(fp)
%IO_LOAD_PRODUCT_MAT Load product from MAT file saved by io_save_product.

    S = load(fp);
    if isfield(S,'P')
        P = S.P;
    else
        % backward: maybe saved with variable name = tag
        fn = fieldnames(S);
        P = S.(fn{1});
    end
end
