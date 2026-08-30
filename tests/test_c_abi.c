#include <boiled_egg/boiled_egg.h>
#include <stdio.h>

int main(void) {
    boiledegg_config c = boiledegg_default_config(48000, 2);
    boiledegg_result r = BOILEDEGG_OK;
    boiledegg_handle* h = boiledegg_create(&c, &r);
    if (!h || r != BOILEDEGG_OK) return 1;
    if (boiledegg_set_time_ratio(h, 1.25f) != BOILEDEGG_OK) return 2;
    if (boiledegg_set_pitch_semitones(h, 3.0f) != BOILEDEGG_OK) return 3;
    printf("%s %s\n", boiledegg_version_string(), boiledegg_result_string(BOILEDEGG_OK));
    boiledegg_destroy(h);
    return 0;
}
