import csv
import os
import re
import json
import random
from time import sleep
from urllib.request import urlopen
from bs4 import BeautifulSoup


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


def get_address(sta_link):
    # 駅の住所を持ってくる
    try:
        with urlopen(sta_link) as response:
            html = response.read()
            sleep(3)
    except Exception as e:
        print(e)
        exit()
    soup = BeautifulSoup(html, "html.parser")
    # 開業年月日というテキストを持つthタグの隣のタグを持ってくる.
    row_tags = soup.select("th:-soup-contains('所在地')")
    result = []
    for row in row_tags:
        text = re.sub("[\n\ufeff/]", "", row.find_next_sibling().get_text())
        main_part = text.split(" ")[0]
        result.append(main_part)
    return result


def validate_man_name_test():
    # （MANDARA10）の自治体名と住所が一致しているか返す
    man_list = random.sample(load_manicipalities_data("日本市町村人口.csv"), 100)
    pattern = re.compile(r"(さいたま市|堺市|...??[都道府県市])(.+?[市区町村])")
    for man in man_list:
        print(f"original: {man}")
        match = pattern.search(man)
        print(match.groups())
