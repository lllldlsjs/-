import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;

/**
 * Main.java — сервис утилит на Java.
 *
 * Работает в режиме JSON-RPC через stdin/stdout: Python-сервер
 * (native_bridge.py) запускает jar и отправляет строки вида
 *   {"method":"wordstats","params":{"text":"..."}}
 * получая в ответ строку вида
 *   {"result":{"words":3,"chars":17,"lines":1}}
 *
 * Поддерживаемые методы: version, ping, wordstats, exit.
 */
public class Main {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        BufferedReader in = new BufferedReader(
                new InputStreamReader(System.in, StandardCharsets.UTF_8));

        String line;
        while ((line = in.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) continue;

            String method = extractString(line, "method");
            String response;

            switch (method == null ? "" : method) {
                case "version":
                    response = "{\"result\": \"pyschool_utils (Java) v1.0, JVM " +
                            System.getProperty("java.version") + "\"}";
                    break;
                case "ping":
                    response = "{\"result\": \"pong\"}";
                    break;
                case "wordstats": {
                    String text = extractString(line, "text");
                    if (text == null) text = "";
                    int words = text.trim().isEmpty() ? 0 : text.trim().split("\\s+").length;
                    int chars = text.length();
                    int lines = text.isEmpty() ? 0 : text.split("\n", -1).length;
                    long nonAscii = text.chars().filter(c -> c > 127).count();
                    response = "{\"result\": {\"words\": " + words +
                            ", \"chars\": " + chars +
                            ", \"lines\": " + lines +
                            ", \"non_ascii\": " + nonAscii + "}}";
                    break;
                }
                case "exit":
                    response = "{\"result\": \"bye\"}";
                    out.println(response);
                    return;
                default:
                    response = "{\"error\": \"unknown method: " + escape(method) + "\"}";
            }
            out.println(response);
        }
    }

    /** Очень простой поиск значения строкового поля "key":"value" в JSON. */
    private static String extractString(String json, String key) {
        String search = "\"" + key + "\":\"";
        int i = json.indexOf(search);
        if (i < 0) return null;
        i += search.length();
        StringBuilder sb = new StringBuilder();
        while (i < json.length()) {
            char c = json.charAt(i);
            if (c == '\\' && i + 1 < json.length()) {
                char n = json.charAt(++i);
                switch (n) {
                    case 'n': sb.append('\n'); break;
                    case 't': sb.append('\t'); break;
                    case '"': sb.append('"'); break;
                    case '\\': sb.append('\\'); break;
                    case 'u':
                        if (i + 4 < json.length()) {
                            sb.append((char) Integer.parseInt(json.substring(i + 1, i + 5), 16));
                            i += 4;
                        }
                        break;
                    default: sb.append(n);
                }
            } else if (c == '"') {
                break;
            } else {
                sb.append(c);
            }
            i++;
        }
        return sb.toString();
    }

    private static String escape(String s) {
        if (s == null) return "null";
        return s.replace("\\", "\\\\").replace("\"", "'");
    }
}
