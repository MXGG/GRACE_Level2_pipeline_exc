function [sumx_sigma,sumg_sigma] = grace2ewh_sigma(Lmax,k,Nlmx,D_sigmaC,D_sigmaS,fir,n_c,n_f,nceta,nfir)
% 用 sigmaC / sigmaS 计算 EWH 不确定性
% 输出单位：cm
% 当前实现：忽略系数间协方差，只做对角方差传播

loveN_k0=[0,0.027,-0.303,-0.194,-0.132,-0.104,-0.089,-0.081,-0.076,-0.072,-0.069,-0.064,-0.058,-0.051,-0.040,-0.033,-0.027,-0.020,-0.014,-0.010,-0.007];
n_loveN=[0,1,2,3,4,5,6,7,8,9,10,12,15,20,30,40,50,70,100,150,200];

n = 0:Lmax;
loveN_k = interp1(n_loveN,loveN_k0,n);
loveN   = (2*n+1)./(1+loveN_k);
loveN2  = loveN.^2;   % 方差传播里要平方

a      = 6.378136460E+06;   % m
Pave   = 5517.0;            % kg/m3
Pwater = 1000.0;            % kg/m3

coef2 = (a*Pave/(3.0*Pwater)*100.0)^2;   % 转成 cm 后再平方，单位 cm^2

mfir = zeros(Lmax+1,n_f);
for j = 1:n_f
    for m = 0:Lmax
        mfir(m+1,j) = m * fir(j);
    end
end

cosdmf2 = cosd(mfir).^2;
sindmf2 = sind(mfir).^2;
clear mfir;

% m=0 时没有 S 项，强制置零更稳妥
D_sigmaS(:,1,:) = 0;

sumg_var = zeros(n_c,n_f,k);
sumx_sigma = zeros(n_c*n_f,k);

for i = 1:k
    sigmaC2 = D_sigmaC(:,:,i).^2;
    sigmaS2 = D_sigmaS(:,:,i).^2;

    for nn = 1:n_c
        Pn2 = Nlmx(:,:,nn).^2;

        for j = 1:n_f
            % 先按 m 累加，再按 n 累加
            varC = (Pn2 .* sigmaC2) * cosdmf2(:,j);
            varS = (Pn2 .* sigmaS2) * sindmf2(:,j);

            sumg_var(nn,j,i) = coef2 * (loveN2 * (varC + varS));
        end
    end
end

% 数值安全
sumg_var(sumg_var < 0) = 0;
sumg_sigma = sqrt(sumg_var);

for i = 1:n_c*n_f
    sumx_sigma(i,:) = sumg_sigma(nceta(i),nfir(i),:);
end
end
