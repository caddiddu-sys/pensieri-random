import os
import json
import hashlib
import random
import requests
from datetime import datetime, date

NO_REPEAT_DAYS = 7
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

CONFIG_DEFAULTS = {
    "paused": False,
    "window_start": "08:00",
    "window_end": "22:30",
    "min_per_day": 2,
    "max_per_day": 4,
    "min_gap_minutes": 90,
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def time_to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def minutes_to_time(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def generate_slots(window_start, window_end, min_per_day, max_per_day, min_gap_minutes):
    start = time_to_minutes(window_start)
    end   = time_to_minutes(window_end)
    n     = random.randint(min_per_day, max_per_day)
    slots = []
    attempts = 0
    while len(slots) < n and attempts < 1000:
        t = random.randint(start, end)
        if all(abs(t - s) >= min_gap_minutes for s in slots):
            slots.append(t)
        attempts += 1
    slots.sort()
    return [{"time": minutes_to_time(s), "sent": False} for s in slots]


def hash_text(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def fetch_config():
    """Legge la config da Apps Script. Falls back ai valori di default."""
    read_url = os.environ.get("PENSIERI_READ_URL", "")
    read_key = os.environ.get("READ_KEY", "")
    if not read_url or not read_key:
        return CONFIG_DEFAULTS.copy()
    try:
        url  = f"{read_url}?key={read_key}&action=getConfig"
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=15,
            allow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "window_start" in data:
            print(f"Config caricata: {data}")
            # Merge con defaults per eventuali chiavi mancanti
            merged = CONFIG_DEFAULTS.copy()
            merged.update(data)
            return merged
        print(f"Config non valida: {data!r}")
    except Exception as ex:
        print(f"Fetch config fallito: {ex}")
    print("Uso config di default.")
    return CONFIG_DEFAULTS.copy()


def fetch_pensieri(state):
    read_url = os.environ.get("PENSIERI_READ_URL", "")
    read_key = os.environ.get("READ_KEY", "")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    try:
        url  = f"{read_url}?key={read_key}"
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        print(f"HTTP {resp.status_code}, url finale: {resp.url[:80]!r}")
        print(f"Body preview: {resp.text[:100]!r}")
        resp.raise_for_status()
        pensieri = resp.json()
        if isinstance(pensieri, list) and len(pensieri) > 0:
            state["last_list_cache"] = pensieri
            print(f"Lista aggiornata: {len(pensieri)} pensieri.")
            return pensieri
        print(f"Risposta non valida: {pensieri!r}")
    except Exception as e:
        print(f"Fetch lista fallito: {e}")

    cache = state.get("last_list_cache", [])
    if cache:
        print(f"Uso cache: {len(cache)} pensieri.")
    else:
        print("Nessuna lista disponibile.")
    return cache


def send_notification(text):
    topic = os.environ.get("NTFY_TOPIC", "")
    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=text.encode("utf-8"),
            headers={"Title": "il Tarlo", "Priority": "default"},
            timeout=15,
        )
        resp.raise_for_status()
        print(f"Notifica inviata: {text[:60]}")
        return True
    except Exception as e:
        print(f"Invio notifica fallito: {e}")
        return False


def choose_pensiero(pensieri, recent_hashes):
    available = [p for p in pensieri if hash_text(p) not in recent_hashes]
    if not available:
        print("Tutti i pensieri recenti esauriti. Uso la lista completa.")
        available = pensieri
    return random.choice(available) if available else None


def main():
    config = fetch_config()

    if config.get("paused", False):
        print("Sistema in pausa. Nessuna notifica inviata.")
        return

    window_start    = config.get("window_start",    CONFIG_DEFAULTS["window_start"])
    window_end      = config.get("window_end",      CONFIG_DEFAULTS["window_end"])
    min_per_day     = int(config.get("min_per_day",    CONFIG_DEFAULTS["min_per_day"]))
    max_per_day     = int(config.get("max_per_day",    CONFIG_DEFAULTS["max_per_day"]))
    min_gap_minutes = int(config.get("min_gap_minutes", CONFIG_DEFAULTS["min_gap_minutes"]))

    state = load_state()
    today = date.today().isoformat()
    now_minutes = datetime.now().hour * 60 + datetime.now().minute

    if state.get("date") != today:
        print(f"Nuovo giorno: {today}. Genero slot.")
        state["date"]  = today
        state["slots"] = generate_slots(window_start, window_end, min_per_day, max_per_day, min_gap_minutes)
        print(f"Slot: {[s['time'] for s in state['slots']]}")

    pensieri = fetch_pensieri(state)
    if not pensieri:
        save_state(state)
        return

    recent_hashes = state.get("recent_hashes", [])
    end_minutes   = time_to_minutes(window_end)
    state_changed = False

    for slot in state["slots"]:
        if slot["sent"]:
            continue

        slot_minutes = time_to_minutes(slot["time"])

        if slot_minutes > now_minutes:
            continue

        if now_minutes > end_minutes:
            print(f"Slot {slot['time']} fuori finestra. Salto.")
            slot["sent"] = True
            state_changed = True
            continue

        last_sent = state.get("last_sent_time")
        if last_sent:
            gap = now_minutes - time_to_minutes(last_sent)
            if gap < min_gap_minutes:
                print(f"Gap insufficiente ({gap} min < {min_gap_minutes}). Aspetto.")
                continue

        pensiero = choose_pensiero(pensieri, recent_hashes)
        if pensiero and send_notification(pensiero):
            slot["sent"] = True
            state["last_sent_time"] = slot["time"]
            recent_hashes.append(hash_text(pensiero))
            state["recent_hashes"] = recent_hashes[-(NO_REPEAT_DAYS * max_per_day):]
            state_changed = True

    if state_changed or "last_list_cache" in state:
        save_state(state)

    print("Esecuzione completata.")


if __name__ == "__main__":
    main()
