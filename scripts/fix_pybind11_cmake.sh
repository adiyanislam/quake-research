#!/usr/bin/env bash
set -e
sed -i 's/cmake_minimum_required(VERSION 3.4)/cmake_minimum_required(VERSION 3.5)/' \
  src/cpp/third_party/pybind11/CMakeLists.txt
