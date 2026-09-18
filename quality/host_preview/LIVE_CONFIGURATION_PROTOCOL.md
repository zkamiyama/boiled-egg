# C2 continuation: live configuration, 2026-09-17

Base: 9b430cf40e7026532c3b01a9dc562b3cb3ed6192. PR #30 / roadmap #15 and #18.
No changes to src/include, DSP algorithms, latency formula or SDK ABI.

The CLAP parameter contract allows live host changes even for parameters that
are not automatable. They can arrive through process(), not just params.flush().
The current adapter parses quality/backend/policy but its processor rejects them
as nonautomatable, causing a valid manual host change to fail an audio callback.

Accept valid configuration events as pending requests. Keep active DSP and
reported latency unchanged until host reactivation. At each sample offset all
values in the group are validated together. While a different configuration is
pending, subsequent controls are staged with that request, not applied to an
incompatible active engine. Returning to the active configuration cancels the
request and resumes compatible controls at that event position. No DSP creation,
allocation, locks or host main-thread callbacks from the audio processing path.
The existing generic/VST3 automation entry retains its nonautomatable rejection;
CLAP explicitly opts into live-configuration handling.

Validate the entire event batch before processing or publishing any target.
An invalid later event must not change samples, state, time position or restart
requests. Test backend/quality/policy, joint controls, cancellation, host restart,
state roundtrip, supported 44.1/48/88.2/96k rates, preview ON/OFF, block boundaries,
in-place and zero callback allocations. Run the same new ABI test against the
inherited unmodified module and retain its failure. Do not relabel it a test of
new DSP sound quality. Add the standard CLAP bypass/enum metadata to identify the
existing controls correctly; no parameter IDs/ranges/state format change.

Primary contract: https://github.com/free-audio/clap/blob/main/include/clap/ext/params.h
Latency: https://github.com/free-audio/clap/blob/main/include/clap/ext/latency.h
The pinned 1.2.10 dependency headers are also checked locally.
