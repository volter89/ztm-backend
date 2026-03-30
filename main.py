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

@app.post("/plan")
def plan(data: RequestData):
    try:
        start_name = data.start
        end_name = data.end

        stop_name_to_ids = {}

        with open("stops.txt", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stop_id = row["stop_id"]
                stop_name = row["stop_name"]

                if stop_name not in stop_name_to_ids:
                    stop_name_to_ids[stop_name] = []

                stop_name_to_ids[stop_name].append(stop_id)

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
            return {"route": ["❌ Nie znaleziono przystanku"], "total_time": data.total_time}

        stop_times = {}

        with open("stop_times.txt", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trip_id = row["trip_id"]
                stop_id = row["stop_id"]

                if trip_id not in stop_times:
                    stop_times[trip_id] = []

                stop_times[trip_id].append(stop_id)

        # 🔥 1. bezpośrednie
        for stops in stop_times.values():
            for s in start_ids:
                for e in end_ids:
                    if s in stops and e in stops and stops.index(s) < stops.index(e):
                        return {
                            "route": [
                                "🚍 Bezpośrednie połączenie",
                                f"{start_name} → {end_name}"
                            ],
                            "total_time": data.total_time
                        }

        # 🔥 2. przesiadka (LEPSZA WERSJA)

        for stops1 in stop_times.values():
            for s in start_ids:
                if s in stops1:

                    start_index = stops1.index(s)

                    # wszystkie przystanki po starcie
                    for transfer_stop in stops1[start_index:]:

                        # szukamy drugiego kursu
                        for stops2 in stop_times.values():
                            if transfer_stop in stops2:

                                transfer_index = stops2.index(transfer_stop)

                                for e in end_ids:
                                    if e in stops2 and transfer_index < stops2.index(e):

                                        return {
                                            "route": [
                                                "🔁 Połączenie z przesiadką",
                                                f"Start: {start_name}",
                                                f"Przesiadka (ID): {transfer_stop}",
                                                f"Koniec: {end_name}"
                                            ],
                                            "total_time": data.total_time
                                        }

        return {"route": ["❌ Nie znaleziono połączenia"], "total_time": data.total_time}

    except Exception as e:
        return {"route": [f"❌ Błąd: {str(e)}"], "total_time": 0}

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
