# 🔧 tylko fragment plan() – reszta zostaje jak masz

for trip_id, stops in stop_times.items():
    full = stop_times_full[trip_id]

    for s in current_ids:
        if s in stops:
            i = stops.index(s)
            dep = tmin(full[i]["departure_time"])

            if dep < current_time:
                continue

            wait = dep - current_time

            if wait < data.transfer_time:
                continue

            if wait > MAX_WAIT:
                continue

            # 🔥 WRACAMY DO PĘTLI ALE WYBIERAMY NAJLEPSZY J
            best_local = None
            best_length = 0

            for j in range(i+2, min(i+6, len(stops))):
                arr = tmin(full[j]["arrival_time"])
                seg = arr - dep

                if total_used + seg > data.total_time:
                    continue

                if seg > best_length:
                    best_length = seg
                    best_local = (trip_id, i, j, dep, arr)

            if best_local:
                if wait < best_wait:
                    best_wait = wait
                    best = best_local
