# PyHoneypot

Prosty honeypot HTTP w Pythonie z fałszywą stroną logowania. Przechwytuje credentiale prób logowania i wysyła alerty na kanał Discord przez webhooka.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

## Funkcje

- Fałszywa strona logowania serwowana na porcie 80 (HTTP).
- Przechwytywanie loginu i hasła wpisanego przez intruza.
- Powiadomienia w czasie rzeczywistym przez Discord Webhook.
- Rate limiter per IP — max 3 powiadomienia / 5 min, żeby nie zaspamować Discorda przy brute-force.
- Pełne logi w konsoli (również dla prób stłumionych przez rate limiter).
- Bez zewnętrznych frameworków — czysty `socket` + `requests`.

## Jak to działa

```
[Intruz / bot]  --HTTP-->  [PyHoneypot :80]  --webhook-->  [Discord]
```

1. **Nasłuch.** `socket` TCP bindowany na `0.0.0.0:80` i czekający na połączenia w pętli.
2. **GET /** → serwowana jest fałszywa strona logowania (HTML zaszyty w stałej `LOGIN_PAGE`). Na Discorda leci alert "wykryto odwiedziny".
3. **POST /** → z body wyciągane są pola `username` i `password` (przez `urllib.parse.parse_qs`). Po sprawdzeniu rate limitera, na Discorda leci alert z credentialami. Intruzowi pokazuje się komunikat "Nieprawidlowy login lub haslo", więc próbuje dalej.
4. **Webhook.** `requests.post()` na `WEBHOOK_URL` z payloadem `{"content": "..."}`. Błędy sieciowe są łapane, żeby honeypot się nie wywalił.
5. **`/favicon.ico`** jest cicho odrzucane (404), żeby przeglądarki nie spamowały logów.

### Rate limiter

Każdy IP ma własne 5-minutowe okno. W oknie dozwolone są **3 powiadomienia** na Discorda. Czwarta i kolejne próby (w tym samym oknie) są tylko logowane do konsoli. Po 5 minutach od pierwszej próby okno resetuje się.

| Czas       | Próba | Co się dzieje                                |
|------------|-------|----------------------------------------------|
| 19:00:00   | 1     | Discord: alert (1/3) — start nowego okna     |
| 19:00:30   | 2     | Discord: alert (2/3)                         |
| 19:01:10   | 3     | Discord: alert (3/3)                         |
| 19:02:00   | 4     | Pominięte (tylko log w konsoli)              |
| 19:04:50   | N     | Pominięte (tylko log w konsoli)              |
| 19:05:01   | N+1   | Reset okna → Discord: alert (1/3)            |

## Wymagania

- Python 3.8+
- Biblioteka `requests`
- Uprawnienia administratora/roota (port 80 jest portem uprzywilejowanym)
- Webhook Discord

## Instalacja

```bash
git clone <url-repo>
cd PyHoneypot
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
pip install -r requirements.txt
```

## Konfiguracja

1. Discord → Ustawienia kanału → Integracje → Webhooks → Nowy webhook → kopiuj URL.
2. W `honeypot.py` wklej URL do zmiennej `WEBHOOK_URL`:

```python
WEBHOOK_URL = "https://discord.com/api/webhooks/XXXXXXXX/XXXXXXXX"
```

## Uruchomienie

**Windows (PowerShell jako Administrator):**

```powershell
python honeypot.py
```

**Linux / macOS:**

```bash
sudo python3 honeypot.py
```

Zatrzymanie: `CTRL+C`.

## Testowanie

W przeglądarce: `http://<IP>/` → wpisać dowolny login/hasło → kliknąć "Zaloguj się".

Symulacja bota z terminala:

```bash
curl -X POST http://localhost/ -d "username=admin&password=admin123"
```

## Przykładowe powiadomienie Discord

```
@everyone
ALERT HONEYPOT — PROBA LOGOWANIA!
IP intruza: 192.168.1.42
Data i godzina: 2026-04-29 19:08:31
Atakowany port: 80 (HTTP)
Login: admin
Haslo: admin
Proba w oknie 5 min: 1/3
```

## Konfigurowalne parametry

Wszystkie ustawienia są na górze pliku `honeypot.py`:

| Zmienna                     | Domyślna wartość | Opis                                                         |
|-----------------------------|------------------|--------------------------------------------------------------|
| `WEBHOOK_URL`               | `""`             | URL webhooka Discord.                                        |
| `PORT`                      | `80`             | Port nasłuchu. `8080` nie wymaga uprawnień admina.           |
| `HOST`                      | `0.0.0.0`        | `0.0.0.0` = wszystkie interfejsy, `127.0.0.1` = tylko local. |
| `RATE_LIMIT_WINDOW_SECONDS` | `300`            | Długość okna rate limitera w sekundach.                      |
| `RATE_LIMIT_MAX_ATTEMPTS`   | `3`              | Ile alertów dozwolonych w jednym oknie per IP.               |

## Struktura projektu

```
PyHoneypot/
├── honeypot.py         # Główny skrypt
├── requirements.txt    # Zależności
└── README.md
```

## Ostrzeżenie

Projekt edukacyjny. Uruchamianie wyłącznie na własnych maszynach i w sieciach. Wystawianie honeypota w publicznym internecie wiąże się z odpowiedzialnością prawną i operacyjną. Webhook URL jest sekretem — nie commitować go do publicznych repozytoriów.
