from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import csv
import unicodedata

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
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text

# 🚍 PLANOWANIE
@app.post("/plan")
def plan(data: RequestData):
    try:
        # 🔥 usuń cudzysłowy i śmieci
        start_name = data.start.replace('"', '').replace("'", "").strip()
        end_name = data.end.replace('"', '').replace("'", "").strip()

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

        # 🔍 NORMALIZACJA
        start_norm = normalize(start_name)
        end_norm = normalize(end_name)

        start_ids = []
        end_ids = []

        # 🔍 dopasowanie przystanków
        for name, ids in stop_name_to_ids.items():
            name_norm = normalize(name)

            if start_norm in name_norm:
                start_ids.extend(ids)

            if end_norm in name_norm:
                end_ids.extend(ids)

        if not start_ids or not end_ids:
            return {
                "route": ["❌ Nie znaleziono przystanku"],
                "total_time": data.total_time
            }

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

        # 🔍 SZUKANIE POŁĄCZENIA
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

    except Exception as e:
        return {
            "route": [f"❌ Błąd: {str(e)}"],
            "total_time": 0
        }

# 🔍 lista przystanków (do autocomplete)
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
