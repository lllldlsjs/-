# ============================================================================
# Python-Школа — корневой CMake-файл проекта (только сборка, без установки).
#
# Архитектура смешанного стека:
#   * Python : HTTP-сервер сайта (src/python/server.py) — не компилируется;
#   * C++    : общая библиотека libpyschool_helpers.so (ctypes-мост);
#   * Java   : pyschool_utils.jar (JSON-RPC по stdio), собирается через javac/jar;
#   * C#     : StatusProxy.exe (порт 8081), собирается через dotnet/mcs/csc если есть.
#
# Сборка (Linux):
#   cmake -S . -B build
#   cmake --build build
#
# Всё складывается в ${CMAKE_BINARY_DIR}, откуда его находит native_bridge.py.
# Если Java или C#-компиляторы отсутствуют, соответствующие цели просто
# пропускаются (сайт продолжает работать с Python-фолбэками).
# ============================================================================

cmake_minimum_required(VERSION 3.16)

project(pyschool
        VERSION 1.0
        DESCRIPTION "Учебный сайт «Python-Школа» на разных языках (Python + C++ + Java + C#)"
        LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Тип сборки" FORCE)
endif()

# Все артефакты — прямо в build/, чтобы их искал src/python/native_bridge.py
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

get_filename_component(PYSCHOOL_ROOT ${CMAKE_CURRENT_SOURCE_DIR} ABSOLUTE)

# ---------------------------------------------------------------------------
# 1. C++ — общая библиотека для Python (ctypes)
# ---------------------------------------------------------------------------
add_library(pyschool_helpers SHARED
    src/cpp/perf_helper.cpp)
target_include_directories(pyschool_helpers PRIVATE src/cpp)
set_target_properties(pyschool_helpers PROPERTIES
    OUTPUT_NAME "pyschool_helpers"          # -> libpyschool_helpers.so
    POSITION_INDEPENDENT_CODE ON)

# ---------------------------------------------------------------------------
# 2. Java — сервис статистики текста (нужен JDK: javac + jar)
# ---------------------------------------------------------------------------
find_program(JAVAC_EXECUTABLE NAMES javac)
find_program(JAR_EXECUTABLE   NAMES jar)

# Проверка работоспособности JDK: в Debian/Ubuntu бывают «битые» симлинки
# /usr/bin/javac из пакета headless без libjli.so. Если javac не запускается —
# считаем Java недоступным и пропускаем цель (сайт работает с Python-фолбэком).
set(JAVA_USABLE FALSE)
if(JAVAC_EXECUTABLE AND JAR_EXECUTABLE)
    execute_process(COMMAND ${JAVAC_EXECUTABLE} -version
                    OUTPUT_QUIET ERROR_QUIET
                    RESULT_VARIABLE _javac_rc)
    if(_javac_rc EQUAL 0)
        set(JAVA_USABLE TRUE)
        message(STATUS "Java найден и работоспособен: ${JAVAC_EXECUTABLE} — цель 'java' включена")
    else()
        message(WARNING "Найден ${JAVAC_EXECUTABLE}, но он не запускается "
                        "(например, сломанный пакет JDK / отсутствует libjli.so). "
                        "Пропускаем сборку Java-модуля — сайт будет использовать "
                        "Python-фолбэк. Установите полный JDK (openjdk-*-jdk), "
                        "чтобы включить Java-цель.")
    endif()
else()
    message(STATUS "Java (javac/jar) НЕ найден — пропуск сборки Java-модуля "
                   "(сайт будет использовать Python-фолбэк)")
endif()

if(JAVA_USABLE)
    add_custom_target(java ALL
        COMMENT "[Java] Компиляция Main.java и упаковка pyschool_utils.jar"
        COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_BINARY_DIR}/java-classes"
        COMMAND ${JAVAC_EXECUTABLE} -encoding UTF-8
                -d "${CMAKE_BINARY_DIR}/java-classes"
                "${PYSCHOOL_ROOT}/src/java/Main.java"
        COMMAND ${JAR_EXECUTABLE} --create --file "${CMAKE_BINARY_DIR}/pyschool_utils.jar"
                --main-class Main
                -C "${CMAKE_BINARY_DIR}/java-classes" .
        BYPRODUCTS "${CMAKE_BINARY_DIR}/pyschool_utils.jar")
