from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 🔥 CORS (żeby frontend działał)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🟢 TEST (TEN ELEMENT CI BRAKOWAŁ)
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

# 🚍 PLANOWANIE
@app.post("/plan")
def plan(data: RequestData):
    import csv

    start_name = data.start
    end_name = data.end

    stop_name_to_ids = {}

    # 📦 mapowanie: nazwa -> lista ID
    with open("stops.txt", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stop_id = row["stop_id"]
            stop_name = row["stop_name"]

            if stop_name not in stop_name_to_ids:
                stop_name_to_ids[stop_name] = []

            stop_name_to_ids[stop_name].append(stop_id)

    if start_name not in stop_name_to_ids or end_name not in stop_name_to_ids:
        return {
            "route": ["❌ Nie znaleziono przystanku"],
            "total_time": data.total_time
        }

    start_ids = stop_name_to_ids[start_name]
    end_ids = stop_name_to_ids[end_name]

    stop_times = {}

    # 📦 wczytaj stop_times
    with open("stop_times.txt", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = row["trip_id"]
            stop_id = row["stop_id"]

            if trip_id not in stop_times:
                stop_times[trip_id] = []

            stop_times[trip_id].append(stop_id)

    # 🔍 SZUKANIE
    for trip_id, stops in stop_times.items():

        for start_id in start_ids:
            for end_id in end_ids:

                if start_id in stops and end_id in stops:
                    if stops.index(start_id) < stops.index(end_id):
                        return {
                            "route": [
                                "🚍 Znaleziono bezpośrednie połączenie!",
                                f"Start: {start_name}",
                                f"Koniec: {end_name}"
                            ],
                            "total_time": data.total_time
                        }

    return {
        "route": ["❌ Nie znaleziono bezpośredniego połączenia"],
        "total_time": data.total_time
    }

# 🔍 lista przystanków z pliku GTFS
@app.get("/stops")
def get_stops():
    stops = []

    with open("stops.txt", encoding="utf-8-sig") as f:
        next(f)  # pomiń nagłówek
        for line in f:
            parts = line.split(",")
            if len(parts) > 2:
                stops.append(parts[2])  # nazwa przystanku

    return list(set(stops))  # usuwa duplikaty
