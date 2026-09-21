/* Installed public C11 surface only.  A silent callback is not a PCM test. */
#include <boiled_egg/boiled_egg.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define N 8192u
static float source[2][N], result[2][N], previous[2][N];

static int read_available(boiledegg_handle* h, unsigned block, unsigned* offset) {
    unsigned calls = 0;
    while (boiledegg_available(h)) {
        float scratch[2][64];
        float* output[2] = {scratch[0], scratch[1]};
        uint32_t made = 0;
        if (++calls > N || boiledegg_pull(h, output, block, &made) ||
            made == 0 || made > block || *offset + made > N) return 1;
        for (unsigned ch = 0; ch < 2; ++ch)
            memcpy(result[ch] + *offset, scratch[ch], made * sizeof(float));
        *offset += made;
    }
    return 0;
}

static int stream(boiledegg_handle* h, unsigned block) {
    unsigned pos = 0, offset = 0;
    memset(result, 0, sizeof(result));
    while (pos < N) {
        const unsigned count = N - pos < block ? N - pos : block;
        const float* input[2] = {source[0] + pos, source[1] + pos};
        uint32_t accepted = 0;
        if (boiledegg_push(h, input, count, &accepted) || accepted != count) return 2;
        pos += accepted;
        if (read_available(h, block, &offset)) return 3;
    }
    if (boiledegg_flush(h) || read_available(h, block, &offset)) return 4;
    if (offset != N || !boiledegg_is_drained(h)) return 5;
    return 0;
}

static int exercise(unsigned rate, unsigned block) {
    boiledegg_config config = boiledegg_default_config(rate, 2);
    config.max_block_size = block;
    boiledegg_result status = BOILEDEGG_OK;
    boiledegg_handle* h = boiledegg_create(&config, &status);
    if (!h || status) { boiledegg_destroy(h); return 6; }
    int failed = 0;
    double max_error = 0, max_ratio_error = 0, energy = 0;
    for (unsigned i = 0; i < N; ++i) {
        /* Exactly representable broad-band nonzero data; no audio oracle fitting. */
        source[0][i] = (float)((int)(i % 257u) - 128) / 512.0f;
        source[1][i] = source[0][i] * .5f;
    }
    for (unsigned repeat = 0; repeat < 2; ++repeat) {
        if (repeat && boiledegg_reset(h)) { failed = 7; break; }
        failed = stream(h, block);
        if (failed) break;
        for (unsigned i = 0; i < N; ++i) {
            if (!isfinite(result[0][i]) || !isfinite(result[1][i])) { failed = 8; break; }
            for (unsigned ch = 0; ch < 2; ++ch) {
                const double d = fabs((double)result[ch][i] - source[ch][i]);
                if (d > max_error) max_error = d;
            }
            const double d = fabs((double)result[1][i] - .5 * result[0][i]);
            if (d > max_ratio_error) max_ratio_error = d;
            if (!repeat) energy += (double)result[0][i] * result[0][i];
        }
        if (repeat && memcmp(previous, result, sizeof(result))) failed = 9;
        memcpy(previous, result, sizeof(result));
    }
    boiledegg_destroy(h);
    if (failed) return failed;
    if (max_error > 3e-6 || max_ratio_error > 3e-6 || energy < 1) return 10;
    printf("rate=%u block=%u frames=%u repeats=2 max_error=%.17g proportional_error=%.17g energy=%.17g\n",
           rate, block, N, max_error, max_ratio_error, energy);
    return 0;
}
int main(void) {
    const unsigned rates[2] = {48000, 96000}, blocks[2] = {32, 64};
    if (boiledegg_abi_version() != BOILEDEGG_ABI_VERSION) return 11;
    for (unsigned r = 0; r < 2; ++r) for (unsigned b = 0; b < 2; ++b) {
        int status = exercise(rates[r], blocks[b]);
        if (status) return status;
    }
    return 0;
}
