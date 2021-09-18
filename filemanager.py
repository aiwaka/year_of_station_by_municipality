import os
import csv
import json
from settings import file_manager_config
from typing import Any, List, Dict, Union

StationData = Dict[str, List[Union[str, int]]]


# 入出力クラス
# と結果csvファイルのパスを入力しておく.
class DataFilesIO:
    """データをファイルで入出力するためのクラス

    Attributes:
        raw_path (str): データ形式そのままのオブジェクトjsonのパス.
        input_path (str): 自治体名が記載されたcsv（MANDARA10のプリセット）のパス
        result_path (str): 結果出力パス
        priority_data_path (str): 優先データのjsonファイルのパス.
        address_data_path (str): 駅ごとの所在地が書いてあるcsvのパス.
        wiki_storage_dir (str): 自治体のhtmlを保存しておくディレクトリ.
    """

    def __init__(
        self,
        raw_path,
        input_path,
        result_path,
        priority_data_path,
        address_data_path,
        wiki_storage_dir,
    ) -> None:
        self.raw_path = raw_path
        self.input_path = input_path
        self.result_path = result_path
        self.priority_data_path = priority_data_path
        self.address_data_path = address_data_path
        self.wiki_storage_dir = wiki_storage_dir

    def load_raw_data(self) -> Dict[str, StationData]:
        """保存してあったローデータを取得

        ファイルで保存してあるraw_dataを読み込み辞書形式で取得して返す.

        Returns:
            Dict[str, StationData]: 駅データの辞書.
        """
        if ".json" not in self.raw_path:
            # jsonファイルでなければ開かずエラーにする.
            raise Exception("tried to open a non-json file. (raw data)")
        if os.path.isfile(self.raw_path):
            with open(self.raw_path) as f:
                data: Dict[str, StationData] = json.load(f)
        else:
            data: Dict[str, StationData] = {}
        return data

    def save_raw_data(self, data: Dict[str, StationData]) -> None:
        """ローデータを保存

        駅データをraw_dataのパスのファイルに保存する.

        Args:
            data (Dict[str, StationData]): 駅データの辞書.
        """
        with open(self.raw_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def load_manicipalities_data(self) -> List[str]:
        """自治体名リストを取得

        MANDARA10の市町村プリセットのcsvから自治体名の名称リストを返す.

        Returns:
            List[str]: 自治体名リスト.
        """
        if ".csv" not in self.input_path:
            # csvファイルでなければ開かずエラーにする.
            raise Exception("tried to open a non-csv file. (manicipalities name data)")
        with open(self.input_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            # 名称だけの一次元リストとして取得
            data = [row.pop(0) for index, row in enumerate(reader) if index > 6]
        return data

    def output_csv(self, data: Dict[str, StationData]) -> None:
        """結果を出力

        駅データを整形してMANDARA10で読み込めるcsv形式で出力する.

        Args:
            data: Dict[str, StationData]: 駅データの辞書. sta_data, max, min属性を持っていること.
        """
        with open(self.result_path, "w", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["MAP", "日本市町村"])
            writer.writerow(["TITLE", "直近年", "最古年"])
            writer.writerow(["UNIT", "年", "年"])
            for man in data:
                writer.writerow([man, data[man]["max"][1], data[man]["min"][1]])

    def load_priority_data(self) -> Dict[str, Dict[str, Any]]:
        """優先データを取得.

        優先データを読み込んで自治体名がキーの辞書で返す.

        Returns:
            Dict[str, Dict[str, Any]]: 優先データ. nodata, data, url属性など.
        """
        with open(self.priority_data_path) as f:
            priority_data: Dict[str, Dict[str, Any]] = json.load(f)
        return priority_data

    def load_address_dict(self) -> Dict[str, List[str]]:
        """所在地データを返す.

        駅名に対応する住所のデータを返す. 一つの駅名に対して複数の所在地があることがあるのでvalueはリスト形式.

        Returns:
            Dict[str, List[str]]: 住所リストが値で駅名がキーの辞書.
        """
        with open(self.address_data_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            res_dict: Dict[str, List[str]] = {}
            for row in reader:
                if row[2] in res_dict:
                    res_dict[row[2]].append(row[8])
                else:
                    res_dict[row[2]] = [row[8]]
        return res_dict

    def save_local_html(self, man_name: str, html: str) -> None:
        """htmlを保存

        htmlソースを受け取ってman_nameをファイル名として保存ディレクトリに保存する.

        Args:
            man_name (str): 自治体名. ファイル名も兼ねる.
            html (str): 保存する内容.
        """
        FILE_PATH = self.wiki_storage_dir + man_name + ".html"
        with open(FILE_PATH, mode="w") as f:
            f.write(html)

    def load_local_html(self, man_name: str) -> Union[str, None]:
        """保存されたhtmlを読み込む

        htmlを読み込んで返す. 存在しないか失敗した場合Noneを返す.

        Args:
            man_name (str): 自治体名. ファイル名も兼ねる.

        Returns:
            str | None: htmlソースを返す. 返せないときはNone.

        """
        # 受け取ったパスのファイルが存在するならそれを返し, 存在しなければNoneを返す.
        FILE_PATH = self.wiki_storage_dir + man_name + ".html"
        if os.path.exists(FILE_PATH):
            with open(FILE_PATH) as f:
                html = f.read()
            return html
        else:
            return None


file_manager = DataFilesIO(**file_manager_config)
