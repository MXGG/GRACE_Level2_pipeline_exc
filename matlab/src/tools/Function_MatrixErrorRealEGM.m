function [ErrorMatrix]=Function_MatrixErrorRealEGM(C1,S1,C2,S2,gmax,kmax)

if(gmax<=kmax)
    smax=gmax;
else
    smax=kmax;
end

dc=zeros(smax+1,smax+1);
ds=zeros(smax+1,smax+1);

dc=C1(1:smax+1,1:smax+1)-C2(1:smax+1,1:smax+1);
ds=S1(1:smax+1,1:smax+1)-S2(1:smax+1,1:smax+1);

ErrorMatrix(smax+1,2*smax+1)=0;
for i=1:smax+1
    for j=1:smax+1
        ErrorMatrix(i,smax+2-j)=dc(i,j);
    end
end

for i=1:smax+1
    for j=2:smax+1  %²»ÐèÒªS£¨i£¬0£©
        ErrorMatrix(i,smax+j)=ds(i,j);
    end
end
