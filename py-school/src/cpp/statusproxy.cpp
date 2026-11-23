/* ==========================================================================
 * statusproxy.cpp — резервная реализация статус-панели (порт 8081) на C++.
 *
 * Используется CMake, если в системе нет компилятора C# (dotnet/mcs/csc),
 * чтобы страница статуса «Python-Школа» всё равно была доступна в LAN.
 * Опрашивает Python-сервер http://127.0.0.1:8080/api/stats по HTTP и
 * отдаёт собственную HTML-страницу. Только POSIX-сокеты, без зависимостей.
 * ========================================================================== */

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cstring>
#include <iostream>
#include <sstream>
#include <string>

static std::string html_escape(const std::string& in) {
    std::string out;
    for (char c : in) {
        switch (c) {
            case '<': out += "&lt;"; break;
            case '>': out += "&gt;"; break;
            case '&': out += "&amp;"; break;
            case '"': out += "&quot;"; break;
            default: out += c;
        }
    }
    return out;
}

// Простой HTTP GET к 127.0.0.1:port по пути path (однострочный запрос).
static std::string http_get(int port, const std::string& path) {
    int fd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return "";

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(port));
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);

    timeval tv{3, 0};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    if (::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        ::close(fd);
        return "";
    }

    std::ostringstream req;
    req << "GET " << path << " HTTP/1.0\r\nHost: 127.0.0.1\r\n"
        << "Connection: close\r\n\r\n";
    std::string r = req.str();
    ::send(fd, r.data(), r.size(), MSG_NOSIGNAL);

    std::string body;
    char buf[4096];
    ssize_t n;
    bool headers_done = false;
    while ((n = ::recv(fd, buf, sizeof(buf), 0)) > 0) {
        body.append(buf, static_cast<size_t>(n));
        if (!headers_done) {
            size_t pos = body.find("\r\n\r\n");
            if (pos != std::string::npos) {
                body.erase(0, pos + 4);
                headers_done = true;
            }
        }
    }
    ::close(fd);
    return headers_done ? body : std::string();
}

static std::string build_page(const std::string& stats_json) {
    std::ostringstream h;
    h << "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
      << "<title>Python-Школа — статус (резервный C++-прокси)</title>"
      << "<style>body{font-family:sans-serif;background:#1e1e2e;color:#cdd6f4;"
      << "display:flex;justify-content:center;padding-top:60px}"
      << ".card{background:#313244;padding:30px 40px;border-radius:12px;"
      << "max-width:640px;width:100%}pre{background:#11111b;padding:16px;"
      << "border-radius:8px;overflow:auto}a{color:#89b4fa}</style></head>"
      << "<body><div class='card'>"
      << "<h1>🟦 Статус платформы «Python-Школа»</h1>"
      << "<p>Эта страница сгенерирована <b>C++-прокси</b> (резерв вместо C#), "
         "который получает данные по HTTP от <b>Python-сервера</b>.</p>"
      << "<p><a href='http://localhost:8080/'>→ Перейти на основной сайт (порт 8080)</a></p>"
      << "<h2>Данные из API (JSON):</h2><pre>"
      << html_escape(stats_json.empty() ? "{\"error\": \"Python-сервер недоступен\"}"
                                        : stats_json)
      << "</pre><p><small>StatusProxy (C++ fallback) v1.0</small></p>"
      << "</div></body></html>";
    return h.str();
}

int main(int argc, char** argv) {
    int port = 8081;
    if (argc > 1) port = std::atoi(argv[1]);

    int srv = ::socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) { perror("socket"); return 1; }
    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in bind_addr{};
    bind_addr.sin_family = AF_INET;
    bind_addr.sin_addr.s_addr = INADDR_ANY;  // доступен из локальной сети
    bind_addr.sin_port = htons(static_cast<uint16_t>(port));
    if (::bind(srv, reinterpret_cast<sockaddr*>(&bind_addr), sizeof(bind_addr)) < 0) {
        perror("bind");
        return 1;
    }
    ::listen(srv, 16);
    std::cout << "[C++] Резервная статус-панель запущена: http://0.0.0.0:"
              << port << "/" << std::endl;

    while (true) {
        int client = ::accept(srv, nullptr, nullptr);
        if (client < 0) continue;

        char reqbuf[1024] = {0};
        ::recv(client, reqbuf, sizeof(reqbuf) - 1, 0);

        std::string stats = http_get(8080, "/api/stats");
        std::string page = build_page(stats);

        std::ostringstream resp;
        resp << "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
             << "Content-Length: " << page.size() << "\r\nConnection: close\r\n\r\n"
             << page;
        std::string out = resp.str();
        ::send(client, out.data(), out.size(), MSG_NOSIGNAL);
        ::close(client);
    }
}
