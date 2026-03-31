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

# 🔥 GLOBALNE DANE
stop_name_to_ids = {}
stop_id_to_name = {}
stop_times = {}
stop_times_full = {}
trip_to_route = {}
route_to_name = {}

print("🚀 Ładowanie danych...")

with open("stops.txt", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        stop_id = row["stop_id"]
        stop_name = row["stop_name"]

        stop_id_to_name[stop_id] = stop_name

        if stop_name not in stop_name_to_ids:
            stop_name_to_ids[stop_name] = []

        stop_name_to_ids[stop_name].append(stop_id)

with open("stop_times.txt", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        trip_id = row["trip_id"]

        if trip_id not in stop_times:
            stop_times[trip_id] = []
            stop_times_full[trip_id] = []

        stop_times[trip_id].append(row["stop_id"])
        stop_times_full[trip_id].append(row)

with open("trips.txt", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        trip_to_route[row["trip_id"]] = row["route_id"]

with open("routes.txt", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        route_to_name[row["route_id"]] = row["route_short_name"]

print("✅ Dane załadowane!")

@app.post("/plan")
def plan(data: RequestData):
    try:
        now = current_minutes()

        start_norm = normalize(data.start)
        end_norm = normalize(data.end)

        start_ids = []
        end_ids = []

        for name, ids in stop_name_to_ids.items():
            name_norm = normalize(name)

            if start_norm in name_norm or name_norm in start_norm:
                start_ids.extend(ids)

            if end_norm in name_norm or name_norm in end_norm:
                end_ids.extend(ids)

        if not start_ids or not end_ids:
            return {"route": ["❌ Nie znaleziono przystanku"], "total_time": data.total_time}

        # 🚍 BEZPOŚREDNIE (tylko przyszłe kursy)
        for trip_id, stops in stop_times.items():
            full = stop_times_full[trip_id]

            for s in start_ids:
                for e in end_ids:
                    if s in stops and e in stops:
                        i1 = stops.index(s)
                        i2 = stops.index(e)

                        if i1 < i2:
                            dep_time = full[i1]["departure_time"]
                            arr_time = full[i2]["arrival_time"]

                            if time_to_minutes(dep_time) < now:
                                continue

                            line = route_to_name.get(trip_to_route.get(trip_id), "?")

                            return {
                                "route": [
                                    f"🚍 Linia {line}",
                                    f"🕒 {dep_time} → {arr_time}",
                                    f"{data.start} → {data.end}"
                                ],
                                "total_time": data.total_time
                            }

        # 🔁 PRZESIADKA (realna!)
        for trip1_id, stops1 in stop_times.items():
            full1 = stop_times_full[trip1_id]

            for s in start_ids:
                if s in stops1:
                    i_start = stops1.index(s)

                    dep1 = full1[i_start]["departure_time"]
                    if time_to_minutes(dep1) < now:
                        continue

                    for transfer in stops1[i_start:]:
                        i_transfer = stops1.index(transfer)
                        arr1 = full1[i_transfer]["arrival_time"]

                        for trip2_id, stops2 in stop_times.items():
                            if transfer in stops2:
                                full2 = stop_times_full[trip2_id]
                                i_transfer2 = stops2.index(transfer)

                                dep2 = full2[i_transfer2]["departure_time"]

                                # 🔥 KLUCZOWY WARUNEK
                                if time_to_minutes(dep2) < time_to_minutes(arr1) + data.transfer_time:
                                    continue

                                for e in end_ids:
                                    if e in stops2:
                                        i_end = stops2.index(e)

                                        if i_transfer2 < i_end:
                                            arr2 = full2[i_end]["arrival_time"]

                                            line1 = route_to_name.get(trip_to_route.get(trip1_id), "?")
                                            line2 = route_to_name.get(trip_to_route.get(trip2_id), "?")

                                            transfer_name = stop_id_to_name.get(transfer, "?")

                                            return {
                                                "route": [
                                                    f"🚍 Linia {line1}",
                                                    f"🕒 {dep1} → {arr1}",
                                                    f"{data.start} → {transfer_name}",
                                                    "🔁 Przesiadka",
                                                    f"🚍 Linia {line2}",
                                                    f"🕒 {dep2} → {arr2}",
                                                    f"{transfer_name} → {data.end}"
                                                ],
                                                "total_time": data.total_time
                                            }

        return {"route": ["❌ Nie znaleziono połączenia"], "total_time": data.total_time}

    except Exception as e:
        return {"route": [f"❌ Błąd: {str(e)}"], "total_time": 0}

@app.get("/stops")
def get_stops():
    return list(stop_name_to_ids.keys())
