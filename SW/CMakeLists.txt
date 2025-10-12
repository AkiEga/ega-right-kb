# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)

# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.2.0)
set(toolchainVersion 14_2_Rel1)
set(picotoolVersion 2.2.0)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
set(PICO_BOARD pico2_w CACHE STRING "Board type")

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

project(pico_arcade_controller C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()

# Add executable. Default name is the project name, version 0.1

cmake_minimum_required(VERSION 3.13)

add_executable(pico_arcade_controller)

target_sources(pico_arcade_controller PUBLIC
        ${CMAKE_CURRENT_LIST_DIR}/main.c
        ${CMAKE_CURRENT_LIST_DIR}/usb_descriptors.c
        )

# Make sure TinyUSB can find tusb_config.h
target_include_directories(pico_arcade_controller PUBLIC
        ${CMAKE_CURRENT_LIST_DIR})

# In addition to pico_stdlib required for common PicoSDK functionality, add dependency on tinyusb_device
# for TinyUSB device support and tinyusb_board for the additional board support library used by the example
target_link_libraries(pico_arcade_controller PUBLIC pico_stdlib pico_unique_id tinyusb_device tinyusb_board hardware_gpio)

# Uncomment this line to enable fix for Errata RP2040-E5 (the fix requires use of GPIO 15)
#target_compile_definitions(pico_arcade_controller PUBLIC PICO_RP2040_USB_DEVICE_ENUMERATION_FIX=1)

pico_add_extra_outputs(pico_arcade_controller)

# add url via pico_set_program_url

# Optional: formatting target if clang-format is available
find_program(CLANG_FORMAT_EXE NAMES clang-format clang-format.exe)
if (CLANG_FORMAT_EXE)
    message(STATUS "Found clang-format: ${CLANG_FORMAT_EXE}")
    add_custom_target(format
        COMMAND ${CLANG_FORMAT_EXE} -i
            ${CMAKE_CURRENT_LIST_DIR}/main.c
            ${CMAKE_CURRENT_LIST_DIR}/usb_descriptors.c
            ${CMAKE_CURRENT_LIST_DIR}/usb_descriptors.h
            ${CMAKE_CURRENT_LIST_DIR}/tusb_config.h
        WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
        COMMENT "Running clang-format on source files"
    )
else()
    message(STATUS "clang-format not found; 'format' target will not be created")
endif()

# Optional: clang-tidy target if available
find_program(CLANG_TIDY_EXE NAMES clang-tidy clang-tidy.exe)
if (CLANG_TIDY_EXE)
    message(STATUS "Found clang-tidy: ${CLANG_TIDY_EXE}")
    add_custom_target(tidy
        COMMAND "${CLANG_TIDY_EXE}" "${CMAKE_CURRENT_LIST_DIR}/main.c" -p "${CMAKE_CURRENT_BINARY_DIR}"
        WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
        COMMENT "Running clang-tidy on main.c"
    )
else()
    message(STATUS "clang-tidy not found; 'tidy' target will not be created")
endif()
