cmake_minimum_required(VERSION 3.17)
project(CppMicroServicesTestPackage CXX)

find_package(CppMicroServices REQUIRED)

add_executable(test_package src/main.cpp)
target_link_libraries(test_package PRIVATE CppMicroServices)
