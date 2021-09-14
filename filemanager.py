import os
import csv
import json
from settings import file_manager_config


# 入出力クラス
# データ形式そのままのオブジェクトjsonのパスと結果csvファイルのパスを入力しておく.
class DataFilesIO:
    def __init__(self, raw_path, input_path, result_path, priority_data_path):
        self.raw_path = raw_path
        self.input_path = input_path
        self.result_path = result_path
        # 例外を補足して処理するための記述を書いたjsonのパス
        self.priority_data_path = priority_data_path

    def load_raw_data(self):
        if os.path.isfile(self.raw_path):
            with open(self.raw_path) as f:
                data = json.load(f)
        else:
            data = {}
        return data

    def save_raw_data(self, data):
        with open(self.raw_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def load_manicipalities_data(self):
        try:
            with open(self.input_path, encoding="utf-8") as f:
                reader = csv.reader(f)
                # 名称だけの一次元リストとして取得
                data = [row.pop(0) for index, row in enumerate(reader) if index > 6]
        except Exception as e:
            print(e)
            exit()
        return data

    def output_csv(self, data):
        # {"man_name": ({max_sta_name: max_year}, {min_sta_name: min_year})}形式で受け取る.
        with open(self.result_path, "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["MAP", "日本市町村"])
            writer.writerow(["TITLE", "直近年", "最古年"])
            writer.writerow(["UNIT", "年", "年"])
            for man in data:
                writer.writerow([man, data[man]["max"][1], data[man]["min"][1]])

    def load_priority_data(self):
        with open(self.priority_data_path) as f:
            priority_data = json.load(f)
        return priority_data

    def load_local_html(self, path):
        # 受け取ったパスのファイルが存在するならそれを返し, 存在しなければNoneを返す.
        if os.path.exists(path):
            with open(path) as f:
                html = f.read()
            return html
        else:
            return None


file_manager = DataFilesIO(**file_manager_config)
