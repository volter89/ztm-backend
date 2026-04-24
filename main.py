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

MAX_STEPS = 5000


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


# ================= LOAD =================

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


# ================= API =================

@app.post("/plan")
def plan(data: RequestData):
    try:
        start_ids = []
        for name, ids in stop_name_to_ids.items():
            if normalize(data.start) in normalize(name):
                start_ids.extend(ids)

        if not start_ids:
            return {"route": ["❌ Nie znaleziono przystanku"], "total_time": data.total_time}

        queue = deque()

        for sid in start_ids:
            queue.append((sid, data.start_time, [], 0))

        best_route = []
        best_score = -1
        best_time = 0

        steps = 0

        while queue:
            steps += 1
            if steps > MAX_STEPS:
                break

            stop_id, current_time, path, total_wait = queue.popleft()

            # czas jazdy
            if path:
                start_trip_time = path[0][1]
                ride_time_total = current_time - start_trip_time
            else:
                ride_time_total = 0

            # ocena powrotu
            if path:
                last_stop = path[-1][4]

                if normalize(data.end) in normalize(last_stop):
                    score = ride_time_total - total_wait

                    if score > best_score:
                        best_score = score
                        best_time = ride_time_total
                        best_route = path

            if ride_time_total >= data.total_time:
                continue

            # 🔥 SZUKAMY NAJBLIŻSZYCH AUTOBUSÓW
            candidates = []

            for trip_id, stops in stop_times.items():
                if stop_id not in stops:
                    continue

                full = stop_times_full[trip_id]
                i = stops.index(stop_id)

                dep = tmin(full[i]["departure_time"])

                if dep < current_time - 1:
                    continue

                wait = dep - current_time
                if wait < 0:
                    wait = 0

                if wait < 2 or wait > 90:
                    continue

                candidates.append((dep, trip_id, i, wait))

            # sortujemy po czasie odjazdu
            candidates.sort(key=lambda x: x[0])

            # bierzemy tylko najbliższe
            candidates = candidates[:5]

            for dep, trip_id, i, wait in candidates:
                full = stop_times_full[trip_id]
                stops = stop_times[trip_id]

                for j in range(i + 1, len(stops)):
                    arr = tmin(full[j]["arrival_time"])

                    if arr <= dep:
                        continue

                    seg = arr - dep

                    if seg <= 1:
                        continue

                    if seg > 20:
                        continue

                    if arr - data.start_time > data.total_time:
                        continue

                    from_stop = stop_id_to_name[stop_id]
                    to_stop = stop_id_to_name[stops[j]]

                    if from_stop == to_stop:
                        continue

                    line = route_to_name.get(trip_to_route.get(trip_id), "?")

                    new_path = path + [(
                        line, dep, arr, from_stop, to_stop
                    )]

                    new_wait = total_wait + wait

                    queue.append((stops[j], arr, new_path, new_wait))

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
