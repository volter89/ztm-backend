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

MAX_WAIT = 20

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

@app.post("/plan")
def plan(data: RequestData):
    try:
        start_ids = []
        for name, ids in stop_name_to_ids.items():
            if normalize(data.start) in normalize(name):
                start_ids.extend(ids)

        if not start_ids:
            return {"route": ["❌ Nie znaleziono przystanku"], "total_time": data.total_time}

        current_time = data.start_time
        current_stops = start_ids
        route = []
        first = True

        while True:
            best = None

            for trip_id, rows in stop_times_full.items():
                for i, row in enumerate(rows):

                    if row["stop_id"] not in current_stops:
                        continue

                    dep = tmin(row["departure_time"])

                    if dep < current_time:
                        continue

                    wait = dep - current_time

                    if wait < data.transfer_time or wait > MAX_WAIT:
                        continue

                    for j in range(i+1, min(i+6, len(rows))):
                        arr = tmin(rows[j]["arrival_time"])
                        seg = arr - dep
                        if seg <= 1:
                            continue

                        # 🔥 KLUCZ: pierwszy przejazd ignoruje ride_time
                        if not first and seg < data.ride_time:
                            continue

                        if not best or seg > best["seg"]:
                            best = {
                                "trip_id": trip_id,
                                "i": i,
                                "j": j,
                                "dep": dep,
                                "arr": arr,
                                "wait": wait,
                                "seg": seg
                            }

            if not best:
                break

            dep = best["dep"]
            arr = best["arr"]

            if arr - data.start_time > data.total_time:
                break

            trip_id = best["trip_id"]
            i = best["i"]
            j = best["j"]

            from_stop = stop_id_to_name[stop_times_full[trip_id][i]["stop_id"]]
            to_stop = stop_id_to_name[stop_times_full[trip_id][j]["stop_id"]]
            line = route_to_name.get(trip_to_route.get(trip_id), "?")

            route.append(
                f"🚍 Linia {line}\n🕒 {dep//60:02d}:{dep%60:02d} → {arr//60:02d}:{arr%60:02d}\n{from_stop} → {to_stop}"
            )

            current_time = arr
            current_stops = [stop_times_full[trip_id][j]["stop_id"]]
            first = False

        used = current_time - data.start_time

        route.append(f"🏁 Powrót (orientacyjnie) do: {data.start}")
        route.append(f"⏱ Wykorzystano ~{used} min")

        return {"route": route, "total_time": data.total_time}

    except Exception as e:
        return {"route": [str(e)], "total_time": 0}

@app.get("/stops")
def get_stops():
    return list(stop_name_to_ids.keys())
