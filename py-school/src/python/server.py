# -*- coding: utf-8 -*-
"""
server.py — главный HTTP-сервер учебной платформы «Python-Школа» (чистый Python).

Архитектура смешанного стека:
  * Python : этот сервер — маршрутизация, сессии, HTML-шаблоны, SQLite;
  * C++    : libpyschool_helpers.so — быстрые вычисления (ctypes, native_bridge);
  * Java   : pyschool_utils.jar — сервис статистики текста (JSON-RPC по stdio);
  * C#     : отдельный процесс StatusProxy (порт 8081) — страница статуса;
  * HTML/CSS/JS : интерфейс в web/.

Запуск:  python3 server.py [порт]      (по умолчанию 8080)
"""

import html
import json
import mimetypes
import os
import sys
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth          # noqa: E402
import db            # noqa: E402
import native_bridge as nb  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB = os.path.join(_ROOT, "web")

db.init_db()


# ---------- Мини-шаблонизатор ----------

def render(template_name, **ctx):
    path = os.path.join(WEB, "templates", template_name)
    with open(path, encoding="utf-8") as f:
        tpl = f.read()
    body = _fill(tpl, ctx)
    layout_path = os.path.join(WEB, "templates", "layout.html")
    with open(layout_path, encoding="utf-8") as f:
        layout = f.read()
    ctx.setdefault("user", None)
    page_title = html.escape(ctx.get("title", "Python-Школа"))
    nav = _nav(ctx.get("user"))
    footer_extra = ("C++: %s · Java: %s" % (html.escape(nb.cpp.version()),
                                            html.escape(str(nb.java.version()))))
    out = layout.replace("{{title}}", page_title) \
                .replace("{{nav}}", nav) \
                .replace("{{content}}", body) \
                .replace("{{footer}}", footer_extra)
    return out


def _fill(tpl, ctx):
    """Подстановка {{var}} и блоков {%for x in list%}...{%endfor%} / {%if v%}."""
    import re

    def expand_for(text):
        # Тело {%for%} не должно содержать других {%for%}/{%endfor%};
        # регулярка ищет самое ВНУТРЕННЕЕ совпадение, поэтому вложенные
        # циклы (например {%for cell in row.cells%} внутри {%for row%})
        # разворачиваются корректно за несколько проходов.
        pattern = re.compile(
            r"\{%for\s+(\w+)\s+in\s+(\w+)%\}"
            r"((?:(?!\{%for\s|\{%endfor%\}).)*?)\{%endfor%\}", re.S)
        while True:
            m = pattern.search(text)
            if not m:
                return text
            var, key, inner = m.groups()
            # Если список лежит в контексте под составным именем
            # (например "row.cells" из-за вложенного цикла), ищем его в item.
            if "." in key:
                holder_var, field = key.split(".", 1)
                holder = ctx.get(holder_var)
                items = (holder.get(field, []) or []) if isinstance(holder, dict) else []
            else:
                items = ctx.get(key, []) or []
            parts = []
            for item in items:
                sub = dict(ctx)
                sub["__loop_" + var] = item
                if isinstance(item, dict):
                    sub[var] = item
                    def repl(mm, _item=item, _ctx=ctx):
                        field = mm.group(1)
                        val = _item.get(field, _ctx.get(field, ""))
                        return html.escape(str(val))
                    chunk = re.sub(r"\{\{\s*" + var + r"\.(\w+)\s*\}\}", repl, inner)
                else:
                    sub[var] = item
                    chunk = re.sub(r"\{\{\s*" + var + r"\s*\}\}",
                                   lambda mm: html.escape(str(item)), inner)
                chunk = _fill(chunk, sub)
                parts.append(chunk)
            text = text[:m.start()] + "".join(parts) + text[m.end():]

    def expand_if(text):
        # Сначала неинвертированные условия {%if v%}...{%else%}...{%endif%},
        # затем только {%if v%}...{%endif%} (без вложенных if внутри).
        pattern_else = re.compile(
            r"\{%if\s+(\w+)%\}((?:(?!\{%if\s|\{%endif%\}).)*?)\{%else%\}"
            r"((?:(?!\{%if\s|\{%endif%\}).)*?)\{%endif%\}", re.S)
        while True:
            m = pattern_else.search(text)
            if not m:
                break
            cond, a, b = m.groups()
            text = text[:m.start()] + (a if ctx.get(cond) else b) + text[m.end():]

        pattern = re.compile(r"\{%if\s+(\w+)%\}((?:(?!\{%if\s).)*?)\{%endif%\}", re.S)
        while True:
            m = pattern.search(text)
            if not m:
                return text
            cond, inner = m.groups()
            val = ctx.get(cond)
            text = text[:m.start()] + (inner if val else "") + text[m.end():]

    text = expand_for(tpl)
    text = expand_if(text)

    def repl(mm):
        key = mm.group(1)
        if key in ctx and not isinstance(ctx[key], (dict, list)):
            v = ctx[key]
            return v if getattr(v, "_raw", False) else html.escape(str(v))
        # Переменная текущего цикла вида {{var.field}} на верхнем уровне
        # (остаётся после разворачивания вложенных {%for%}).
        if "." in key:
            holder_var, field = key.split(".", 1)
            holder = ctx.get("__loop_" + holder_var)
            if isinstance(holder, dict) and field in holder:
                return html.escape(str(holder[field]))
        return ""

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", repl, text)


