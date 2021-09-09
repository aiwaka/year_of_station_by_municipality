import csv
import os
from logzero import logfile
from crawl import crawler


# このファイルと同じ場所に出力
output_path = os.path.dirname(__file__)

logfile("log.log", disableStderrLogger=True)


def load_csv(filepath):
    try:
        with open(filepath, encoding="utf-8") as f:
            reader = csv.reader(f)
            # 名称だけの一次元リストとして取得
            data = [row.pop(0) for index, row in enumerate(reader) if index > 6]
    except Exception as e:
        print(e)
        exit()
    return data


def main():
    data = load_csv("日本市町村人口.csv")
    test = crawler.get_year_data(data[0])
    print(test)
    crawler.close_browser()


if __name__ == "__main__":
    main()
