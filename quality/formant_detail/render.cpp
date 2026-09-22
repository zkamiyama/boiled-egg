#include "driver.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
using namespace detail_test;
static unsigned integer(const char* text){std::size_t n=0;unsigned long v=std::stoul(text,&n);require(n==std::string(text).size()&&v<=1000000,"bad integer");return unsigned(v);}
int main(int argc,char** argv){try{
    require(argc==11,"input.raw output.raw report.json rate channels block pitch detail io repeat");
    unsigned rate=integer(argv[4]),channels=integer(argv[5]),block=integer(argv[6]),detail=integer(argv[8]),io=integer(argv[9]);
    std::size_t used=0;float pitch=std::stof(argv[7],&used);require(used==std::string(argv[7]).size()&&std::isfinite(pitch),"pitch");
    require((rate==48000||rate==96000)&&(channels==1||channels==2)&&(block==32||block==64||block==257)&&detail<=1&&(io==1||io==2),"scope");
    std::ifstream input(argv[1],std::ios::binary|std::ios::ate);require(bool(input),"input missing");auto bytes=input.tellg();require(bytes>0&&bytes%(4*channels)==0&&bytes<=8*96000*4,"input shape/budget");
    unsigned n=unsigned(bytes)/(4*channels);std::vector<float> interleaved(n*channels);input.seekg(0);input.read(reinterpret_cast<char*>(interleaved.data()),bytes);require(bool(input),"input truncated");
    Audio x{std::vector<float>(n),std::vector<float>(n)};for(unsigned i=0;i<n;++i)for(unsigned ch=0;ch<channels;++ch){float v=interleaved[i*channels+ch];require(std::isfinite(v),"input finite");x[ch][i]=v;}
    auto r=render(x,rate,channels,block,pitch,detail!=0,io==2);
    require(!std::ifstream(argv[2])&&!std::ifstream(argv[3]),"refuse overwrite");
    std::ofstream out(argv[2],std::ios::binary);for(unsigned i=0;i<r.pcm[0].size();++i)for(unsigned ch=0;ch<channels;++ch)out.write(reinterpret_cast<const char*>(&r.pcm[ch][i]),4);out.close();require(bool(out),"write output");
    double energy=0,peak=0,proportion=0;for(unsigned i=0;i<r.pcm[0].size();++i){double a=r.pcm[0][i];energy+=a*a;peak=std::max(peak,std::abs(a));if(channels==2)proportion=std::max(proportion,std::abs(double(r.pcm[1][i])+.5*a));}
    std::ofstream report(argv[3]);report<<std::setprecision(17)<<"{\"frames\":"<<r.pcm[0].size()<<",\"rate\":"<<rate<<",\"channels\":"<<channels<<",\"detail\":"<<detail<<",\"io\":"<<io<<",\"repeat\":"<<integer(argv[10])<<",\"latency\":"<<r.info.realtime_latency_frames<<",\"tail\":"<<r.info.realtime_tail_frames<<",\"peak\":"<<peak<<",\"energy\":"<<energy<<",\"proportional_error\":"<<proportion<<",\"setup_seconds\":"<<r.setup_seconds<<",\"service_seconds\":"<<r.service_seconds<<",\"flush_seconds\":"<<r.flush_seconds<<",\"max_service_seconds\":"<<r.max_service_seconds<<",\"input_blocks\":"<<r.input_blocks<<",\"service_period_exceedances\":"<<r.service_period_exceedances<<",\"services\":[";
    for(unsigned i=0;i<r.services.size();++i){if(i)report<<',';report<<r.services[i];}report<<"]}\n";report.close();require(bool(report),"write receipt");return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
