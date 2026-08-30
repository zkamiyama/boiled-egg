#ifndef BOILED_EGG_RESEARCH_PV_RT_WAV_HPP
#define BOILED_EGG_RESEARCH_PV_RT_WAV_HPP
#include <cstdint>
#include <filesystem>
#include <vector>
struct wav_audio { std::uint32_t sample_rate{}; std::uint16_t channels{}; std::vector<float> interleaved; };
wav_audio read_wav(const std::filesystem::path& path);
void write_wav_float32(const std::filesystem::path& path, const wav_audio& audio);
#endif
