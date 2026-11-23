// perf_helper.cpp — реализация вспомогательных «быстрых» функций на C++.
// Компилируется в общую библиотеку libpyschool_helpers.so, которую
// загружает Python-сервер через ctypes (см. src/python/native_bridge.py).

#include "perf_helper.h"

#include <string>
#include <vector>
#include <numeric>
#include <cmath>

namespace {

bool is_prime_impl(long long n) {
    if (n < 2) return false;
    if (n < 4) return true;
    if (n % 2 == 0) return false;
    for (long long i = 3; i * i <= n; i += 2) {
        if (n % i == 0) return false;
    }
    return true;
}

unsigned long long fnv1a(const std::string& s) {
    unsigned long long h = 1469598103934665603ULL; // FNV offset basis (64-bit)
    for (unsigned char c : s) {
        h ^= c;
        h *= 1099511628211ULL;                     // FNV prime
    }
    return h;
}

} // namespace

extern "C" {

const char* ps_version() {
    static const std::string ver = "pyschool_helpers (C++) v1.0";
    return ver.c_str();
}

double ps_average_grade(const int* grades, int count) {
    if (grades == nullptr || count <= 0) return 0.0;
    const std::vector<int> v(grades, grades + count);
    double sum = std::accumulate(v.begin(), v.end(), 0.0);
    return sum / static_cast<double>(count);
}

int ps_is_prime(long long n) {
    return is_prime_impl(n) ? 1 : 0;
}

unsigned long long ps_hash_str(const char* s) {
    if (s == nullptr) return 0ULL;
    return fnv1a(std::string(s));
}

} // extern "C"
