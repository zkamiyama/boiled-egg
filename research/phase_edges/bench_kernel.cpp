// Traversal microbenchmark, NOT complete rendering or a realtime deadline test.
// Increments are prepared outside timing. Baseline/edge outputs must agree.
#include "edge_heap.hpp"
#include "../phase_gradient/heap_integrator.hpp"
#include <array>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <vector>
#include <algorithm>
int main(){
    std::cout<<"repeat,bins,mode,iterations,mean_us,p99_us,max_us,max_pops\n";
    for(unsigned r=1;r<=3;++r)for(unsigned n:{513U,1025U,2049U,4097U}) {
        boiled_egg::experiment::phase_heap old(n);boiled_egg::experiment::edge_heap edge(n);
        std::vector<double> m(n),om(n),dt(n),odt(n),df(n),op(n),ip(n),ti(n),fi(n-1),out(n),expected(n),durations(1000);
        for(unsigned k=0;k<n;++k){m[k]=1.+double(k*719U%97U);om[k]=1.+double(k*23U%103U);dt[k]=.01*k;odt[k]=.01*k+.001;df[k]=std::sin(.07*k);op[k]=std::cos(.1*k);ip[k]=.1;ti[k]=.5*256*(odt[k]+dt[k]);if(k)fi[k-1]=.5*1.5*(df[k-1]+df[k]);}
        old.integrate(m.data(),om.data(),dt.data(),odt.data(),df.data(),op.data(),ip.data(),256,1.5,1e-6,expected.data());
        edge.integrate(m.data(),om.data(),ti.data(),fi.data(),op.data(),ip.data(),1e-6,out.data());
        if(out!=expected)return 2;
        for(unsigned v=0;v<2;++v){unsigned mode=(v+r)%2,maxp=0;
            for(unsigned i=0;i<1200;++i){
                auto start=std::chrono::steady_clock::now();unsigned pops;
                if(mode)pops=edge.integrate(m.data(),om.data(),ti.data(),fi.data(),op.data(),ip.data(),1e-6,out.data()).pops;
                else pops=old.integrate(m.data(),om.data(),dt.data(),odt.data(),df.data(),op.data(),ip.data(),256,1.5,1e-6,out.data()).pops;
                auto end=std::chrono::steady_clock::now();if(out!=expected||pops>2*n)return 3;
                if(i>=200)durations[i-200]=std::chrono::duration<double,std::micro>(end-start).count();maxp=std::max(maxp,pops);
            }
            double mean=std::accumulate(durations.begin(),durations.end(),0.)/durations.size();std::sort(durations.begin(),durations.end());
            std::cout<<r<<','<<n<<','<<(mode?"edge":"nodal")<<",1000,"<<std::setprecision(9)<<mean<<','<<durations[989]<<','<<durations.back()<<','<<maxp<<'\n';
        }
    }
}
