// perf_helper.h — публичный C-API библиотеки pyschool_helpers (C++).
// Python-сервер загружает её через ctypes и вызывает для «быстрых» вычислений.
#ifndef PYSCHOOL_PERF_HELPER_H
#define PYSCHOOL_PERF_HELPER_H

#ifdef __cplusplus
extern "C" {
#endif

// Возвращает версию библиотеки статической строкой.
const char* ps_version();

// Средний балл по массиву целых оценок (0 возвращает 0.0 для пустого массива).
double ps_average_grade(const int* grades, int count);

// Быстрая проверка: является ли число простым (демонстрация C++-вычислений).
int ps_is_prime(long long n);

// Простая хеш-функция строки (FNV-1a) — используется как демо-«солить» токены.
unsigned long long ps_hash_str(const char* s);

#ifdef __cplusplus
}
#endif

#endif // PYSCHOOL_PERF_HELPER_H
