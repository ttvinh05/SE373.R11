files = list_logs()
records_scanned = 0
counts = {}
for filename in files:
    records = read_log(filename)
    records_scanned += len(records)
    for record in records:
        if record["level"] == "ERROR":
            group = record["service"] + "/" + record["error_code"]
            counts[group] = counts.get(group, 0) + 1
emit({"files_scanned": len(files), "records_scanned": records_scanned, "counts": counts})
