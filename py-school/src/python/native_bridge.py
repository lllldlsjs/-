# -*- coding: utf-8 -*-
"""
native_bridge.py — мост между Python и скомпилированными модулями C++ / Java.

* C++   : подгружает libpyschool_helpers.so через ctypes.
* Java  : запускает pyschool_utils.jar в режиме JSON-RPC по stdio
          (Python пишет запрос в stdin JVM, читает ответ из stdout).

Если нативный компонент недоступен, используются чистые Python-аналоги,
поэтому сайт работает в любом случае (смешанный режим деградирует мягко).
"""

import ctypes
import json
import os
import shutil
import subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BUILD = os.path.join(_ROOT, "build")


def _find_file(name):
    for base in (_BUILD, os.path.join(_BUILD, "bin"), _ROOT):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


# ------------------------- C++ через ctypes -------------------------

class _CppBridge:
    def __init__(self):
        self.lib = None
        path = _find_file("libpyschool_helpers.so")
        if path:
            try:
                self.lib = ctypes.CDLL(path)
                self.lib.ps_version.restype = ctypes.c_char_p
                self.lib.ps_average_grade.restype = ctypes.c_double
                self.lib.ps_average_grade.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
                self.lib.ps_is_prime.restype = ctypes.c_int
                self.lib.ps_is_prime.argtypes = [ctypes.c_longlong]
                self.lib.ps_hash_str.restype = ctypes.c_ulonglong
                self.lib.ps_hash_str.argtypes = [ctypes.c_char_p]
            except OSError:
                self.lib = None

    @property
    def available(self):
        return self.lib is not None

    def version(self):
        return self.lib.ps_version().decode() if self.available else "C++ библиотека не загружена"

    def average_grade(self, grades):
        if not grades:
            return 0.0
        if self.available:
            arr = (ctypes.c_int * len(grades))(*grades)
            return self.lib.ps_average_grade(arr, len(grades))
        return sum(grades) / float(len(grades))

    def is_prime(self, n):
        if self.available:
            return bool(self.lib.ps_is_prime(n))
        if n < 2:
            return False
        i = 2
        while i * i <= n:
            if n % i == 0:
                return False
            i += 1
        return True

    def hash_str(self, s):
        if self.available:
            return self.lib.ps_hash_str(s.encode("utf-8"))
        h = 1469598103934665603
        for b in s.encode("utf-8"):
            h = ((h ^ b) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
        return h


cpp = _CppBridge()


# ------------------------- Java через JSON-RPC/stdio -------------------------

class _JavaBridge:
    def __init__(self):
        self.proc = None
        jar = _find_file("pyschool_utils.jar")
        java = shutil.which("java")
        if jar and java:
            try:
                self.proc = subprocess.Popen(
                    [java, "-jar", jar],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, bufsize=1)
            except OSError:
                self.proc = None

    @property
    def available(self):
        return self.proc is not None and self.proc.poll() is None

    def _call(self, method, **params):
        if not self.available:
            return None
        req = {"method": method, "params": params}
        try:
            self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                return None
            return json.loads(line)
        except (OSError, ValueError):
            return None

    def version(self):
        r = self._call("version")
        return r.get("result") if r else "Java-сервис не запущен"

    def word_stats(self, text):
        r = self._call("wordstats", text=text)
        if r and "result" in r:
            return r["result"]
        # python-фолбэк
        words = text.split()
        return {"words": len(words), "chars": len(text),
                "lines": max(1, text.count("\n") + 1)}

    def ping(self):
        r = self._call("ping")
        return r.get("result") if r else None

    def shutdown(self):
        if self.available:
            try:
                self._call("exit")
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()


java = _JavaBridge()


if __name__ == "__main__":
    print("C++ :", cpp.version(), "| prime(97) =", cpp.is_prime(97),
          "| avg([5,4,5]) =", cpp.average_grade([5, 4, 5]))
    print("Java:", java.version(), "| stats =", java.word_stats("Привет мир Python"))
    java.shutdown()
