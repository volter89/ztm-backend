from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import csv
import unicodedata
import re
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "ZTM backend działa 🚍"}

class RequestData(BaseModel):
    start: str
    end: str
    ride_time: int
    transfer_time: int
    total_time: int

def normalize(text):
    text = text.lower().strip()
    text = text.replace('"', '').replace("'", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\b\d+\b", "", text)
    return text.strip()

def time_to_minutes(t):
    h, m, s = map(int, t.split(":"))
    return h * 60 + m

def current_minutes():
    now = datetime.now()
    return now.hour * 60 + now.minute

# 🔥 GLOBAL
stop_name_to_ids = {}
stop_id_to_name = {}
stop_times = {}
stop_times_full = {}
trip_to_route = {}
route_to_name = {}

# LOAD
with open("stops.txt", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        stop_id = row["stop_id"]
        stop_name = row["stop_name"]
        stop_id_to_name[stop_id] = stop_name
        stop_name_to_ids.setdefault(stop_name, []).append(stop_id)

with open("stop_times.txt", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        trip_id = row["trip_id"]
        stop_times.setdefault(trip_id, []).append(row["stop_id"])
        stop_times_full.setdefault(trip_id, []).append(row)

with open("trips.txt", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        trip_to_route[row["trip_id"]] = row["route_id"]

with open("routes.txt", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        route_to_name[row["route_id"]] = row["route_short_name"]

@app.post("/plan")
def plan(data: RequestData):
    try:
        now = current_minutes()

        start_norm = normalize(data.start)
        end_norm = normalize(data.end)

        start_ids = []
        end_ids = []

        for name, ids in stop_name_to_ids.items():
            n = normalize(name)
            if start_norm in n or n in start_norm:
                start_ids.extend(ids)
            if end_norm in n or n in end_norm:
                end_ids.extend(ids)

        if not start_ids or not end_ids:
            return {"route": ["❌ Nie znaleziono przystanku"], "total_time": data.total_time}

        best_option = None
        best_wait = 9999

        # 🔁 SZUKAJ WSZYSTKICH PRZESIADEK
        for trip1_id, stops1 in stop_times.items():
            full1 = stop_times_full[trip1_id]

            for s in start_ids:
                if s in stops1:
                    i_start = stops1.index(s)
                    dep1 = time_to_minutes(full1[i_start]["departure_time"])

                    if dep1 < now:
                        continue

                    for transfer in stops1[i_start:]:
                        i_transfer = stops1.index(transfer)
                        arr1 = time_to_minutes(full1[i_transfer]["arrival_time"])

                        for trip2_id, stops2 in stop_times.items():
                            if transfer in stops2:
                                full2 = stop_times_full[trip2_id]
                                i_transfer2 = stops2.index(transfer)

                                dep2 = time_to_minutes(full2[i_transfer2]["departure_time"])

                                if dep2 < arr1 + data.transfer_time:
                                    continue

                                wait = dep2 - arr1

                                if wait < best_wait:

                                    for e in end_ids:
                                        if e in stops2:
                                            i_end = stops2.index(e)

                                            if i_transfer2 < i_end:
                                                best_wait = wait

                                                best_option = {
                                                    "line1": route_to_name.get(trip_to_route.get(trip1_id), "?"),
                                                    "line2": route_to_name.get(trip_to_route.get(trip2_id), "?"),
                                                    "dep1": full1[i_start]["departure_time"],
                                                    "arr1": full1[i_transfer]["arrival_time"],
                                                    "dep2": full2[i_transfer2]["departure_time"],
                                                    "arr2": full2[i_end]["arrival_time"],
                                                    "transfer": stop_id_to_name.get(transfer, "?")
                                                }

        if best_option:
            return {
                "route": [
                    f"🚍 Linia {best_option['line1']}",
                    f"🕒 {best_option['dep1']} → {best_option['arr1']}",
                    f"{data.start} → {best_option['transfer']}",
                    "🔁 Przesiadka",
                    f"🚍 Linia {best_option['line2']}",
                    f"🕒 {best_option['dep2']} → {best_option['arr2']}",
                    f"{best_option['transfer']} → {data.end}"
                ],
                "total_time": data.total_time
            }

        return {"route": ["❌ Nie znaleziono połączenia"], "total_time": data.total_time}

    except Exception as e:
        return {"route": [f"❌ Błąd: {str(e)}"], "total_time": 0}

@app.get("/stops")
def get_stops():
    return list(stop_name_to_ids.keys())