class Raw(str):
    def __new__(cls, s):
        obj = super().__new__(cls, s)
        obj._raw = True
        return obj


def _nav(user):
    if not user:
        return "<a href='/login'>Вход</a>"
    role_link = ("/teacher" if user["role"] == "teacher" else "/course")
    role_name = "Кабинет учителя" if user["role"] == "teacher" else "Мои курсы"
    return (f"<a href='{role_link}'>{role_name}</a>"
            f"<span class='nav-user'>👤 {html.escape(user['full_name'])}</span>"
            f"<form method='post' action='/logout' class='inline'>"
            f"<button type='submit' class='link-btn'>Выйти</button></form>")


# ---------- Обработчик запросов ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "PySchool/1.0 (Python)"

    # --- утилиты ---
    def _send(self, code, body, ctype="text/html; charset=utf-8", extra_headers=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location, cookie=None):
        headers = {"Location": location}
        if cookie:
            headers["Set-Cookie"] = cookie
        self._send(302, "", "text/plain", headers)

    def _current_user(self):
        raw = self.headers.get("Cookie", "")
        ck = SimpleCookie()
        ck.load(raw)
        token = ck["psid"].value if "psid" in ck else None
        return auth.get_session_user(token), token

    def _read_form(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        data = self.rfile.read(length).decode("utf-8") if length else ""
        return {k: v[0] for k, v in urllib.parse.parse_qs(data).items()}

    def log_message(self, fmt, *args):
        sys.stderr.write("[Python] %s - %s\n" % (self.address_string(), fmt % args))

    # --- GET ---
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        if path.startswith("/static/"):
            return self._serve_static(path)
        if path == "/api/stats":
            return self._api_stats()

        user, _ = self._current_user()

        if path == "/":
            if user:
                return self._redirect("/teacher" if user["role"] == "teacher" else "/course")
            return self._page_index()
        if path == "/login":
            return self._send(200, render("login.html", title="Вход", error="", user=user))
        if path == "/course":
            if not user or user["role"] != "student":
                return self._redirect("/login")
            return self._page_course(user, query)
        if path == "/teacher":
            if not user or user["role"] != "teacher":
                return self._redirect("/login")
            return self._page_teacher(user)

        self._send(404, render("login.html", title="404",
                               error="Страница не найдена", user=user))

    # --- POST ---
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        form = self._read_form()
        user, token = self._current_user()

        if path == "/login":
            tok, usr = auth.login(form.get("login", ""), form.get("password", ""))
            if not usr:
                return self._send(200, render("login.html", title="Вход",
                                              error="Неверный логин или пароль", user=None))
            dest = "/teacher" if usr["role"] == "teacher" else "/course"
            cookie = f"psid={tok}; Path=/; HttpOnly"
            return self._redirect(dest, cookie)

        if path == "/logout":
            auth.logout(token)
            return self._redirect("/login", "psid=; Path=/; Max-Age=0")

        if not user:
            return self._redirect("/login")

        if path == "/teacher/course/new":
            db.create_course(form.get("title", "Новый курс"), form.get("description", ""))
            return self._redirect("/teacher")

        if path == "/teacher/course/update":
            cid = int(form.get("course_id", 0))
            db.update_course(cid, form.get("title", ""), form.get("description", ""),
                             form.get("enabled") == "on")
            return self._redirect("/teacher")

        if path == "/teacher/course/delete":
            db.delete_course(int(form.get("course_id", 0)))
            return self._redirect("/teacher")

        if path == "/teacher/lesson/new":
            db.add_lesson(int(form.get("course_id", 0)),
                          form.get("title", "Урок"), form.get("content", ""))
            return self._redirect("/teacher")

        if path == "/teacher/grade":
            db.set_grade(int(form.get("student_id", 0)), int(form.get("course_id", 0)),
                         max(1, min(5, int(form.get("grade", 2)))), form.get("comment", ""))
            return self._redirect("/teacher")

        if path == "/api/textstats":
            stats = nb.java.word_stats(form.get("text", ""))
            return self._send(200, json.dumps(stats, ensure_ascii=False),
                              "application/json; charset=utf-8")

        self._send(404, "Not found", "text/plain")

    # --- страницы ---
    def _page_index(self):
        self._send(200, render("index.html", title="Главная", user=None))

    def _page_course(self, user, query):
        courses = [c for c in db.list_courses() if c["enabled"]]
        course = courses[0] if courses else None
        if query.get("course") and courses:
            try:
                course = next(c for c in courses if c["id"] == int(query["course"]))
            except StopIteration:
                pass
        lessons = db.list_lessons(course["id"]) if course else []
        sel = int(query.get("lesson", 0) or 0)
        current = next((l for l in lessons if l["id"] == sel), lessons[0] if lessons else None)
        grades = db.get_grades_for_student(user["id"])
        avg = nb.cpp.average_grade([g["grade"] for g in grades])
        self._send(200, render("course.html", title="Мой курс", user=user,
                               courses=courses, course=course or {},
                               lessons=lessons, lesson=current or {},
                               grades=grades, avg="%.2f" % avg,
                               has_lesson=bool(current)))

    def _page_teacher(self, user):
        courses = db.list_courses()
        students = db.list_students()
        grades = db.get_all_grades()
        # карта (student_id, course_id) -> grade
        gmap = {(g["student_id"], g["course_id"]): g for g in grades}
        rows = []
        for s in students:
            cells = []
            for c in courses:
                g = gmap.get((s["id"], c["id"]))
                val = g["grade"] if g else ""
                comment = g["comment"] if g else ""
                cells.append({"course_id": c["id"], "grade": val, "comment": comment})
            rows.append({"id": s["id"], "name": s["full_name"], "group": s["group_name"],
                         "login": s["login"], "cells": cells})
        lessons_by_course = {c["id"]: db.list_lessons(c["id"]) for c in courses}
        self._send(200, render("teacher.html", title="Кабинет учителя", user=user,
                               courses=courses, students=students, rows=rows,
                               lessons_by_course=lessons_by_course))

    def _api_stats(self):
        students = db.list_students()
        grades = db.get_all_grades()
        avg = nb.cpp.average_grade([g["grade"] for g in grades])
        payload = {
            "platform": "Python-Школа",
            "python_server": True,
            "cpp_library": nb.cpp.version(),
            "java_service": nb.java.version(),
            "courses": len(db.list_courses()),
            "students": len(students),
            "grades_count": len(grades),
            "average_grade": round(avg, 2),
            "demo_cpp_is_prime_97": nb.cpp.is_prime(97),
        }
        self._send(200, json.dumps(payload, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def _serve_static(self, path):
        safe = os.path.normpath(path.lstrip("/"))
        full = os.path.join(_ROOT, "web", safe)
        if not full.startswith(os.path.join(_ROOT, "web")) or not os.path.isfile(full):
            return self._send(404, "Not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("=" * 60)
    print("  🐍 Python-Школа — учебный сайт о языке Python")
    print(f"  Python-сервер   : http://localhost:{port}/")
    print(f"  C# статус-панель: http://localhost:8081/  (запускается отдельно)")
    print(f"  C++ модуль      : {nb.cpp.version()}")
    print(f"  Java модуль     : {nb.java.version()}")
    print("  Тестовые аккаунты:")
    print("    студент: 123456/123456, 12345/12345, 1234567/1234567")
    print("    учитель: admin/admin")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        nb.java.shutdown()
        httpd.server_close()
        print("\nСервер остановлен.")


if __name__ == "__main__":
    main()
