from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import csv
import unicodedata
import re

app = FastAPI()

# 🔥 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🟢 TEST
@app.get("/")
def home():
    return {"status": "ZTM backend działa 🚍"}

# 📦 dane wejściowe
class RequestData(BaseModel):
    start: str
    end: str
    ride_time: int
    transfer_time: int
    total_time: int

# 🔤 NORMALIZACJA
def normalize(text):
    text = text.lower().strip()
    text = text.replace('"', '').replace("'", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\b\d+\b", "", text)
    return text.strip()

# 🚍 PLANOWANIE
@app.post("/plan")
def plan(data: RequestData):
    try:
        start_name = data.start
        end_name = data.end

        # 📦 wczytaj stops
        stop_name_to_ids = {}
        with open("stops.txt", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stop_id = row["stop_id"]
                stop_name = row["stop_name"]

                if stop_name not in stop_name_to_ids:
                    stop_name_to_ids[stop_name] = []

                stop_name_to_ids[stop_name].append(stop_id)

        # 🔍 dopasowanie nazw
        start_norm = normalize(start_name)
        end_norm = normalize(end_name)

        start_ids = []
        end_ids = []

        for name, ids in stop_name_to_ids.items():
            name_norm = normalize(name)

            if start_norm in name_norm or name_norm in start_norm:
                start_ids.extend(ids)

            if end_norm in name_norm or name_norm in end_norm:
                end_ids.extend(ids)

        if not start_ids or not end_ids:
            return {
                "route": ["❌ Nie znaleziono przystanku"],
                "total_time": data.total_time
            }

        # 📦 wczytaj stop_times
        stop_times = {}

        with open("stop_times.txt", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trip_id = row["trip_id"]
                stop_id = row["stop_id"]

                if trip_id not in stop_times:
                    stop_times[trip_id] = []

                stop_times[trip_id].append(stop_id)

        # 🔍 1. BEZPOŚREDNIE POŁĄCZENIE
        for trip_id, stops in stop_times.items():
            for s_id in start_ids:
                for e_id in end_ids:
                    if s_id in stops and e_id in stops:
                        if stops.index(s_id) < stops.index(e_id):
                            return {
                                "route": [
                                    "🚍 Bezpośrednie połączenie",
                                    f"Start: {start_name}",
                                    f"Koniec: {end_name}"
                                ],
                                "total_time": data.total_time
                            }

        # 🔥 2. PRZESIADKA (A → X → B)

        # znajdź trasy ze startu
        start_trips = []
        for trip_id, stops in stop_times.items():
            if any(s in stops for s in start_ids):
                start_trips.append((trip_id, stops))

        # znajdź trasy do końca
        end_trips = []
        for trip_id, stops in stop_times.items():
            if any(e in stops for e in end_ids):
                end_trips.append((trip_id, stops))

        # 🔍 szukaj wspólnego przystanku
        for trip1_id, stops1 in start_trips:
            for trip2_id, stops2 in end_trips:

                # wspólne przystanki
                common_stops = set(stops1) & set(stops2)

                for transfer_stop in common_stops:

                    for s_id in start_ids:
                        if s_id in stops1 and stops1.index(s_id) < stops1.index(transfer_stop):

                            for e_id in end_ids:
                                if e_id in stops2 and stops2.index(transfer_stop) < stops2.index(e_id):

                                    return {
                                        "route": [
                                            "🔁 Połączenie z przesiadką",
                                            f"Start: {start_name}",
                                            f"Przesiadka na przystanku ID: {transfer_stop}",
                                            f"Koniec: {end_name}"
                                        ],
                                        "total_time": data.total_time
                                    }

        return {
            "route": ["❌ Nie znaleziono połączenia"],
            "total_time": data.total_time
        }

    except Exception as e:
        return {
            "route": [f"❌ Błąd: {str(e)}"],
            "total_time": 0
        }

# 🔍 lista przystanków
@app.get("/stops")
def get_stops():
    stops = []

    with open("stops.txt", encoding="utf-8-sig") as f:
        next(f)
        for line in f:
            parts = line.split(",")
            if len(parts) > 2:
                stops.append(parts[2])

    return list(set(stops))
