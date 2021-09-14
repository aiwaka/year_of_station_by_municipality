from crawl import Crawler
from filemanager import file_manager
import traceback
from my_exception import ThisAppException
from error_storage import error_storage
from logzero import logger


class Collector:
    def __init__(self, config: dict) -> None:
        self.file_manager = file_manager
        self.crawler = Crawler()
        self.START_INDEX = config.get("START_INDEX", 0)
        self.END_INDEX = config.get("GET_NUM", 5) + self.START_INDEX
        self.man_list = file_manager.load_manicipalities_data()
        self.data = file_manager.load_raw_data()  # 保存データがあるなら読み込まれ, なければ空の辞書が返される.
        self.priority_data = file_manager.load_priority_data()

    def run(self):
        # 自治体リストを回してクローラに入れて結果を求める.
        # GET_NUMとリストの最大数で小さい方のインデックスまで繰り返す.
        for man_index in range(
            self.START_INDEX, min(self.END_INDEX, len(self.man_list))
        ):
            man_name = self.man_list[man_index]
            if man_name in self.data:
                # データにすでにあるとき
                pri_data = self.priority_data.get(man_name, {}).get("data", None)
                if pri_data:
                    # 優先データが指定されているならそれで置き換える.
                    # sta_data, max, minそれぞれについて個別に見る.
                    pri_sta_data = pri_data.get("sta_data", None)
                    pri_max_data = pri_data.get("max", None)
                    pri_min_data = pri_data.get("min", None)
                    if pri_sta_data:
                        self.data[man_name]["sta_data"] = pri_sta_data
                    if pri_max_data:
                        self.data[man_name]["max"] = pri_max_data
                    if pri_min_data:
                        self.data[man_name]["min"] = pri_min_data
                    # self.data[man_name] = pri_data
                    logger.info(
                        f"{man_name} : "
                        "priority data found. partially or fully replaced it."
                    )
                # ない場合は特に何もせず飛ばす.
                logger.info(f"{man_name} : data already exists. skipped")
                continue
            try:
                result = self.crawler.get_year_data(man_name)
                self.data[man_name] = result
                logger.info(f"{man_name} : {result}")
            except ThisAppException as e:
                logger.error(e)
                self.file_manager.save_raw_data(self.data)
                error_storage.add(e)
                continue
            except Exception as e:
                logger.error(traceback.format_exc())
                print(e)
                self.file_manager.save_raw_data(self.data)
        self.crawler.close_browser()
        return self.data

    def save(self):
        self.file_manager.save_raw_data(self.data)
        self.file_manager.output_csv(self.data)
        logger.info("summary:")
        logger.info(f"got {len(self.data)} data correctly.")
        if error_storage.storage:
            logger.info("the following error caused.")
            for e in error_storage.storage:
                logger.info(e)
        logger.info("script finished.")
