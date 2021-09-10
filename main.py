from os.path import dirname
from logzero import logfile
from filemanager import DataFilesIO
from collector import Collector


# このファイルと同じ場所に出力
output_dir = dirname(__file__)

logfile("log.log", disableStderrLogger=False, maxBytes=32768, backupCount=5)


def main():
    file_manager = DataFilesIO(
        **{
            "raw_path": output_dir + "/raw.json",
            "input_path": output_dir + "/日本市町村人口.csv",
            "result_path": output_dir + "/自治体別駅設置年データ.csv",
            "priority_data_path": output_dir + "/priority_data.json",
        }
    )

    config = {
        "GET_NUM": 10,  # データを取得する最大数. 最大ならlen(man_list)でOK
    }
    collector = Collector(file_manager, config)
    collector.run()
    collector.save()


if __name__ == "__main__":
    main()
