# naruto - Naruto: Rise of a Ninja (Xbox 360), ReXGlue recompiled project.
#
# Stage 3 (PC boot with the SDK's emulated GPU): the SDK's init template, nothing game-specific yet.
# SDK boilerplate lives in generated/rexglue.cmake (written by rexglue codegen).

cmake_minimum_required(VERSION 3.25)
project(naruto LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(REXSDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../sdk" CACHE PATH "Path to rexglue-sdk source tree")

include(generated/rexglue.cmake)

set(NARUTO_SOURCES
    src/main.cpp
)

if(WIN32)
    add_executable(naruto WIN32 ${NARUTO_SOURCES})
else()
    add_executable(naruto ${NARUTO_SOURCES})
endif()

rexglue_setup_target(naruto GPU_PLUGINS xenos)
