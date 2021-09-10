import csv
import os
import json


def load_manicipalities_data(path):
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            # 名称だけの一次元リストとして取得
            data = [row.pop(0) for index, row in enumerate(reader) if index > 6]
    except Exception as e:
        print(e)
        exit()
    return data


def load_raw_data(path):
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f)
    else:
        data = {}
    return data


def data_exists(man_name, data):
    return data.get(man_name, None)
