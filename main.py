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

# 🔥 PARAMETRY
MAX_WAIT = 20  # maksymalny czas oczekiwania na przesiadkę (min)

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

# 📦 LOAD
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

        # =========================
        # 🚍 TRYB NORMALNY (A → B)
        # =========================
        if data.start != data.end:
            for trip_id, stops in stop_times.items():
                full = stop_times_full[trip_id]

                for s in start_ids:
                    for e in end_ids:
                        if s in stops and e in stops:
                            i1 = stops.index(s)
                            i2 = stops.index(e)

                            if i1 < i2:
                                dep = full[i1]["departure_time"]
                                if time_to_minutes(dep) < now:
                                    continue

                                arr = full[i2]["arrival_time"]
                                line = route_to_name.get(trip_to_route.get(trip_id), "?")

                                return {
                                    "route": [
                                        f"🚍 Linia {line}",
                                        f"🕒 {dep} → {arr}",
                                        f"{data.start} → {data.end}"
                                    ],
                                    "total_time": data.total_time
                                }

        # =========================
        # 🔁 TRYB KONTROLI (PĘTLA)
        # =========================
        else:
            current_stop_ids = start_ids
            current_time = now
            total_used = 0
            route_output = []

            while total_used < data.total_time:

                found = False

                for trip_id, stops in stop_times.items():
                    full = stop_times_full[trip_id]

                    for s in current_stop_ids:
                        if s in stops:
                            i = stops.index(s)

                            dep = time_to_minutes(full[i]["departure_time"])

                            wait = dep - current_time

                            # 🔥 KLUCZOWY FIX
                            if wait < 0:
                                continue

                            if wait > MAX_WAIT:
                                continue

                            for j in range(i+2, min(i+6, len(stops))):
                                arr = time_to_minutes(full[j]["arrival_time"])

                                segment_time = arr - dep

                                if total_used + segment_time > data.total_time:
                                    continue

                                line = route_to_name.get(trip_to_route.get(trip_id), "?")
                                from_stop = stop_id_to_name.get(stops[i], "?")
                                to_stop = stop_id_to_name.get(stops[j], "?")

                                route_output.append(
                                    f"🚍 {line} | {full[i]['departure_time']} → {full[j]['arrival_time']} | {from_stop} → {to_stop}"
                                )

                                current_stop_ids = [stops[j]]
                                current_time = arr + data.transfer_time
                                total_used += segment_time

                                found = True
                                break

                        if found:
                            break
                    if found:
                        break

                if not found:
                    break

            route_output.append(f"🏁 Powrót (orientacyjnie) do: {data.start}")
            route_output.append(f"⏱ Wykorzystano ~{total_used} min")

            return {
                "route": route_output,
                "total_time": data.total_time
            }

        return {"route": ["❌ Nie znaleziono połączenia"], "total_time": data.total_time}

    except Exception as e:
        return {"route": [f"❌ Błąd: {str(e)}"], "total_time": 0}

@app.get("/stops")
def get_stops():
    return list(stop_name_to_ids.keys())
