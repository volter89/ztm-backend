dep = tmin(full[i]["departure_time"])

if dep < current_time:
    continue

# ✅ brakująca linia
wait = dep - current_time

# ⏱ max czekanie
if wait > 20:
    continue

# ⏱ min przesiadka
if wait < 2:
    continue

for j in range(i+2, min(i+8, len(stops))):
    arr = tmin(full[j]["arrival_time"])

    if arr <= dep:
        continue

    seg = arr - dep

    if seg <= 1:
        continue

    if path and seg < data.ride_time:
        continue

    if arr - data.start_time > data.total_time:
        continue

    line = route_to_name.get(trip_to_route.get(trip_id), "?")
    from_stop = stop_id_to_name[stop_id]
    to_stop = stop_id_to_name[stops[j]]

    new_path = path + [(
        line, dep, arr, from_stop, to_stop
    )]

    # 🎯 KONIEC TRASY
    if normalize(data.end) in normalize(to_stop):
        best_route = new_path
        best_time = arr - new_path[0][1] if new_path else 0

        result = []
        for l, d, a, f, t in best_route:
            result.append(
                f"🚍 Linia {l}\n🕒 {d//60:02d}:{d%60:02d} → {a//60:02d}:{a%60:02d}\n{f} → {t}"
            )

        result.append(f"🏁 Koniec: {to_stop}")
        result.append(f"⏱ Wykorzystano ~{int(best_time)} min")

        return {"route": result, "total_time": data.total_time}

    queue.append((stops[j], arr, new_path))
