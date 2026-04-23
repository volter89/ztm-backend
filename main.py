from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import csv
import unicodedata
import re
import heapq

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

MAX_WAIT = 30

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
stop_times_full = {}
trip_to_route = {}
route_to_name = {}

with open("stops.txt", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        stop_name_to_ids.setdefault(r["stop_name"], []).append(r["stop_id"])
        stop_id_to_name[r["stop_id"]] = r["stop_name"]

with open("stop_times.txt", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        stop_times_full.setdefault(r["trip_id"], []).append(r)

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

        pq = []
        for sid in start_ids:
            heapq.heappush(pq, (0, sid, data.start_time, []))

        best_route = []
        best_time = 0
        visited = {}

        while pq:
            neg_score, stop_id, current_time, path = heapq.heappop(pq)
            real_time = current_time - data.start_time

            key = (stop_id, current_time)
            if key in visited and visited[key] >= real_time:
                continue
            visited[key] = real_time

            if real_time > best_time:
                best_time = real_time
                best_route = path

            if real_time >= data.total_time:
                continue

            for trip_id, rows in stop_times_full.items():

                for i, row in enumerate(rows):

                    if row["stop_id"] != stop_id:
                        continue

                    dep = tmin(row["departure_time"])

                    if dep < current_time:
                        continue

                    wait = dep - current_time

                    if wait < data.transfer_time or wait > MAX_WAIT:
                        continue

                    for j in range(i+1, min(i+10, len(rows))):
                        arr = tmin(rows[j]["arrival_time"])

                        if arr <= dep:
                            continue

                        seg = arr - dep

                        if seg <= 1:
                            continue

                        if path and seg < data.ride_time:
                            continue

                        new_time = arr - data.start_time

                        if new_time > data.total_time:
                            continue

                        to_stop = stop_id_to_name[rows[j]["stop_id"]]
                        from_stop = stop_id_to_name[stop_id]
                        line = route_to_name.get(trip_to_route.get(trip_id), "?")

                        # 🔥 HEURYSTYKA (klucz!)
                        bonus = 0
                        name = to_stop.lower()

                        if "katowice" in name:
                            bonus += 40
                        elif "centrum" in name or "dworzec" in name:
                            bonus += 30
                        elif "sosnowiec" in name:
                            bonus += 20

                        score = new_time + bonus

                        new_path = path + [(
                            line, dep, arr, from_stop, to_stop
                        )]

                        heapq.heappush(
                            pq,
                            (-score, rows[j]["stop_id"], arr, new_path)
                        )

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
