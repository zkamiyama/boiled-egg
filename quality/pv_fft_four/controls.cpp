// Reuse all predecessor comparisons; add the new stage's partial-boundary cases.
#define main inherited_fft_controls_main
#include "../pv_fft_stage/controls.cpp"
#undef main

int main(int argc,char** argv) {
    if(argc!=2 || std::string(argv[1])!="second_stage")
        return inherited_fft_controls_main(argc,argv);
    try {
        for(std::size_t n=4;n<=16384;n*=2)
        for(unsigned family=0;family<4;++family)
        for(bool inverse:{false,true})for(bool simd:{false,true})
        for(std::size_t column:{0ul,1ul})
        for(auto budget:{0ul,1ul,2ul,3ul,4ul,5ul,127ul,128ul,129ul,4096ul,n/2,n/2+1}) {
            Plan plan(n);Old old(n);auto x=fixture(n,family),y=x;
            Plan::cursor a;Old::cursor b;
            plan.start(a,x.data(),inverse,simd);old.start(b,y.data(),inverse,simd);
            const auto prefix=n+n/2+column;
            plan.advance(a,prefix);old.advance(b,prefix);
            need(a.stage==1 && a.length==4 && a.column==column,"stage-four entry");
            cursors(a,b);need(same(x,y),"entry differs");
            need(plan.advance(a,budget)==old.advance(b,budget),"stage-four return differs");
            cursors(a,b);need(same(x,y),"stage-four pause differs");
            ++cases;++pauses;
        }
        std::cout<<"second_stage cases="<<cases<<" pauses="<<pauses<<" passed\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
