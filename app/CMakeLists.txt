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

set(NARUTO_SOURCES
    src/main.cpp
    src/naruto_test_exit.cpp
    src/naruto_test_shots.cpp
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
    configure_file("${CMAKE_CURRENT_SOURCE_DIR}/src/naruto_builtin_config.h.in"
                   "${CMAKE_CURRENT_BINARY_DIR}/builtin_config/naruto_builtin_config.h" @ONLY)
    target_include_directories(naruto PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/builtin_config")
    target_compile_definitions(naruto PRIVATE NARUTO_BUILTIN_CONFIG=1)

    rexglue_switch_add_nro(naruto
        NAME "Naruto: Rise of a Ninja"
        AUTHOR "malinkin-s"
        VERSION "0.0.1")
endif()
