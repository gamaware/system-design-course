cmake_minimum_required(VERSION 3.20)
project(cache_lab LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(cache_lab cache_lab.cpp)

find_package(PkgConfig REQUIRED)
pkg_check_modules(HIREDIS REQUIRED hiredis)
find_package(CURL REQUIRED)

target_include_directories(cache_lab PRIVATE
    ${HIREDIS_INCLUDE_DIRS}
    ${CURL_INCLUDE_DIRS}
)

target_link_libraries(cache_lab PRIVATE
    ${HIREDIS_LIBRARIES}
    ${CURL_LIBRARIES}
)
