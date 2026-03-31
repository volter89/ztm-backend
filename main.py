from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import csv
import unicodedata
import re

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

MAX_WAIT = 15
FALLBACK_WAIT = 40

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

# 🔥 sprawdza czy można kontynuować
def has_next(stop_id, current_time):
    for trip_id, stops in stop_times.items():
        full = stop_times_full[trip_id]
        if stop_id in stops:
            i = stops.index(stop_id)
            dep = tmin(full[i]["departure_time"])
            if dep >= current_time:
                return True
    return False

@app.post("/plan")
def plan(data: RequestData):
    try:
        current_time = data.start_time

        start_ids = []
        for name, ids in stop_name_to_ids.items():
            if normalize(data.start) in normalize(name):
                start_ids.extend(ids)

        current_ids = start_ids
        total_used = 0
        route = []

        while total_used < data.total_time:

            best = None
            best_score = -1

            for MAX in [MAX_WAIT, FALLBACK_WAIT]:

                for trip_id, stops in stop_times.items():
                    full = stop_times_full[trip_id]

                    for s in current_ids:
                        if s in stops:
                            i = stops.index(s)
                            dep = tmin(full[i]["departure_time"])

                            if dep < current_time:
                                continue

                            wait = dep - current_time

                            if wait < data.transfer_time:
                                continue

                            if wait > MAX:
                                continue

                            for j in range(i+2, min(i+10, len(stops))):
                                arr = tmin(full[j]["arrival_time"])
                                seg = arr - dep

                                if seg < data.ride_time:
                                    continue

                                if total_used + seg > data.total_time:
                                    continue

                                next_stop = stops[j]

                                # 🔥 NOWY SYSTEM OCENY
                                score = seg

                                if has_next(next_stop, arr):
                                    score += 20  # bonus za kontynuację

                                if score > best_score:
                                    best_score = score
                                    best = (trip_id, i, j, dep, arr)

                if best:
                    break

            if not best:
                route.append("🚶 Brak dalszego połączenia")
                break

            trip_id, i, j, dep, arr = best

            line = route_to_name.get(trip_to_route.get(trip_id), "?")
            from_stop = stop_id_to_name.get(stop_times[trip_id][i], "?")
            to_stop = stop_id_to_name.get(stop_times[trip_id][j], "?")

            route.append(
                f"🚍 Linia {line}\n🕒 {dep//60:02d}:{dep%60:02d} → {arr//60:02d}:{arr%60:02d}\n{from_stop} → {to_stop}"
            )

            current_ids = [stop_times[trip_id][j]]
            current_time = arr
            total_used += (arr - dep)

        route.append(f"🏁 Powrót (orientacyjnie) do: {data.start}")
        route.append(f"⏱ Wykorzystano ~{total_used} min")

        return {"route": route, "total_time": data.total_time}

    except Exception as e:
        return {"route": [str(e)], "total_time": 0}

@app.get("/stops")
def get_stops():
    return list(stop_name_to_ids.keys())
