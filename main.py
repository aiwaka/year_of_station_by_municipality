import csv
import os
from logzero import logfile, logger
from crawl import crawler
from output import save_raw_data, output_csv, load_raw_data
from my_exception import ThisAppException


# このファイルと同じ場所に出力
output_dir = os.path.dirname(__file__)

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
    CSV_OUTPUT_PATH = output_dir + "/自治体別駅設置年データ.csv"
    RAW_OUTPUT_PATH = output_dir + "/raw.json"
    man_list = load_csv("日本市町村人口.csv")
    if os.path.exists(RAW_OUTPUT_PATH):
        data = load_raw_data(RAW_OUTPUT_PATH)
    else:
        data = {}
    start_index = len(data)
    for i in range(start_index, 3):
        try:
            result = crawler.get_year_data(man_list[i])
            data[man_list[i]] = result
            print(result)
        except ThisAppException as e:
            logger.error(e)
            save_raw_data(data, RAW_OUTPUT_PATH)

    save_raw_data(data, RAW_OUTPUT_PATH)
    output_csv(data, CSV_OUTPUT_PATH)
    crawler.close_browser()


if __name__ == "__main__":
    main()
