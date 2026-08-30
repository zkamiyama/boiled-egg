#include <boiled_egg/boiled_egg.h>
#include <stdio.h>

int main(void) {
    boiledegg_config c = boiledegg_default_config(48000, 2);
    c.max_block_size = 64;
    boiledegg_result r = BOILEDEGG_OK;
    boiledegg_handle* h = boiledegg_create(&c, &r);
    if (!h || r != BOILEDEGG_OK) return 1;

    boiledegg_runtime_info info = {0};
    info.struct_size = sizeof(info);
    if (boiledegg_get_runtime_info(h, &info) != BOILEDEGG_OK) return 2;
    if (info.realtime_latency_frames == 0 || info.realtime_tail_frames != info.realtime_latency_frames) return 3;

    float in_l[64] = {0}, in_r[64] = {0}, out_l[64] = {0}, out_r[64] = {0};
    const float* in[2] = {in_l, in_r};
    float* out[2] = {out_l, out_r};
    boiledegg_parameter_event event = {
        sizeof(boiledegg_parameter_event), 32,
        BOILEDEGG_PARAMETER_PITCH_SEMITONES, 3.0f
    };
    if (boiledegg_process_realtime(h, in, out, 64, &event, 1) != BOILEDEGG_OK) return 4;
    if (boiledegg_set_time_ratio(h, 1.25f) != BOILEDEGG_UNSUPPORTED_MODE) return 5;

    printf("%s %s latency=%u\n", boiledegg_version_string(), boiledegg_result_string(BOILEDEGG_OK), info.realtime_latency_frames);
    boiledegg_destroy(h);
    return 0;
}
