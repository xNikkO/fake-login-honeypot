import socket
import requests
from datetime import datetime
from urllib.parse import parse_qs


WEBHOOK_URL = "WEBHOOK_URL_HERE"

PORT = 80

HOST = "0.0.0.0"

RATE_LIMIT_WINDOW_SECONDS = 300
RATE_LIMIT_MAX_ATTEMPTS = 3

login_attempts = {}


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Panel administracyjny</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: Arial, Helvetica, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { background: white; padding: 36px 32px; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); width: 340px; }
        h1 { margin: 0 0 18px; font-size: 22px; color: #1c1e21; text-align: center; }
        p.sub { margin: 0 0 20px; font-size: 13px; color: #65676b; text-align: center; }
        input { width: 100%; padding: 11px 12px; margin: 6px 0; border: 1px solid #dddfe2; border-radius: 6px; font-size: 15px; }
        input:focus { outline: none; border-color: #1877f2; }
        button { width: 100%; padding: 11px; background: #1877f2; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; margin-top: 10px; }
        button:hover { background: #145dbf; }
        .err { background: #ffebee; color: #c62828; padding: 10px; border-radius: 6px; font-size: 13px; text-align: center; margin-bottom: 12px; }
    </style>
</head>
<body>
    <form class="box" method="POST" action="/">
        <h1>Panel administracyjny</h1>
        <p class="sub">Zaloguj sie, aby kontynuowac</p>
        {ERROR}
        <input type="text" name="username" placeholder="Login" autofocus required>
        <input type="password" name="password" placeholder="Haslo" required>
        <button type="submit">Zaloguj sie</button>
    </form>
</body>
</html>"""


def send_to_discord(message):
    data = {"content": message}

    try:
        response = requests.post(WEBHOOK_URL, json=data, timeout=5)

        if response.status_code == 204:
            print("[+] Powiadomienie wyslane na Discord.")
        else:
            print(f"[!] Blad wysylania na Discord. Kod odpowiedzi: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"[!] Wystapil blad podczas wysylania na Discord: {e}")


def should_notify_login(ip):
    now = datetime.now()
    entry = login_attempts.get(ip)

    if entry is None or (now - entry["window_start"]).total_seconds() >= RATE_LIMIT_WINDOW_SECONDS:
        login_attempts[ip] = {"window_start": now, "count": 1}
        return True, 1

    entry["count"] += 1

    if entry["count"] <= RATE_LIMIT_MAX_ATTEMPTS:
        return True, entry["count"]

    return False, entry["count"]


def parse_credentials(request_text):
    parts = request_text.split("\r\n\r\n", 1)
    if len(parts) < 2:
        return "", ""

    body = parts[1]
    params = parse_qs(body, keep_blank_values=True)
    username = params.get("username", [""])[0]
    password = params.get("password", [""])[0]
    return username, password


def get_request_line(request_text):
    if not request_text:
        return "", "", ""

    first_line = request_text.split("\r\n", 1)[0]
    pieces = first_line.split(" ")
    if len(pieces) < 3:
        return "", "", ""

    return pieces[0], pieces[1], pieces[2]


def build_http_response(html):
    body = html.encode("utf-8")
    headers = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    return headers.encode("utf-8") + body


def start_honeypot():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
    except PermissionError:
        print(f"[!] Brak uprawnien do portu {PORT}. Uruchom jako administrator/root.")
        return
    except OSError:
        print(f"[!] Port {PORT} jest juz zajety przez inny program.")
        return

    server_socket.listen(5)

    print(f"[*] Honeypot HTTP uruchomiony na http://{HOST}:{PORT}")
    print("[*] Aby zatrzymac, wcisnij CTRL+C")

    while True:
        try:
            client_socket, client_address = server_socket.accept()
            client_socket.settimeout(3)

            try:
                raw = client_socket.recv(8192)
            except socket.timeout:
                client_socket.close()
                continue

            request_text = raw.decode("utf-8", errors="replace")

            intruder_ip = client_address[0]
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            method, path, _ = get_request_line(request_text)

            if path == "/favicon.ico":
                client_socket.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                client_socket.close()
                continue

            if method == "POST":
                username, password = parse_credentials(request_text)

                allowed, attempt_no = should_notify_login(intruder_ip)

                if allowed:
                    message = (
                        f"@everyone\n"
                        f"**ALERT HONEYPOT — PROBA LOGOWANIA!**\n"
                        f"**IP intruza:** `{intruder_ip}`\n"
                        f"**Data i godzina:** `{current_time}`\n"
                        f"**Atakowany port:** `{PORT}` (HTTP)\n"
                        f"**Login:** `{username}`\n"
                        f"**Haslo:** `{password}`\n"
                        f"**Proba w oknie 5 min:** `{attempt_no}/{RATE_LIMIT_MAX_ATTEMPTS}`"
                    )

                    print(f"[!!!] LOGOWANIE ({attempt_no}/{RATE_LIMIT_MAX_ATTEMPTS}) z {intruder_ip} -> login: '{username}' | haslo: '{password}'")
                    send_to_discord(message)
                else:
                    print(f"[~] Pominieto powiadomienie dla {intruder_ip} (proba #{attempt_no}, limit {RATE_LIMIT_MAX_ATTEMPTS}/{RATE_LIMIT_WINDOW_SECONDS // 60}min) | login: '{username}' | haslo: '{password}'")

                error_html = '<div class="err">Nieprawidlowy login lub haslo. Sprobuj ponownie.</div>'
                response_html = LOGIN_PAGE.replace("{ERROR}", error_html)

            else:
                message = (
                    f"**Honeypot — wykryto odwiedziny**\n"
                    f"**IP:** `{intruder_ip}`\n"
                    f"**Data i godzina:** `{current_time}`\n"
                    f"**Atakowany port:** `{PORT}` (HTTP)\n"
                    f"**Metoda:** `{method or '?'}`"
                )

                print(f"[!] {method} {path} z {intruder_ip} o {current_time}")
                send_to_discord(message)

                response_html = LOGIN_PAGE.replace("{ERROR}", "")

            client_socket.sendall(build_http_response(response_html))
            client_socket.close()

        except KeyboardInterrupt:
            print("\n[*] Zatrzymywanie honeypota...")
            break

        except Exception as e:
            print(f"[!] Blad podczas obslugi polaczenia: {e}")

    server_socket.close()
    print("[*] Honeypot zatrzymany.")


if __name__ == "__main__":
    start_honeypot()
