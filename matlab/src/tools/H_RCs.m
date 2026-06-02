%% Runs Harmonic reconstruction components
function [Amp, alfa, freq, theta,Y,Ex,Ex_flag]=H_RCs(x,Ts,p,k)

%----Results----
% {Amp, alfa, freq, theta}
% Y-RCs 重构数据clea
% Ex-Singular value
%------------------------------------------
[Amp, alfa, freq, theta,Ex,Ex_flag]=HTLS_PM(x,Ts,p,k);
[freq, ix]=sort(freq);%按照频率进行排序
Amp =Amp(ix);%振幅
alfa=alfa(ix);%衰减因子
theta=theta(ix);%相位

%%
N=length(x);
n=0:N-1;
n=repmat(n, [k 1]);
k =exp(repmat(alfa, [1 N]).*n*Ts);
k(isinf(k))=realmax*sign(k(isinf(k)));
Y=(repmat(Amp, [1 N] ).*k).*...
cos(2*pi*Ts*repmat(freq, [1 N]).*n+repmat(theta, [1 N]));
end
