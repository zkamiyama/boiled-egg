#pragma once
#include <cstdint>
#include <string>
#include <vector>
struct WavData { uint32_t sample_rate=0; uint16_t channels=0; std::vector<float> interleaved; };
bool read_wav(const std::string& path,WavData& wav,std::string& error);
bool write_wav_float32(const std::string& path,const WavData& wav,std::string& error);
