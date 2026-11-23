// main.js — клиентский JavaScript платформы «Python-Школа».
// 1) Загружает статистику платформы (/api/stats) на главной странице.
// 2) Счётчик текста через Java-сервис (/api/textstats) на странице курса.
// 3) Сохранение оценок в кабинете учителя (POST /teacher/grade).

document.addEventListener('DOMContentLoaded', () => {

  // ---------- Статистика на главной ----------
  const statsBox = document.getElementById('stats-box');
  if (statsBox) {
    fetch('/api/stats')
      .then(r => r.json())
      .then(data => {
        statsBox.textContent =
          `Платформа : ${data.platform}\n` +
          `Курсы     : ${data.courses}\n` +
          `Студенты  : ${data.students}\n` +
          `Оценок    : ${data.grades_count}\n` +
          `Средний балл (C++): ${data.average_grade}\n` +
          `C++ модуль: ${data.cpp_library}\n` +
          `Java модуль: ${data.java_service}`;
      })
      .catch(() => { statsBox.textContent = 'Не удалось загрузить статистику.'; });
  }

  // ---------- Java-виджет: счётчик текста ----------
  const tsBtn = document.getElementById('ts-btn');
  if (tsBtn) {
    tsBtn.addEventListener('click', () => {
      const text = document.getElementById('ts-input').value || '';
      const res = document.getElementById('ts-result');
      res.textContent = 'Считаем (Java)…';
      const body = new URLSearchParams();
      body.set('text', text);
      fetch('/api/textstats', { method: 'POST', body })
        .then(r => r.json())
        .then(s => {
          res.textContent =
            `Слов: ${s.words} · Символов: ${s.chars} · Строк: ${s.lines}` +
            (s.non_ascii !== undefined ? ` · Нелатиница/не-ASCII: ${s.non_ascii}` : '');
        })
        .catch(() => { res.textContent = 'Java-сервис недоступен.'; });
    });
  }

  // ---------- Кабинет учителя: сохранение оценок ----------
  const saveBtn = document.getElementById('save-grades');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const status = document.getElementById('save-status');
      status.textContent = 'Сохраняем…';
      let saved = 0;

      const cells = {};
      document.querySelectorAll('.grade-input').forEach(inp => {
        const tr = inp.closest('tr');
        const sid = tr.querySelector('input[name=student_id]');
        if (!sid) return;
        cells[sid.value + ':' + inp.dataset.course] = { grade: inp.value, comment: '' };
      });
      document.querySelectorAll('.comment-input').forEach(inp => {
        const tr = inp.closest('tr');
        const sid = tr.querySelector('input[name=student_id]');
        if (!sid) return;
        const key = sid.value + ':' + inp.dataset.course;
        if (cells[key]) cells[key].comment = inp.value;
      });

      for (const [key, val] of Object.entries(cells)) {
        const [studentId, courseId] = key.split(':');
        if (!val.grade) continue;
        const body = new URLSearchParams();
        body.set('student_id', studentId);
        body.set('course_id', courseId);
        body.set('grade', val.grade);
        body.set('comment', val.comment);
        try {
          await fetch('/teacher/grade', { method: 'POST', body });
          saved++;
        } catch (e) { /* ignore per-cell errors */ }
      }
      status.textContent = `Сохранено записей: ${saved}. Обновляем страницу…`;
      setTimeout(() => location.reload(), 600);
    });
  }
});
