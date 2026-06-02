function    [cs,cs_sigma,int_year,int_month,meanday,time] = gmt_readgfc_ucas(pathname)
% Read the ICGEM gravity filed files
%
% INPUT:
%   pathname    filename with full path
% 
% OUTPUT:
%   cs          spherical harmonic coefficients in CS-format
%   cs_sigma    spherical harmonic coefficients in CS-format (formal error)
%
% FENG Wei 24/03/2015
% State Key Laboratory of Geodesy and Earth's Dynamics
% Institute of Geodesy and Geophysics, Chinese Academy of Sciences
% fengwei@whigg.ac.cn

[dir_in,file_name,file_type]=fileparts(pathname);
if  ~strcmp(file_type,'.gfc') && ~strcmp(file_type,'.GFC')
    error('Format of gmt_readgfc function is wrong!');
end
% read the header
head_index=0;
fid = fopen(pathname,'r');
tline = fgetl(fid);
while size(tline,2)<11 || ~strcmp(tline(1:11),'end_of_head')
    head_index = head_index+1;
    tline = fgetl(fid);
    % In JPL GSM files, the maximum degree changes, 60 or 90
    if size(tline,2)>10 && strcmp(tline(1:10),'max_degree') 
        degree_max=str2double(tline(11:end));
    end
end
fclose(fid);
% re-read the file, skip the comment lines
[~, l, m, Clm, Slm, Clm_sigma, Slm_sigma] = textread(pathname,'%s %u %u %f %f %f %f','headerlines',head_index+1);
for i = 1:length(l)
    sc_tmp(l(i)+1,degree_max+1-m(i)) = Slm(i);
    sc_tmp(l(i)+1,degree_max+1+m(i)) = Clm(i);
    sc_sigma_tmp(l(i)+1,degree_max+1-m(i)) = Slm_sigma(i);
    sc_sigma_tmp(l(i)+1,degree_max+1+m(i)) = Clm_sigma(i);
end

cs=gmt_sc2cs(sc_tmp);
cs_sigma=gmt_sc2cs(sc_sigma_tmp);
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% modified 2022-11-29 GET TIME
% Get time tag GSM-2_2002095-2002120_GRAC_UTCSR_BA01_0600.gfc
year1 = str2num(file_name(7:10));
year2 = str2num(file_name(15:18));
day1  = str2num(file_name(11:13));
day2  = str2num(file_name(19:21));
if year1 == year2
    meanday = (day1+day2)/2;
else
    if (day1+(366-day1+day2)/2)>365 % in latter year
        year1   = year1 + 1;
        meanday = day2-(366-day1+day2)/2;
    else
        meanday = day1+(366-day1+day2)/2;  % in former year
    end
end
time        = year1 + meanday/365.;
meanday     = round(meanday);
int_year    = year1;
int_month   = gmt_get_mon_day(year1,meanday+1);
end


