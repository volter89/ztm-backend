from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import csv
import unicodedata
import re
from collections import deque

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestData(BaseModel):
    start: str
    end: str
    ride_time: int
    transfer_time: int
    total_time: int
    start_time: int

MAX_STEPS = 2000  # zabezpieczenie przed zawieszeniem

def normalize(text):
    text = text.lower().strip()
    text = text.replace('"', '').replace("'", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\b\d+\b", "", text)
    return text.strip()

def tmin(t):
    h, m, s = map(int, t.split(":"))
    return h * 60 + m

# LOAD
stop_name_to_ids = {}
stop_id_to_name = {}
stop_times = {}
stop_times_full = {}
trip_to_route = {}
route_to_name = {}

with open("stops.txt", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        stop_id_to_name[r["stop_id"]] = r["stop_name"]
        stop_name_to_ids.setdefault(r["stop_name"], []).append(r["stop_id"])

with open("stop_times.txt", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        tid = r["trip_id"]
        stop_times.setdefault(tid, []).append(r["stop_id"])
        stop_times_full.setdefault(tid, []).append(r)

with open("trips.txt", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        trip_to_route[r["trip_id"]] = r["route_id"]

with open("routes.txt", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        route_to_name[r["route_id"]] = r["route_short_name"]

@app.post("/plan")
def plan(data: RequestData):
    try:
        # 🔍 znajdź startowe przystanki
        start_ids = []
        for name, ids in stop_name_to_ids.items():
            if normalize(data.start) in normalize(name):
                start_ids.extend(ids)

        if not start_ids:
            return {"route": ["❌ Nie znaleziono przystanku"], "total_time": data.total_time}

        queue = deque()

        for sid in start_ids:
            queue.append((sid, data.start_time, 0, []))

        best_route = []
        best_time = 0
        steps = 0

        while queue:
            steps += 1
            if steps > MAX_STEPS:
                break

            stop_id, current_time, used_time, path = queue.popleft()

            # 🔥 zapisujemy najlepszy wynik
            if used_time > best_time:
                best_time = used_time
                best_route = path

            if used_time >= data.total_time:
                continue

            for trip_id, stops in stop_times.items():

                if stop_id not in stops:
                    continue

                full = stop_times_full[trip_id]
                i = stops.index(stop_id)

                dep = tmin(full[i]["departure_time"])

                if dep < current_time:
                    continue

                wait = dep - current_time

                if wait < 2:
                    continue

                for j in range(i+2, min(i+8, len(stops))):
                    arr = tmin(full[j]["arrival_time"])
                    seg = arr - dep

                    # 🔥 KLUCZOWA ZMIANA — kara zamiast blokady
                    penalty = 0
                    if seg < data.ride_time:
                        penalty = 5

                    new_time = arr - data.start_time

                    if new_time > data.total_time:
                        continue

                    line = route_to_name.get(trip_to_route.get(trip_id), "?")
                    from_stop = stop_id_to_name[stop_id]
                    to_stop = stop_id_to_name[stops[j]]

                    new_path = path + [(
                        line, dep, arr, from_stop, to_stop
                    )]

                    queue.append((stops[j], arr, new_time, new_path))

        result = []

        for line, dep, arr, fr, to in best_route:
            result.append(
                f"🚍 Linia {line}\n🕒 {dep//60:02d}:{dep%60:02d} → {arr//60:02d}:{arr%60:02d}\n{fr} → {to}"
            )

        result.append(f"🏁 Powrót (orientacyjnie) do: {data.start}")
        result.append(f"⏱ Wykorzystano ~{int(best_time)} min")

        return {"route": result, "total_time": data.total_time}

    except Exception as e:
        return {"route": [str(e)], "total_time": 0}

@app.get("/stops")
def get_stops():
    return list(stop_name_to_ids.keys())