endif()

# ---------------------------------------------------------------------------
# 3. C# — статус-панель StatusProxy (dotnet / mono-mcs / csc — что найдётся)
# ---------------------------------------------------------------------------
find_program(DOTNET_EXECUTABLE NAMES dotnet)
find_program(MCS_EXECUTABLE    NAMES mcs mono-csc)
find_program(CSC_EXECUTABLE    NAMES csc)

if(DOTNET_EXECUTABLE OR MCS_EXECUTABLE OR CSC_EXECUTABLE)
    if(MCS_EXECUTABLE)
        message(STATUS "C#: используется Mono-компилятор ${MCS_EXECUTABLE} — цель 'csharp' включена")
        add_custom_target(csharp ALL
            COMMENT "[C#] Компиляция Program.cs -> StatusProxy.exe (Mono)"
            COMMAND ${MCS_EXECUTABLE} -out:"${CMAKE_BINARY_DIR}/StatusProxy.exe"
                    "${PYSCHOOL_ROOT}/src/csharp/Program.cs"
            BYPRODUCTS "${CMAKE_BINARY_DIR}/StatusProxy.exe")
    elseif(CSC_EXECUTABLE)
        message(STATUS "C#: используется ${CSC_EXECUTABLE} — цель 'csharp' включена")
        add_custom_target(csharp ALL
            COMMENT "[C#] Компиляция Program.cs -> StatusProxy.exe"
            COMMAND ${CSC_EXECUTABLE} -out:"${CMAKE_BINARY_DIR}/StatusProxy.exe"
                    "${PYSCHOOL_ROOT}/src/csharp/Program.cs"
            BYPRODUCTS "${CMAKE_BINARY_DIR}/StatusProxy.exe")
    else()
        # dotnet: собираем csproj, сгенерированный ниже
        message(STATUS "C#: используется .NET SDK ${DOTNET_EXECUTABLE} — цель 'csharp' включена")
        set(CSHARP_PROJ "${CMAKE_BINARY_DIR}/statusproxy/StatusProxy.csproj")
        file(WRITE "${CMAKE_BINARY_DIR}/statusproxy/Program.cs" "")
        configure_file("${PYSCHOOL_ROOT}/src/csharp/StatusProxy.csproj.in"
                       "${CSHARP_PROJ}" COPYONLY)
        file(COPY "${PYSCHOOL_ROOT}/src/csharp/Program.cs"
             DESTINATION "${CMAKE_BINARY_DIR}/statusproxy")
        add_custom_target(csharp ALL
            COMMENT "[C#] dotnet build StatusProxy"
            COMMAND ${DOTNET_EXECUTABLE} build -c Release
                    "${CMAKE_BINARY_DIR}/statusproxy/StatusProxy.csproj"
                    -o "${CMAKE_BINARY_DIR}/csharp")
    endif()
    # Резервная статус-панель на C++ — собирается всегда,
    # пригодится, если C#-сервис не запустится.
    add_executable(statusproxy_cpp src/cpp/statusproxy.cpp)
    set_target_properties(statusproxy_cpp PROPERTIES OUTPUT_NAME "statusproxy_cpp")
else()
    message(WARNING "C#-компилятор (dotnet/mcs/csc) НЕ найден — вместо C#-панели "
                    "будет собрана резервная статус-панель на C++ (build/statusproxy_cpp)")
    add_executable(statusproxy_cpp src/cpp/statusproxy.cpp)
    set_target_properties(statusproxy_cpp PROPERTIES OUTPUT_NAME "statusproxy_cpp")
endif()

# ---------------------------------------------------------------------------
# 4. Проверка готовности (собрать всё и показать список модулей)
# ---------------------------------------------------------------------------
add_custom_target(check
    COMMAND ${CMAKE_COMMAND} -E echo "=== Модули платформы «Python-Школа» ==="
    COMMAND ${CMAKE_COMMAND} -E list ${CMAKE_BINARY_DIR}
    DEPENDS pyschool_helpers
    COMMENT "Список собранных артефактов в build/")

message(STATUS "")
message(STATUS "Проект «Python-Школа»: C++ = OK, Java = ${JAVAC_EXECUTABLE}, C# = ok")
message(STATUS "После сборки запуск сайта:  python3 src/python/server.py 8080")
message(STATUS "")
