function [C,S]=Function_Read_GFC(filename,Lmax,nmax)
%FUNCTION_READ_GFC Read spherical harmonic coefficients from GFC file.
%
% Description:
%   Reads gravity field coefficients (GFC format) and extracts C_lm and S_lm
%   matrices up to a specified maximum degree.
%
% INPUT:
%   filename - Full path to the GFC file
%   Lmax     - Maximum degree present in the file
%   nmax     - Maximum degree to extract (nmax <= Lmax)
%
% OUTPUT:
%   C        - Cosine coefficients matrix [(nmax+1) x (nmax+1)]
%   S        - Sine coefficients matrix [(nmax+1) x (nmax+1)]
%
% File Format:
%   Expects ICGEM-style GFC files with 35 header lines, followed by:
%   keyword  l  m  C_lm  S_lm  sigma_C  sigma_S
%
% Author: GRACE Pipeline Team

C=zeros(nmax+1,nmax+1);
S=zeros(nmax+1,nmax+1);

% Pre-allocate temporary arrays
temll=zeros((Lmax+3)*Lmax/2+1,1);
temmm=zeros((Lmax+3)*Lmax/2+1,1);
temc=zeros((Lmax+3)*Lmax/2+1,1);
tems=zeros((Lmax+3)*Lmax/2+1,1);

% Read coefficients (skip 35 header lines)
[~,temll,temmm,temc,tems,~,~]=textread(filename,'%s %u %u %f %f %f %f','headerlines',35);

% Fill coefficient matrices
m=length(temll);
for i=1:m
    if(temll(i)<=nmax)
        C(temll(i)+1,temmm(i)+1)=temc(i);
        S(temll(i)+1,temmm(i)+1)=tems(i);
    end
end
end