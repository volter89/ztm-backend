from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 🔥 CORS FIX
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

@app.get("/")
def home():
    return {"status": "ZTM backend działa 🚍"}

@app.post("/plan")
def plan(data: RequestData):
    return {
        "route": [
            f"🚍 Start: {data.start}",
            f"➡️ Jedź około {data.ride_time} min",
            f"🔁 Przesiadka {data.transfer_time} min",
            f"🏁 Koniec: {data.end}"
        ],
        "total_time": data.total_time
    }
@app.get("/stops")
def get_stops():
    return [
        "Katowice Dworzec",
        "Katowice Strefa Kultury",
        "Chorzów Rynek",
        "Czeladź Staszica",
        "Czeladź Piaski",
        "Sosnowiec Dworzec PKP",
        "Bytom Dworzec"
    ]
