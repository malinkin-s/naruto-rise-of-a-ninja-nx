# naruto - Naruto: Rise of a Ninja (Xbox 360), ReXGlue recompiled project.
#
# Stage 3 (PC boot with the SDK's emulated GPU): the SDK's init template, nothing game-specific yet.
# SDK boilerplate lives in generated/rexglue.cmake (written by rexglue codegen).

cmake_minimum_required(VERSION 3.25)
project(naruto LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Switch: devkitA64 GCC 16's AArch64 early register allocation pass miscompiles table lookups (sa2-nx app/CMakeLists.txt,
# 2026-10-19: Peggle 2's large textures came out as garbage on the console only). Before the SDK, so it gets it too.
if(REXGLUE_PLATFORM_SWITCH)
    add_compile_options(-mearly-ra=none)
    add_link_options(-mearly-ra=none)
endif()

set(REXSDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../sdk" CACHE PATH "Path to rexglue-sdk source tree")

include(generated/rexglue.cmake)

# The PC build re-runs the generator by itself whenever an input in codegen.d changes (manifest, tomls, xex, the
# generator binary). That rewrites app/generated without the optimised flavour's post-codegen steps (no-volatile guest
# memory, loop barriers, direct calls, store cards; it happened on 2026-10-25), so they are appended to the same
# command (from sa2-nx). Every step is idempotent. The Switch cross build has no generator target: tools/codegen.sh.
if(TARGET naruto_codegen)
    add_custom_command(OUTPUT "${CMAKE_CURRENT_SOURCE_DIR}/generated/default/codegen.build.stamp" APPEND
        COMMAND bash "${CMAKE_CURRENT_SOURCE_DIR}/../tools/post_codegen.sh")
endif()

set(NARUTO_SOURCES
    src/main.cpp
    src/naruto_test_exit.cpp
    src/naruto_test_shots.cpp
    src/naruto_save_thumbnail.cpp
)
if(REXGLUE_PLATFORM_SWITCH)
    list(APPEND NARUTO_SOURCES src/naruto_static_modules.cpp src/naruto_no_gpu_plugin.cpp)
endif()

if(WIN32)
    add_executable(naruto WIN32 ${NARUTO_SOURCES})
else()
    add_executable(naruto ${NARUTO_SOURCES})
endif()

if(REXGLUE_PLATFORM_SWITCH)
    # Stage 6 first boot: no renderer yet (Renut on deko3d comes next); the game runs without a GPU plugin.
    rexglue_setup_target(naruto)
else()
    rexglue_setup_target(naruto GPU_PLUGINS xenos)
endif()

# Renut's Direct3D-level renderer (reNut by masterspike52, through banjo-nx and sa2-nx; docs/renut-retarget.md), chosen
# at boot with sa2_renderer = "renut": plume Vulkan on the PC, plume's deko3d back end on the Switch.
option(NARUTO_RENUT_RENDERER "Link Renut's Direct3D-level renderer" ON)
if(NARUTO_RENUT_RENDERER)
    include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/naruto_renut_gpu.cmake")
endif()

# From sa2-nx: the SDK compiles itself with these (directory scope), but they do not reach the generated game code,
# built in this directory. GCC's default for GNU C++ is -ffp-contract=fast: it fuses the guest's separate fmul/fadd
# into FMA and results drift from the Xbox 360; strict aliasing is unsafe for recompiled code (guest memory written
# and read through different types: with guest loads that are not volatile, GCC reordered them and freed a garbage
# pointer, 2026-10-25). Every target that holds generated code: the executable, naruto_recomp and the AI2C module.
# Clang (the PC build) gets them too, so the PC rounds exactly like the console.
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    foreach(target naruto naruto_recomp naruto_AI2C)
        if(TARGET ${target})
            target_compile_options(${target} PRIVATE -ffp-contract=off -fno-strict-aliasing)
        endif()
    endforeach()
endif()

# CPU step (2026-10-25, from sa2-nx's candidate 1 of 2026-10-12): the recompiled game code's `sqrt` without the errno
# check (a compare and a branch to the C library after every fsqrt). Values are unchanged: nothing reads errno.
# Not -fno-trapping-math: it may move a float operation across the code's flush-mode switches (sa2-nx's audit).
option(NARUTO_GAME_NO_MATH_ERRNO "-fno-math-errno on the recompiled game code" ON)
if(NARUTO_GAME_NO_MATH_ERRNO AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    foreach(target naruto_recomp naruto_AI2C)
        if(TARGET ${target})
            target_compile_options(${target} PRIVATE -fno-math-errno)
        endif()
    endforeach()
endif()

if(REXGLUE_PLATFORM_SWITCH)
    # An emulator (Ryujinx) starts NROs without argv[0]: the SDK then uses this path for the NRO's folder.
    if(TARGET rexcore)
        target_compile_definitions(rexcore PRIVATE REX_SWITCH_FALLBACK_EXE="/switch/naruto-nx/naruto.nro")
    endif()

    # The guest engine DLL (AI2C.dll) goes into the NRO (an NRO cannot load libraries): its static archive is partially
    # linked into one object, every symbol it did not export made local (its generated globals share names with the
    # executable's) and the two entry points renamed for src/naruto_static_modules.cpp. From sa2-nx (Data_DLL).
    set(_dll_object "${CMAKE_CURRENT_BINARY_DIR}/naruto_AI2C_linked.o")
    get_filename_component(_switch_bin "${CMAKE_CXX_COMPILER}" DIRECTORY)
    add_custom_command(OUTPUT "${_dll_object}"
        COMMAND "${_switch_bin}/aarch64-none-elf-ld" -r --force-group-allocation -o "${_dll_object}.tmp"
                --whole-archive $<TARGET_FILE:naruto_AI2C> --no-whole-archive
        COMMAND "${CMAKE_OBJCOPY}" --localize-hidden
                --redefine-sym ReXModule_Register=ReXModule_Register_naruto_AI2C
                --redefine-sym ReXModule_GetImageInfo=ReXModule_GetImageInfo_naruto_AI2C
                "${_dll_object}.tmp" "${_dll_object}"
        DEPENDS naruto_AI2C
        COMMENT "Linking the AI2C module into one object for the NRO"
        VERBATIM)
    set_source_files_properties("${_dll_object}" PROPERTIES EXTERNAL_OBJECT TRUE GENERATED TRUE)
    target_sources(naruto PRIVATE "${_dll_object}")

    # The generated function-registration files: one function of ~24,000 SetFunction calls; -O0 compiles it in seconds
    # (sa2-nx, from sasrt-nx: GCC -O3 spent 13-15 minutes on SA2's).
    foreach(register_file generated/default/naruto_register.cpp generated/ai2c/naruto_register.cpp)
        if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${register_file}")
            set_property(SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/${register_file}" APPEND PROPERTY COMPILE_OPTIONS -O0)
        endif()
    endforeach()

    # Settings compiled into the NRO (naruto_switch_defaults.toml).
    file(READ "${CMAKE_CURRENT_SOURCE_DIR}/naruto_switch_defaults.toml" NARUTO_BUILTIN_CONFIG)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/naruto_switch_defaults.toml")
    # And the player's naruto.toml, written next to the NRO when it is missing (src/naruto_app.h DefaultConfigFile).
    file(READ "${CMAKE_CURRENT_SOURCE_DIR}/naruto_switch.toml" NARUTO_PLAYER_CONFIG)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/naruto_switch.toml")
    configure_file("${CMAKE_CURRENT_SOURCE_DIR}/src/naruto_builtin_config.h.in"
                   "${CMAKE_CURRENT_BINARY_DIR}/builtin_config/naruto_builtin_config.h" @ONLY)
    target_include_directories(naruto PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/builtin_config")
    target_compile_definitions(naruto PRIVATE NARUTO_BUILTIN_CONFIG=1)

    # Link-time optimisation (sa2-nx app/CMakeLists.txt, from nfsmw-nx / UnleashedRecomp-NX): the recompiled
    # default.xex (naruto_recomp) and the app compiled to GIMPLE and optimised as one program at the link, so small
    # game functions inline across files. Out of it: the SDK libraries, the renderer library (an archive of LTO objects
    # needs gcc-ar) and AI2C (partially linked with ld -r above, which needs machine code). -ffp-contract=off and
    # -fno-strict-aliasing repeated at the link (the LTRANS stage must not fuse what the compile stage kept apart);
    # xxHash with XXH_FORCE_MEMORY_ACCESS=0 (nfsmw-nx: its default broke once inlined under LTO).
    # Off: no gain measured on 2026-10-24 (lto768 against gpu768: the game thread stays at ~26 ms a frame).
    option(NARUTO_SWITCH_LTO "Link-time optimisation of the game code and the app (Switch)" OFF)
    set(NARUTO_SWITCH_LTO_JOBS "2" CACHE STRING "Parallel LTRANS jobs of the Switch LTO link (memory)")
    option(NARUTO_SWITCH_IPA_PTA "-fipa-pta at the Switch LTO link" OFF)
    target_compile_definitions(naruto PRIVATE XXH_FORCE_MEMORY_ACCESS=0)
    if(NARUTO_SWITCH_LTO)
        set(_naruto_lto_compile -flto -fno-fat-lto-objects)
        set(_naruto_lto_link -flto=${NARUTO_SWITCH_LTO_JOBS} -flto-partition=balanced -ffp-contract=off
                             -fno-strict-aliasing)
        if(NARUTO_SWITCH_IPA_PTA)
            list(APPEND _naruto_lto_compile -fipa-pta)
            list(APPEND _naruto_lto_link -fipa-pta)
        endif()
        foreach(target naruto_recomp naruto)
            if(TARGET ${target})
                target_compile_options(${target} PRIVATE ${_naruto_lto_compile})
            endif()
        endforeach()
        target_link_options(naruto PRIVATE ${_naruto_lto_link})
        message(STATUS "naruto: Switch LTO on (${NARUTO_SWITCH_LTO_JOBS} LTRANS jobs, -fipa-pta ${NARUTO_SWITCH_IPA_PTA})")
    endif()

    rexglue_switch_add_nro(naruto
        NAME "Naruto: Rise of a Ninja"
        AUTHOR "malinkin-s"
        VERSION "0.1.1")
endif()
