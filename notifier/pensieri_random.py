import os
import json
import hashlib
import random
import requests
from datetime import datetime, date

# --- Parametri configurabili ---
WINDOW_START = "08:00"
WINDOW_END = "22:30"
MIN_PER_DAY = 2
MAX_PER_DAY = 4
MIN_GAP_MINUTES = 90
NO_REPEAT_DAYS = 7
PAUSED = False

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")


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


def generate_slots():
    start = time_to_minutes(WINDOW_START)
    end = time_to_minutes(WINDOW_END)
    n = random.randint(MIN_PER_DAY, MAX_PER_DAY)
    slots = []
    attempts = 0
    while len(slots) < n and attempts < 1000:
        t = random.randint(start, end)
        if all(abs(t - s) >= MIN_GAP_MINUTES for s in slots):
            slots.append(t)
        attempts += 1
    slots.sort()
    return [{"time": minutes_to_time(s), "sent": False} for s in slots]


def hash_text(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def fetch_pensieri(state):
    read_url = os.environ.get("PENSIERI_READ_URL", "")
    read_key = os.environ.get("READ_KEY", "")

    # Google Apps Script fa un redirect durante il quale i parametri GET vengono
    # persi. Seguiamo il redirect manualmente e riaggiungiamo la chiave.
    try:
        session = requests.Session()
        url = f"{read_url}?key={read_key}"
        resp = session.get(url, timeout=15, allow_redirects=False)

        # Segui i redirect mantenendo il parametro key
        for _ in range(5):
            if resp.status_code not in (301, 302, 303, 307, 308):
                break
            location = resp.headers.get("Location", "")
            if "?" not in location:
                location = f"{location}?key={read_key}"
            resp = session.get(location, timeout=15, allow_redirects=False)

        print(f"HTTP {resp.status_code}, body: {resp.text[:120]!r}")
        resp.raise_for_status()
        pensieri = resp.json()
        if isinstance(pensieri, list) and len(pensieri) > 0:
            state["last_list_cache"] = pensieri
            print(f"Lista aggiornata: {len(pensieri)} pensieri.")
            return pensieri
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
    if PAUSED:
        print("Sistema in pausa. Nessuna notifica inviata.")
        return

    state = load_state()
    today = date.today().isoformat()
    now_minutes = datetime.now().hour * 60 + datetime.now().minute

    # Nuovo giorno: genera slot casuali
    if state.get("date") != today:
        print(f"Nuovo giorno: {today}. Genero slot.")
        state["date"] = today
        state["slots"] = generate_slots()
        print(f"Slot: {[s['time'] for s in state['slots']]}")

    pensieri = fetch_pensieri(state)
    if not pensieri:
        save_state(state)
        return

    recent_hashes = state.get("recent_hashes", [])
    end_minutes = time_to_minutes(WINDOW_END)
    state_changed = False

    for slot in state["slots"]:
        if slot["sent"]:
            continue

        slot_minutes = time_to_minutes(slot["time"])

        # Slot nel futuro: skip
        if slot_minutes > now_minutes:
            continue

        # Fuori dalla finestra giornaliera: salta senza recuperare
        if now_minutes > end_minutes:
            print(f"Slot {slot['time']} fuori finestra. Salto.")
            slot["sent"] = True
            state_changed = True
            continue

        # Verifica distanza minima dall'ultimo invio
        last_sent = state.get("last_sent_time")
        if last_sent:
            gap = now_minutes - time_to_minutes(last_sent)
            if gap < MIN_GAP_MINUTES:
                print(f"Gap insufficiente ({gap} min < {MIN_GAP_MINUTES}). Aspetto.")
                continue

        # Scegli e invia
        pensiero = choose_pensiero(pensieri, recent_hashes)
        if pensiero and send_notification(pensiero):
            slot["sent"] = True
            state["last_sent_time"] = slot["time"]
            recent_hashes.append(hash_text(pensiero))
            # Conserva solo gli hash degli ultimi NO_REPEAT_DAYS * MAX_PER_DAY invii
            state["recent_hashes"] = recent_hashes[-(NO_REPEAT_DAYS * MAX_PER_DAY):]
            state_changed = True

    if state_changed or "last_list_cache" in state:
        save_state(state)

    print("Esecuzione completata.")


if __name__ == "__main__":
    main()
