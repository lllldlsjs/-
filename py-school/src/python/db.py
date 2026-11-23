# -*- coding: utf-8 -*-
"""
db.py — слой работы с базой данных (SQLite).
Хранит пользователей, курсы, уроки и оценки учебной платформы «Python-Школа».
"""

import json
import os
import sqlite3
import threading

DB_PATH = os.environ.get(
    "PYSCHOOL_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "data", "school.db")
)

_lock = threading.Lock()


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',      -- student | teacher
    full_name TEXT NOT NULL DEFAULT '',
    group_name TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    lesson_id INTEGER,
    grade INTEGER NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);
"""


def init_db():
    """Создаёт таблицы и наполняет базу начальными данными."""
    with _lock, _connect() as conn:
        conn.executescript(SCHEMA)

        # --- Начальные пользователи -------------------------------------
        students = [
            ("123456",  "123456",  "Иванов Иван Иванович",   "ПИ-21-1"),
            ("12345",   "12345",   "Петрова Анна Сергеевна", "ПИ-21-1"),
            ("1234567", "1234567", "Сидоров Пётр Петрович",  "ПИ-21-2"),
        ]
        for login, pwd, name, group in students:
            cur = conn.execute("SELECT id FROM users WHERE login=?", (login,))
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO users (login, password, role, full_name, group_name) "
                    "VALUES (?, ?, 'student', ?, ?)", (login, pwd, name, group))

        cur = conn.execute("SELECT id FROM users WHERE login='admin'")
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO users (login, password, role, full_name, group_name) "
                "VALUES ('admin', 'admin', 'teacher', 'Учитель Информатики', '')")

        # --- Начальный курс по Python ------------------------------------
        cur = conn.execute("SELECT id FROM courses LIMIT 1")
        if cur.fetchone() is None:
            cur = conn.execute(
                "INSERT INTO courses (title, description) VALUES (?, ?)",
                ("Основы Python",
                 "Учебный курс для начинающих: синтаксис, переменные, типы данных."))
            course_id = cur.lastrowid
            lessons = [
                ("Введение в Python",
                 "Python — интерпретируемый язык программирования высокого уровня.\n"
                 "Он прост в изучении и широко применяется: веб-разработка, анализ данных,\n"
                 "автоматизация, машинное обучение.\n\n"
                 "Первая программа:\nprint('Привет, мир!')"),
                ("Переменные и типы данных",
                 "В Python переменная создаётся при первом присваивании:\n\n"
                 "age = 18            # int (целое число)\n"
                 "height = 1.75       # float (дробное число)\n"
                 "name = 'Анна'       # str (строка)\n"
                 "is_student = True   # bool (логический тип)\n\n"
                 "Тип переменной можно узнать функцией type()."),
                ("Условия и циклы",
                 "Условный оператор:\n\n"
                 "if age >= 18:\n    print('Взрослый')\nelse:\n    print('Ребёнок')\n\n"
                 "Циклы:\n\n"
                 "for i in range(5):\n    print(i)\n\n"
                 "while count < 10:\n    count += 1"),
            ]
            for pos, (title, content) in enumerate(lessons, 1):
                conn.execute(
                    "INSERT INTO lessons (course_id, position, title, content) "
                    "VALUES (?, ?, ?, ?)", (course_id, pos, title, content))

            # Стартовые оценки для студентов
            conn.execute("INSERT INTO grades (student_id, course_id, lesson_id, grade, comment) "
                         "VALUES (1, 1, 1, 5, 'Отличное введение')")
            conn.execute("INSERT INTO grades (student_id, course_id, lesson_id, grade, comment) "
                         "VALUES (2, 1, 1, 4, 'Хорошо, но внимательнее')")


# ---------- API для остальных модулей ----------

def check_login(login, password):
    """Возвращает dict пользователя при успешном входе, иначе None."""
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE login=? AND password=?", (login, password)).fetchone()
        return dict(row) if row else None


def get_user(user_id):
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_students():
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE role='student' ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def list_courses():
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM courses ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_course(course_id):
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        return dict(row) if row else None


def create_course(title, description):
    with _lock, _connect() as conn:
        cur = conn.execute("INSERT INTO courses (title, description) VALUES (?, ?)",
                           (title, description))
        return cur.lastrowid


def update_course(course_id, title, description, enabled):
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE courses SET title=?, description=?, enabled=? WHERE id=?",
            (title, description, 1 if enabled else 0, course_id))


def delete_course(course_id):
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM lessons WHERE course_id=?", (course_id,))
        conn.execute("DELETE FROM grades WHERE course_id=?", (course_id,))
        conn.execute("DELETE FROM courses WHERE id=?", (course_id,))


def list_lessons(course_id):
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM lessons WHERE course_id=? ORDER BY position", (course_id,)).fetchall()
        return [dict(r) for r in rows]


def add_lesson(course_id, title, content):
    with _lock, _connect() as conn:
        cur = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS p FROM lessons WHERE course_id=?",
            (course_id,))
        pos = cur.fetchone()["p"]
        cur = conn.execute(
            "INSERT INTO lessons (course_id, position, title, content) VALUES (?, ?, ?, ?)",
            (course_id, pos, title, content))
        return cur.lastrowid


def set_grade(student_id, course_id, grade, comment=""):
    """Выставляет/обновляет итоговую оценку студента по курсу."""
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT id FROM grades WHERE student_id=? AND course_id=? AND lesson_id IS NULL",
            (student_id, course_id)).fetchone()
        if row:
            conn.execute("UPDATE grades SET grade=?, comment=? WHERE id=?",
                         (grade, comment, row["id"]))
        else:
            conn.execute(
                "INSERT INTO grades (student_id, course_id, lesson_id, grade, comment) "
                "VALUES (?, ?, NULL, ?, ?)", (student_id, course_id, grade, comment))


def get_grades_for_student(student_id):
    with _lock, _connect() as conn:
        rows = conn.execute(
            """SELECT g.*, c.title AS course_title
               FROM grades g JOIN courses c ON c.id = g.course_id
               WHERE g.student_id=?""", (student_id,)).fetchall()
        return [dict(r) for r in rows]


def get_all_grades():
    with _lock, _connect() as conn:
        rows = conn.execute(
            """SELECT g.*, c.title AS course_title, u.full_name, u.login
               FROM grades g
               JOIN courses c ON c.id = g.course_id
               JOIN users u ON u.id = g.student_id""").fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"База инициализирована: {DB_PATH}")
    print(json.dumps(list_students(), ensure_ascii=False, indent=2))
