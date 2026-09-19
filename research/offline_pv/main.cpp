#include "offline.hpp"
#include "wav_io.hpp"
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <chrono>

namespace fs=std::filesystem;
namespace {
std::string quote(const std::string& s) {
    std::string out="\""; for (unsigned char ch:s) {
        if(ch=='"' || ch=='\\') out+='\\';
        if(ch<32) out+=' '; else out+=static_cast<char>(ch);
    } return out+'"';
}
double number(const std::string& text) {
    std::size_t end=0; const auto value=std::stod(text,&end);
    if(end!=text.size() || !std::isfinite(value)) throw std::invalid_argument("invalid finite number");
    return value;
}
void write(const fs::path& path,const std::string& text) {
    std::ofstream file(path); file.exceptions(std::ios::badbit|std::ios::failbit); file<<text<<'\n';
}
}
int main(int argc,char** argv) {
    fs::path directory; bool owned=false;
    try {
        if(argc<3) throw std::invalid_argument("INPUT.wav NEW_OUTPUT_DIRECTORY --execution offline --allow-experimental --iterations 0|8|32 [--time .5..2] [--pitch-semitones -12..12] [--formant off]");
        directory=argv[2];
        if(!fs::create_directory(directory)) throw std::invalid_argument("output directory must be new; no overwrite");
        owned=true;
        std::map<std::string,std::string> args;
        for(int i=3;i<argc;++i) {
            const std::string key=argv[i];
            if(args.contains(key)) throw std::invalid_argument("duplicate argument");
            if(key=="--allow-experimental") {args[key]="yes";continue;}
            if(key!="--execution" && key!="--iterations" && key!="--time" && key!="--pitch-semitones" && key!="--formant") throw std::invalid_argument("unknown argument");
            if(i+1>=argc) throw std::invalid_argument("missing option value");
            args[key]=argv[++i];
        }
        if(args["--execution"]!="offline" || !args.contains("--allow-experimental") || !args.contains("--iterations")) throw std::invalid_argument("explicit offline opt-in and iteration count required");
        if(args.contains("--formant") && args["--formant"]!="off") throw std::invalid_argument("formant preservation is unsupported; not silently disabled");
        const auto it=number(args["--iterations"]);
        if(it!=0 && it!=8 && it!=32) throw std::invalid_argument("iterations must be0,8,32");
        boiled_egg::offline_research::Config c; c.iterations=static_cast<unsigned>(it);
        if(args.contains("--time")) c.time_ratio=number(args["--time"]);
        const auto semitones=args.contains("--pitch-semitones")?number(args["--pitch-semitones"]):0;
        if(semitones < -12 || semitones > 12) throw std::invalid_argument("pitch outside +/-12st");
        c.pitch_ratio=std::pow(2.,semitones/12.);
        if(fs::file_size(argv[1])>24000000) throw std::invalid_argument("input file exceeds safety limit");
        WavData input; std::string error;
        if(!read_wav(argv[1],input,error)) throw std::runtime_error(error);
        if(input.channels!=1) throw std::invalid_argument("only mono supported; no implicit downmix");
        c.sample_rate=input.sample_rate;
        const auto begin=std::chrono::steady_clock::now();
        auto result=boiled_egg::offline_research::render(input.interleaved,c);
        const auto seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
        WavData output; output.sample_rate=input.sample_rate; output.channels=1; output.interleaved=std::move(result.audio);
        if(!write_wav_float32((directory/"output.wav").string(),output,error)) throw std::runtime_error(error);
        std::ostringstream report; report<<std::setprecision(17)
          <<"{\"status\":\"rendered\",\"execution\":\"offline\",\"algorithm\":\"pv-seeded-griffin-lim-research-v1\",\"quality_selection\":null,\"realtime_qualified\":false,\"formant\":\"off\",\"iterations\":"<<c.iterations
          <<",\"sample_rate\":"<<c.sample_rate<<",\"input_frames\":"<<input.interleaved.size()<<",\"output_frames\":"<<output.interleaved.size()
          <<",\"time_ratio\":"<<c.time_ratio<<",\"pitch_ratio\":"<<c.pitch_ratio<<",\"fft_size\":"<<result.fft_size<<",\"hop\":"<<result.hop
          <<",\"intermediate_frames\":"<<result.intermediate_frames<<",\"estimated_work_bytes\":"<<result.estimated_work_bytes<<",\"render_wall_seconds\":"<<seconds<<",\"magnitude_residual\":[";
        for(std::size_t i=0;i<result.magnitude_residual.size();++i) {if(i)report<<',';report<<result.magnitude_residual[i];}
        report<<"]}"; write(directory/"report.json",report.str());
        std::cout<<"offline research render complete; not product quality qualification\n";
    } catch(const std::exception& e) {
        if(owned) {std::error_code ignored;fs::remove(directory/"output.wav",ignored);try {write(directory/"report.json","{\"status\":\"blocked\",\"quality_selection\":null,\"error\":"+quote(e.what())+"}");}catch(...) {}}
        std::cerr<<e.what()<<'\n';return 2;
    }
    return 0;
}
