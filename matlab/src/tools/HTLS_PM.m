%% Runs HTLS parameter.
function [Amp, alfa, freq, theta,Ex,Ex_flag]=HTLS_PM(x,Ts,p,k)
%----Results----
% {Amp, alfa, freq, theta}
% Ex-Singular value

%%
N=length(x);
L=N+1-p;
%X=zeros(L,p);
 X=hankel(x(1:L), x(L:N));
X1=hankel(x(1:p),x(p:N));
[Vx,Ex,Ux]=svd(X1);
% [Vx,Ex,Ux]=econ(X);
Ex=diag(Ex);
Ex_flag=length(find(Ex(:)>0.001));
Us=Ux(:,1:k);

[m,n]=size(Ux);
U1=Us(1:m-1,:);
U2=Us(2:m,:);
D12=[U1,U2];
[RD,ED,UD]=svd(D12); %对应YEV
U12=UD(1:k,k+1:k+k);
U22=UD(k+1:k+k,k+1:k+k);
fai=-U12*pinv(U22);%U12即为W12
l=eig(fai); %z

alfa=log(abs(l))/Ts; %% damping factor
freq=atan2(imag(l), real(l))/(2*pi*Ts);%%  frequency

%%
Z=zeros(N,k);
for i=1: length(l)
    Z(:, i)= transpose(l(i).^(0: N-1));
end
ck=Z\x; %h为ck， x为输入序列，Z为

Amp=abs(ck); %振幅
theta=atan2(imag(ck), real(ck));%相位
end

