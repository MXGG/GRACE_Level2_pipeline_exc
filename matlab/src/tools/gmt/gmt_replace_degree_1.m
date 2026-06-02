function [ cs_replace,tag] = gmt_replace_degree_1(dir_in,cs,int_year,int_month,num_file )

% Read the degree 1 files and replace the corresponding original Stokes
% coefficients with them
%
% INPUT:
%   dir_in      full path
%   cs          spherical harmonic coefficients in CS-format
%   int_year    year
%   int_month   mont
%   num_file    number of files
% 
% OUTPUT:
%   cs_replace  spherical harmonic coefficients with replaced degree one
%   tag         check
%
% FENG Wei 22/03/2015
% State Key Laboratory of Geodesy and Earth's Dynamics
% Institute of Geodesy and Geophysics, Chinese Academy of Sciences
% fengwei@whigg.ac.cn
cs_replace=zeros(size(cs));
[~, FILE_NAME,~]=fileparts(dir_in);
ind = 0;
if (strcmp(FILE_NAME,'TN-13_GEOC_CSR_RL06'))
    tag=1;
    % read the header
    %---------------------------modified-----------------------------------
    head_index=0;
    fid2 = fopen(dir_in,'r');
    while ~feof(fid2)
        str = fgetl(fid2);
        if fid2 == -1 
            ('Error opening the file'); 
        end
        if (isempty(str) | str==' ') 
           continue
        end % to find the blankspace, and skip it!
        if ~ischar(str)
           break,
        end 
        if strcmp(str(1:6),'GRCOF2')
            ind = ind+1; 
            a=sscanf(str,'%s %d %d %f %f %f %f %f %f %f');

        if(mod(ind,2)==0)
            D_C(ind,2) = a(9);
            D_S(ind,2) = a(10);
            D_C(ind,4) = a(11);
            D_S(ind,3) = a(12);
            l(ind) = a(2);
        else
            D_C(ind,1) = a(9);
            D_S(ind,1) = a(10);
            D_C(ind,3) = a(11);
            D_S(ind,3) = a(12);
            l(ind) = a(2);
        end
        end
    end
    % Replace Degree 1
    for ii=1:num_file
        cs_replace(ii,:,:) = cs(ii,:,:);
        for jj=1:length(l)
            if (int_year(ii)==year(jj) && int_month(ii)==mon(jj) && l(jj)==1 && m(jj)==0)
                cs_replace(ii,2,1) = aa(jj);
            elseif (int_year(ii)==year(jj) && int_month(ii)==mon(jj) && l(jj)==1 && m(jj)==1)
                cs_replace(ii,2,2) = aa(jj);
                cs_replace(ii,1,2) = bb(jj);
            end
        end
    end
else
    tag=0;
    %     warndlg('Format of degree 1 file is wrong!','Warning');
end



