import os
import csv
import json
from settings import file_manager_config
from typing import Union


# 入出力クラス
# データ形式そのままのオブジェクトjsonのパスと結果csvファイルのパスを入力しておく.
class DataFilesIO:
    def __init__(
        self,
        raw_path,
        input_path,
        result_path,
        priority_data_path,
        address_data_path,
        wiki_storage_dir,
    ):
        self.raw_path = raw_path
        self.input_path = input_path
        self.result_path = result_path
        # 例外を補足して処理するための記述を書いたjsonのパス
        self.priority_data_path = priority_data_path
        self.address_data_path = address_data_path
        # wikipediaのページを保存しておくディレクトリ
        self.wiki_storage_dir = wiki_storage_dir

    def load_raw_data(self) -> dict:
        # データオブジェクトのファイルを読み込んで辞書で返す.
        if os.path.isfile(self.raw_path):
            with open(self.raw_path) as f:
                data = json.load(f)
        else:
            data = {}
        return data

    def save_raw_data(self, data) -> None:
        # データオブジェクトをファイルに保存する
        with open(self.raw_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def load_manicipalities_data(self) -> list:
        # MANDARA10の市町村プリセットのcsvから自治体名の名称リストを返す
        try:
            if ".csv" not in self.input_path:
                # csvファイルでなければ開かずエラーにする.
                raise Exception("tried to open a non-csv file.")
            with open(self.input_path, encoding="utf-8") as f:
                reader = csv.reader(f)
                # 名称だけの一次元リストとして取得
                data = [row.pop(0) for index, row in enumerate(reader) if index > 6]
        except Exception as e:
            print(e)
            exit()
        return data

    def output_csv(self, data: dict) -> None:
        # {
        #   "man_name": {
        #       "sta_name": ["name", "name", ...],
        #       "max": ["name", year],
        #       "min": ["name", year]
        #   }
        # }
        # の形式を受け取り, MANDARA10で読み込めるcsvを出力する.
        with open(self.result_path, "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["MAP", "日本市町村"])
            writer.writerow(["TITLE", "直近年", "最古年"])
            writer.writerow(["UNIT", "年", "年"])
            for man in data:
                writer.writerow([man, data[man]["max"][1], data[man]["min"][1]])

    def load_priority_data(self) -> dict:
        # 優先データを読み込んで自治体名がキーの辞書で返す
        with open(self.priority_data_path) as f:
            priority_data = json.load(f)
        return priority_data

    def load_address_dict(self) -> dict:
        # 駅名に対応する住所のデータを返す.
        # 一つの駅名に対して複数の所在地があることがあるのでvalueはリスト形式.
        with open(self.address_data_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            res_dict = {}
            for row in reader:
                if row[2] in res_dict:
                    res_dict[row[2]].append(row[8])
                else:
                    res_dict[row[2]] = [row[8]]
        return res_dict

    def save_local_html(self, man_name: str, html: str) -> None:
        # htmlソースを受け取ってfilenameで保存ディレクトリに保存する.
        FILE_PATH = self.wiki_storage_dir + man_name + ".html"
        with open(FILE_PATH, mode="w") as f:
            f.write(html)

    def load_local_html(self, man_name) -> Union[str, None]:
        # 受け取ったパスのファイルが存在するならそれを返し, 存在しなければNoneを返す.
        FILE_PATH = self.wiki_storage_dir + man_name + ".html"
        if os.path.exists(FILE_PATH):
            with open(FILE_PATH) as f:
                html = f.read()
            return html
        else:
            return None


file_manager = DataFilesIO(**file_manager_config)
