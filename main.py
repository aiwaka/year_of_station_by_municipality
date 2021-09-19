from logzero import logfile
from collector import Collector

logfile("log.log", disableStderrLogger=False)


def main() -> None:
    config = {
        "START_INDEX": 0,  # 検索開始するインデックス
        "GET_NUM": 1900,  # データを取得する最大数. 指定しなければすべて取得する.
    }
    collector = Collector(config)
    collector.run()
    collector.save()


if __name__ == "__main__":
    main()
