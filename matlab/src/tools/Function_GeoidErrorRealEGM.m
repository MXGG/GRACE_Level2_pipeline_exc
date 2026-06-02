% 
% function [GeoidDegreeError,CumGeoidError]=Function_GeoidErrorRealEGM(C1,S1,C2,S2,gmax,kmax)
% %计算大地水准面阶次误差和累积误差
% AverageR = 6378137.0D0 ;
% 
% if(gmax<=kmax)
%     smax=gmax;
% else
%     smax=kmax;
% end
% 
% dc=zeros(smax+1,smax+1);
% ds=zeros(smax+1,smax+1);
% 
% dc=C1(1:smax+1,1:smax+1)-C2(1:smax+1,1:smax+1);
% ds=S1(1:smax+1,1:smax+1)-S2(1:smax+1,1:smax+1);
% 
% GeoidDegreeError=zeros(smax+1,2);
% CumGeoidError=zeros(smax+1,2);
% 
% temcum=0.0;
% for i=1:smax+1
%     tem=0.0;
%     for j=1:i
%         tem=tem+dc(i,j)^2+ds(i,j)^2;
%     end
%     GeoidDegreeError(i,1)=i-1;
%     GeoidDegreeError(i,2)=sqrt(tem)*AverageR;
%     temcum=temcum+tem;
%     CumGeoidError(i,1)=i-1;
%     CumGeoidError(i,2)=sqrt(temcum)*AverageR;
% end


function [GeoidDegreeError, CumGeoidError] = ...
    Function_GeoidErrorRealEGM(C1,S1,C2,S2,gmax,kmax)

%------------- 参数与初始化 ---------------------------------------------%
R      = 6378137.0;                     % 平均地球半径 (m)
smax   = min(gmax,kmax);               % 可比较的最高阶
dc     = C1(1:smax+1,1:smax+1) - C2(1:smax+1,1:smax+1);
ds     = S1(1:smax+1,1:smax+1) - S2(1:smax+1,1:smax+1);

GeoidDegreeError = zeros(smax+1,2);     % [n,  E_n]
CumGeoidError    = zeros(smax+1,2);     % [n,  Cum_n]

cumVar = 0;                             % 累计方差 Σ σ_n^2

%------------- 主循环：n = 0 ... smax ----------------------------------%
for n = 0:smax
    %   MATLAB 索引行号 / 列号
    row     = n + 1;
    
    %   对给定 n, m=0...n 的系数误差平方和
    deltaSq = dc(row,1:row).^2 + ds(row,1:row).^2;   % 1×(n+1) 向量
    var_n   = (n+1)/(2*n+1) * sum(deltaSq);          % σ_n^2
    
    %   单度 RMS 误差
    GeoidDegreeError(row,:) = [n, R * sqrt(var_n)];
    
    %   累计到当前 n 的误差
    cumVar = cumVar + var_n;
    CumGeoidError(row,:)    = [n, R * sqrt(cumVar)];
end
