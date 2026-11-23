#!/usr/bin/env bash
# ============================================================================
# build.sh — сборка всех модулей платформы «Python-Школа» через CMake (Linux).
#   C++   -> build/libpyschool_helpers.so
#   Java  -> build/pyschool_utils.jar        (если есть javac/jar)
#   C#    -> build/StatusProxy.exe / csharp  (если есть mcs/dotnet)
# Python-код не компилируется — он запускается напрямую.
# ============================================================================
set -e
cd "$(dirname "$0")/.."

cmake -S . -B build
cmake --build build -j"$(nproc)"

echo
echo "Сборка завершена. Артефакты в ./build/:"
ls -1 build | grep -E '\.(so|jar|exe)$' || true
echo
echo "Запуск сайта:            python3 src/python/server.py 8080"
echo "Запуск C# статус-панели: mono build/StatusProxy.exe 8081   (или dotnet build/csharp/StatusProxy.dll 8081)"
