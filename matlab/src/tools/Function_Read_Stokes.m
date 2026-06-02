function [C,S]=Function_Read_Stokes(filename,nmax)

C=zeros(nmax+1,nmax+1);
S=zeros(nmax+1,nmax+1);

fid=fopen(filename,'r');
for L=1:nmax+1
    for M=1:L
        aline=fgetl(fid);
        sline=sscanf(aline,'%f',4);
        i=floor(sline(1))+1;
        j=floor(sline(2))+1;
        a=sline(3);
        b=sline(4);
        if(i<=nmax+1)
            C(i,j)=a;
            S(i,j)=b;
        end
    end
end
% pause(1000);
fclose(fid);