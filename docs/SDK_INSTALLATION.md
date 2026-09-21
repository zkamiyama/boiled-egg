# SDK installation and relocation / SDKの導入・移設

This guide covers the **existing SDK**, not the paused NRT research kernels.
A successful installed-consumer test qualifies only that platform/build/configuration;
it does not certify a DAW, audio device, plugin editor or perceptual quality.

## Build and install

CMake 3.20+, a C++20 compiler and a C11 compiler are required. CMake 3.21+ is
needed for the JSON/JUnit test driver used below. Release is explicit so that
Visual Studio and other multi-configuration generators select the right files.

```sh
cmake -S . -B build-package -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_BUILD_SHARED=ON \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=OFF \
  -DBOILED_EGG_BUILD_TESTS=OFF -DBOILED_EGG_BUILD_TOOLS=OFF \
  -DBOILED_EGG_BUILD_BENCH=OFF
cmake --build build-package --config Release --parallel 2
cmake --install build-package --config Release --prefix /chosen/sdk/path
```

Set `BOILED_EGG_BUILD_SHARED=OFF` for a static library. The exported CMake target
then propagates `BOILED_EGG_STATIC=1` to its consumers. When using a Windows static
library without CMake, define `BOILED_EGG_STATIC=1` before including public SDK
headers. Do not define it for a DLL client, and never define the private
`BOILED_EGG_BUILDING_LIBRARY` in client code. Static C clients still require the
matching C++ runtime at link time; compiling the client as C does not make the
implementation a C-only library. Use a compatible compiler/runtime and architecture.

For a shared build, ship/load the actual DLL/so/dylib as well as the relevant link
library. Windows runtime discovery needs the SDK's `bin` directory on the process
search path or another explicitly configured trusted deployment location. This
guide does not recommend changing the user's global loader path. On other systems,
configure the consumer's runtime search path through its build/deployment tooling.

## External CMake consumer

```cmake
cmake_minimum_required(VERSION 3.20)
project(client LANGUAGES C CXX)
find_package(boiled_egg CONFIG REQUIRED)
add_executable(client main.c)
set_target_properties(client PROPERTIES
  C_STANDARD 11 C_STANDARD_REQUIRED YES LINKER_LANGUAGE CXX)
target_link_libraries(client PRIVATE boiled_egg::boiled_egg)
```

Configure with `-DCMAKE_PREFIX_PATH=/moved/sdk/path` (or the exact
`boiled_egg_DIR` containing `boiled_eggConfig.cmake`). C++ consumers include the
header-only `boiled_egg/boiled_egg.hpp` wrapper and use C++20 or newer.
Do not include private `src/` or research headers. Multiple installed SDK versions
should use separate prefixes and explicit package selection.

## Reproducible package check

From the repository, using a previously built SDK and a **new** output directory:

```sh
python scripts/check_sdk_install.py --build build-package \
  --output package-evidence --linkage shared --spectral OFF --configuration Release
```

The driver installs into a new prefix, moves that prefix (including a space in its
name), confirms the original prefix is absent, and builds independent copies of the
public C11/C++ consumers. It verifies the imported linkage and static definitions,
rejects a deliberately missing installed library, then runs exactly five unique,
enabled and built tests with no skips. Receipts contain platform, package/consumer
hashes, commands, return codes and test names. Existing evidence is not overwritten.

The five tests include the established backend/state/ramp contracts and two new
nonzero PCM consumers: 48/96 kHz, 32/64-frame input/output partitions, full8192-frame
EOF drain, reset/repetition, numerical unity reconstruction, and proportional stereo
in C. These cases verify package usability, not general pitch/TSM naturalness.

The `sdk-installation` workflow runs shared/static x spectral ON/OFF on native
Linux, Windows and macOS runners. A workflow definition is not evidence of a pass:
use its exact HEAD/job results and receipts. This matrix intentionally builds no
new research kernels, CLAP/VST3 adapters or GUI. Existing SDK regression workflows
are separate and still required for changes in their scope.

## Product and preview boundaries

|Use|Existing path|What is still required|
|---|---|---|
|PDC-assisted DAW mix|fixed-I/O processing; query actual latency/tail|DAW automation/state/reactivation/multiple-instance/long-run validation|
|Live monitor|same fixed-I/O contract, one audio owner per instance|physical round-trip latency/device recovery and an explicit latency budget|
|Offline clip|variable-rate push/pull/flush with declared ratios|application progress/cancel/long-file behavior; no native-freeze substitution|

WSOLA remains the default. Building spectral support with
`BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON` does not select or certify it: use the
public backend capability query and explicit `BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL`
opt-in. Quality and formant policies remain distinct. The Audition Lab transport
is a separate path; this SDK package does not acquire its freeze semantics.

日本語: 今回の導入確認は、既存SDKの共有・静的リンクと、配布先を移動した後の
C/C++利用を対象にします。音声処理の計算量や方式を増やす変更ではありません。
Windows/macOSのSDK導入成功を、プラグインGUI・実DAW・物理音声機器の対応完了と
読み替えません。重い研究候補は保留し、既定値・ABI・state・ID・latencyを維持します。
ライセンス、署名、第三者noticeや正式サポート範囲は、所有者の決定と個別の検証が
必要であり、この導入試験だけで配布許諾を決めません。

References: CMake's official Importing and Exporting Guide and
`target_compile_definitions` documentation; Microsoft's `__declspec(dllimport)`
documentation. Project-specific measured results are in the E1 results report and
Issue56 / PR57, not implied by those external documents.
