// Program.cs — сервис на C# (.NET / Mono).
// Небольшой HTTP-прокси «статус-панель»: запускается рядом с Python-сервером,
// опрашивает его API (/api/stats) и отдаёт собственную HTML-страницу со сводкой.
// Демонстрирует работу C# в связке с Python-сайтом в локальной сети.

using System;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;

namespace PySchool.StatusProxy
{
    internal static class Program
    {
        private const string BackendUrl = "http://127.0.0.1:8080/api/stats";
        private const string ListenPrefix = "http://localhost:8081/";

        private static int Main(string[] args)
        {
            int port = 8081;
            if (args.Length > 0 && int.TryParse(args[0], out int p))
            {
                port = p;
            }

            var listener = new HttpListener();
            listener.Prefixes.Clear();
            listener.Prefixes.Add($"http://localhost:{port}/");

            try
            {
                listener.Start();
            }
            catch (HttpListenerException ex)
            {
                Console.Error.WriteLine("[C#] Не удалось запустить слушатель на порту " + port + ": " + ex.Message);
                return 1;
            }

            Console.WriteLine($"[C#] Сервис статус-панели запущен: http://localhost:{port}/");
            Console.WriteLine($"[C#] Источник данных: {BackendUrl}");

            while (true)
            {
                HttpListenerContext ctx;
                try
                {
                    ctx = listener.GetContext();
                }
                catch (Exception)
                {
                    break;
                }
                ThreadPool.QueueUserWorkItem(_ => Handle(ctx));
            }

            listener.Stop();
            return 0;
        }

        private static void Handle(HttpListenerContext ctx)
        {
            try
            {
                string statsJson = FetchStats();
                string html = BuildHtml(statsJson);
                byte[] buf = Encoding.UTF8.GetBytes(html);
                ctx.Response.ContentType = "text/html; charset=utf-8";
                ctx.Response.ContentLength64 = buf.Length;
                ctx.Response.OutputStream.Write(buf, 0, buf.Length);
            }
            catch (Exception ex)
            {
                byte[] err = Encoding.UTF8.GetBytes("<h1>Ошибка C#-сервиса</h1><pre>" +
                                                    WebUtility.HtmlEncode(ex.Message) + "</pre>");
                ctx.Response.StatusCode = 500;
                ctx.Response.ContentType = "text/html; charset=utf-8";
                ctx.Response.OutputStream.Write(err, 0, err.Length);
            }
            finally
            {
                ctx.Response.Close();
            }
        }

        private static string FetchStats()
        {
            try
            {
                var req = (HttpWebRequest)WebRequest.Create(BackendUrl);
                req.Timeout = 3000;
                using (var resp = (HttpWebResponse)req.GetResponse())
                using (var sr = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                {
                    return sr.ReadToEnd();
                }
            }
            catch (Exception ex)
            {
                return "{\"error\": \"" + ex.Message.Replace("\"", "'") + "\"}";
            }
        }

        private static string BuildHtml(string statsJson)
        {
            var sb = new StringBuilder();
            sb.Append("<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>");
            sb.Append("<title>Python-Школа — статус (C#-сервис)</title>");
            sb.Append("<style>body{font-family:sans-serif;background:#1e1e2e;color:#cdd6f4;");
            sb.Append("display:flex;justify-content:center;padding-top:60px}");
            sb.Append(".card{background:#313244;padding:30px 40px;border-radius:12px;max-width:640px;width:100%}");
            sb.Append("pre{background:#11111b;padding:16px;border-radius:8px;overflow:auto}");
            sb.Append("a{color:#89b4fa}</style></head><body><div class='card'>");
            sb.Append("<h1>🟦 Статус платформы «Python-Школа»</h1>");
            sb.Append("<p>Эта страница сгенерирована <b>C#-сервисом</b> (.NET), ");
            sb.Append("который получает данные по HTTP от <b>Python-сервера</b>. </p>");
            sb.Append("<p><a href='http://localhost:8080/'>→ Перейти на основной сайт (порт 8080)</a></p>");
            sb.Append("<h2>Данные из API (JSON):</h2>");
            sb.Append("<pre>" + WebUtility.HtmlEncode(PrettyJson(statsJson)) + "</pre>");
            sb.Append("<p><small>C# StatusProxy v1.0 · Thread: #" +
                      Thread.CurrentThread.ManagedThreadId + "</small></p>");
            sb.Append("</div></body></html>");
            return sb.ToString();
        }

        // Минимальное «украшение» JSON — вставляем переносы после запятых и скобок.
        private static string PrettyJson(string json)
        {
            var sb = new StringBuilder();
            int indent = 0;
            bool inStr = false;
            foreach (char c in json)
            {
                if (c == '"' && (sb.Length == 0 || sb[sb.Length - 1] != '\\')) inStr = !inStr;
                if (!inStr && (c == '{' || c == '['))
                {
                    sb.Append(c).Append('\n').Append(new string(' ', ++indent * 2));
                }
                else if (!inStr && (c == '}' || c == ']'))
                {
                    sb.Append('\n').Append(new string(' ', --indent * 2)).Append(c);
                }
                else if (!inStr && c == ',')
                {
                    sb.Append(c).Append('\n').Append(new string(' ', indent * 2));
                }
                else if (!inStr && c == ':')
                {
                    sb.Append(": ");
                }
                else
                {
                    sb.Append(c);
                }
            }
            return sb.ToString();
        }
    }
}
