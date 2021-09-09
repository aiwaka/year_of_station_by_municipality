import csv
import json


def save_raw_data(data, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data))


def load_raw_data(path):
    with open(path) as f:
        data = json.load(f)
    return data


def output_csv(data, path):
    # {"man_name": (max_sta_name, max_year, min_sta_name, min_year)}形式で受け取る.
    with open(path, "w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["MAP", "日本市町村"])
        writer.writerow(["TITLE", "直近年", "最古年"])
        writer.writerow(["UNIT", "年", "年"])
        for man in data:
            writer.writerow([man, data[man][1], data[man][3]])
