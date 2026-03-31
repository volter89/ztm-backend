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

# 🔥 GLOBALNE DANE
stop_name_to_ids = {}
stop_id_to_name = {}
stop_times = {}
stop_times_full = {}
trip_to_route = {}
route_to_name = {}

print("🚀 Ładowanie danych...")

# stops
with open("stops.txt", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        stop_id = row["stop_id"]
        stop_name = row["stop_name"]

        stop_id_to_name[stop_id] = stop_name

        if stop_name not in stop_name_to_ids:
            stop_name_to_ids[stop_name] = []

        stop_name_to_ids[stop_name].append(stop_id)

# stop_times (pełne dane)
with open("stop_times.txt", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        trip_id = row["trip_id"]

        if trip_id not in stop_times:
            stop_times[trip_id] = []
            stop_times_full[trip_id] = []

        stop_times[trip_id].append(row["stop_id"])
        stop_times_full[trip_id].append(row)

# trips
with open("trips.txt", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        trip_to_route[row["trip_id"]] = row["route_id"]

# routes
with open("routes.txt", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        route_to_name[row["route_id"]] = row["route_short_name"]

print("✅ Dane załadowane!")

@app.post("/plan")
def plan(data: RequestData):
    try:
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

        # 🚍 BEZPOŚREDNIE
        for trip_id, stops in stop_times.items():
            full = stop_times_full[trip_id]

            for s in start_ids:
                for e in end_ids:
                    if s in stops and e in stops:
                        i1 = stops.index(s)
                        i2 = stops.index(e)

                        if i1 < i2:
                            start_time = full[i1]["departure_time"]
                            end_time = full[i2]["arrival_time"]

                            line = route_to_name.get(trip_to_route.get(trip_id), "?")

                            return {
                                "route": [
                                    f"🚍 Linia {line}",
                                    f"🕒 {start_time} → {end_time}",
                                    f"{data.start} → {data.end}"
                                ],
                                "total_time": data.total_time
                            }

        # 🔁 PRZESIADKA
        for trip1_id, stops1 in stop_times.items():
            full1 = stop_times_full[trip1_id]

            for s in start_ids:
                if s in stops1:
                    i_start = stops1.index(s)

                    for transfer in stops1[i_start:]:
                        i_transfer = stops1.index(transfer)

                        for trip2_id, stops2 in stop_times.items():
                            if transfer in stops2:
                                full2 = stop_times_full[trip2_id]
                                i_transfer2 = stops2.index(transfer)

                                for e in end_ids:
                                    if e in stops2:
                                        i_end = stops2.index(e)

                                        if i_transfer2 < i_end:

                                            line1 = route_to_name.get(trip_to_route.get(trip1_id), "?")
                                            line2 = route_to_name.get(trip_to_route.get(trip2_id), "?")

                                            t1_start = full1[i_start]["departure_time"]
                                            t1_end = full1[i_transfer]["arrival_time"]

                                            t2_start = full2[i_transfer2]["departure_time"]
                                            t2_end = full2[i_end]["arrival_time"]

                                            transfer_name = stop_id_to_name.get(transfer, "?")

                                            return {
                                                "route": [
                                                    f"🚍 Linia {line1}",
                                                    f"🕒 {t1_start} → {t1_end}",
                                                    f"{data.start} → {transfer_name}",
                                                    "🔁 Przesiadka",
                                                    f"🚍 Linia {line2}",
                                                    f"🕒 {t2_start} → {t2_end}",
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
