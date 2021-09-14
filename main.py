from logzero import logfile
from collector import Collector

logfile("log.log", disableStderrLogger=False)


def main():
    config = {
        "START_INDEX": 10,  # 検索開始するインデックス
        "GET_NUM": 5,  # データを取得する最大数. 最大ならlen(man_list)でOK
    }
    collector = Collector(config)
    collector.run()
    collector.save()


if __name__ == "__main__":
    main()
