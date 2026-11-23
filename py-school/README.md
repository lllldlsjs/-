# 🐍 Python-Школа — учебный сайт по программированию на Python

Учебная платформа доступна **из локальной сети** (сервер слушает `0.0.0.0`).
Стек смешанный, код написан на разных языках:

| Язык   | Компонент                                   | Файл(ы)                          |
|--------|---------------------------------------------|----------------------------------|
| Python | HTTP-сервер сайта, SQLite, сессии           | `src/python/server.py`, `db.py`, `auth.py` |
| C++    | Библиотека быстрых вычислений (ctypes)      | `src/cpp/perf_helper.cpp` → `libpyschool_helpers.so` |
| Java   | Сервис статистики текста (JSON-RPC/stdio)   | `src/java/Main.java` → `pyschool_utils.jar` |
| C#     | Статус-панель на порту 8081                 | `src/csharp/Program.cs` → `StatusProxy.exe` |
| JS/CSS | Интерфейс браузера                          | `web/static/js/main.js`, `web/static/css/style.css` |

## Сборка (Linux, только CMake — ничего ставить не нужно)

```bash
cmake -S . -B build
cmake --build build
# или просто: ./scripts/build.sh
```

CMake соберёт:
* `build/libpyschool_helpers.so` — C++ (обязательно);
* `build/pyschool_utils.jar`     — Java, если в системе есть `javac`/`jar`;
* `build/StatusProxy.exe`        — C#, если есть `mcs`/`csc`/`dotnet`
  (иначе автоматически соберётся резервная панель `build/statusproxy_cpp` на C++).

Если Java/C#-компиляторов нет — сайт всё равно работает: в `native_bridge.py`
есть чистые Python-аналоги этих функций.

> **Примечание про ошибку `javac: libjli.so: cannot open shared object file`.**
> Это сломанный пакет JDK (симлинк `/usr/bin/javac` есть, а самих библиотек
> нет). Теперь CMake при конфигурации проверяет работоспособность `javac`
> и просто пропускает Java-цель с предупреждением — сборка больше не падает.
> Чтобы всё-таки собрать Java-модуль, почините JDK:
> ```bash
> sudo apt install --reinstall openjdk-17-jdk   # или ваш дистрибутивный пакет
> ```

## Запуск

```bash
python3 src/python/server.py 8080            # основной сайт
mono build/StatusProxy.exe 8081              # статус-панель C# (опционально)
# либо без Mono: ./build/statusproxy_cpp 8081
```

Открыть из любой машины локальной сети: `http://IP-МАШИНЫ:8080/`
(при необходимости разрешите порт в firewall:
`sudo ufw allow 8080/tcp`)

## Учётные записи

| Роль     | Логин   | Пароль  |
|----------|---------|---------|
| Студент  | `123456`  | `123456`  |
| Студент  | `12345`   | `12345`   |
| Студент  | `1234567` | `1234567` |
| Учитель  | `admin`   | `admin`   |

Студенты видят уроки курса и свои оценки; учитель управляет курсами,
уроками и выставляет оценки. База SQLite создаётся автоматически в `data/school.db`.

## Готовая сборка (папка dist/)

Я собрал проект через CMake и выложил результат в отдельную папку **`py-school/dist/`**:

```
dist/
├── pyschool-linux/          # готовая сборка, запускать отсюда
│   ├── run.sh               # ./run.sh — запускает сайт (8080) и статус-панель (8081)
│   ├── bin/statusproxy_cpp  # собранный статус-прокси (C++)
│   ├── lib/libpyschool_helpers.so  # собранная C++-библиотека (ctypes)
│   ├── share/jar/pyschool_utils.jar# собранный Java-архив
│   └── src/ web/ scripts/   # код сайта
└── pyschool-linux.tar.gz    # тот же архив для переноса на другую машину
```

Запуск без сборки: `tar xzf pyschool-linux.tar.gz && ./pyschool-linux/run.sh`
(нужен только python3; сборка через cmake не требуется).
