from filemanager import StationData
import traceback
import re
from itertools import product
from typing import List, Dict, Final
from bs4.element import Tag
from bs4 import BeautifulSoup
from crawl import Crawler
from filemanager import file_manager
from error_storage import error_storage
from logzero import logger
from appexcp.my_exception import NoDateColumn, ElementNotFound, ThisAppException


def validate_man_name_and_address(man_name: str, address_list: list[str]) -> bool:
    # （MANDARA10の）自治体名と住所が一致しているか返す
    # これで（都道府県または政令市）（市区町村または政令市区）に分けることができる.
    pattern = re.compile(r"(さいたま市|堺市|...??[都道府県市])(.+?[市区町村])")
    # （市区町村または政令市区）を取得
    # partial_name = pattern.search(man_name).groups()[1]
    partial_name = match.groups()[1] if (match := pattern.search(man_name)) else None
    if not partial_name:
        raise ThisAppException(f"cannot find pattern from man_name({man_name}).")
    result = False
    for address in address_list:
        # 住所のリストにその名前が入っていればOKとする.
        if partial_name in address:
            result = True
    return result


class Collector:
    # 鉄道のことが記載されている見出しの名前リスト
    RAILWAY_TAG_ID: Final[List[str]] = [
        "鉄道",
        "鉄道路線",
        "鉄道・索道",
        "BRT",
        "鉄道と駅",
        "鉄道・ケーブルカー・ロープウェイ",
    ]
    # 廃線として記載されている可能性がある言葉のリスト
    ABANDONED_LINE_TEXT: Final[List[str]] = [
        "廃線",
        "廃止路線",
        "廃止された路線",
        "廃止された鉄道",
        "廃止された鉄道路線",
        "廃線となった路線",
        "廃線となった鉄道",
        "廃線となった鉄道路線",
        "かつてあった路線",
        "かつてあった鉄道",
        "かつてあった鉄道路線",
        "かつて存在した鉄道",
        "かつて存在した鉄道路線",
        "過去に存在した鉄道",
        "過去に存在した路線",
        "過去に存在した鉄道路線",
    ]
    # リンクとして考えられるが固有名詞ではないものをリストにしておく.
    NON_PROPER_NAME: Final[List[str]] = [
        "旅客",
        "鉄道",
        "休止",
        "臨時",
        "請願",
        "貨物",
        "貨物ターミナル",
        "",
    ]

    def __init__(self, config: dict) -> None:
        self.crawler = Crawler()
        # 自治体名リストを取得.
        self.man_list: List[str] = file_manager.load_manicipalities_data()
        self.START_INDEX: Final[int] = config.get("START_INDEX", 0)
        self.END_INDEX: Final[int] = min(
            config.get("GET_NUM", len(self.man_list)) + self.START_INDEX,
            len(self.man_list),
        )
        self.data = file_manager.load_raw_data()  # 保存データがあるなら読み込まれ, なければ空の辞書が返される.
        self.priority_data = file_manager.load_priority_data()  # 優先データを辞書で読み込む.
        self.address_data: Dict[str, List[str]] = file_manager.load_address_dict()

    def get_station_links(self, man_name: str) -> Dict[str, str]:
        # 自治体名からそこに属する駅のリンクのリストを持ってくる.
        # {"駅名": "リンク"}の辞書で返す.
        html = self.crawler.get_source(man_name)
        soup = BeautifulSoup(html, "html.parser")

        # まずh3タグで検索
        base_tag_name: str = "h3"
        base_tags = soup.select(
            # ",".join(map(lambda text: f"h3:has( > span#{text})", RAILWAY_TAG_ID))
            ",".join([f"h3:has( > span#{text})" for text in self.RAILWAY_TAG_ID])
        )
        if not base_tags:
            # だめならh4タグで検索
            base_tag_name = "h4"
            base_tags = soup.select(
                ",".join([f"h4:has( > span#{text})" for text in self.RAILWAY_TAG_ID])
            )
        if not base_tags:
            # それでもだめなら例外
            raise ElementNotFound(f"railroad section not found : {man_name}")
        railroad_blocks: list[Tag] = []
        for base_tag in base_tags:
            next_tag = base_tag.find_next_sibling()
            # 鉄道が書いてあるh3またはh4から次のものまでの間のタグを保存する.
            # ただしclassにgalleryを含むものは不要なので取り除きたい.
            while type(next_tag) is Tag and next_tag.name != base_tag_name:
                if (
                    "class" not in next_tag.attrs
                    or "gallery" not in next_tag.attrs["class"]
                ):
                    railroad_blocks.append(next_tag)
                next_tag = next_tag.find_next_sibling()

        # 「廃線」や「廃止された鉄道」などがあるなら警告として出しておく.
        warning_text: str = ""
        # まずidから探す. セレクタを作り, 一つでもあればOK.
        if abandoned_line := soup.select_one(
            ",".join([f"#{text}" for text in self.ABANDONED_LINE_TEXT])
        ):
            warning_text = (
                f"abandoned line may exist : {abandoned_line.attrs['id']} : {man_name}"
            )
        else:
            # なければ個別にテキスト検索する.
            for block in railroad_blocks:
                # まずそれらしいテキストで検索.
                for text in self.ABANDONED_LINE_TEXT:
                    if block.select_one(f"*:-soup-contains('{text}')"):
                        warning_text = f"abandoned line may exist : {text} : {man_name}"
                        break
                if warning_text:
                    break
                else:
                    # まだなければ「かつては」で検索
                    if block.select_one("p:-soup-contains('かつては')"):
                        warning_text = (
                            f"abandoned line may exist : かつては... : {man_name}"
                        )
                        break
        if warning_text:
            error_storage.add(warning_text, "w")

        result_dict: Dict[str, str] = {}
        # station_name_pattern = re.compile(r"(?<!旅客|鉄道|休止|臨時|請願)(駅|停留場)$")

        # 取ってきたタグの中で駅や停留所を探して順番に検査する.
        for block in railroad_blocks:
            # どうせ住所チェックするので, 駅を含むリンクすべて取ってくることにする.
            # ただし少なくとも敦賀市では失敗する.
            link_list = block.select("a:-soup-contains('駅'),a:-soup-contains('停留場')")
            for link in link_list:
                sta_name = link.get_text()
                is_proper_name: bool = True
                # 取得したくないテキストのリストを生成して回す
                for non_proper_text in [
                    name_text + sta_text
                    for name_text, sta_text in product(
                        self.NON_PROPER_NAME, ["駅", "停留場"]
                    )
                ]:
                    # 取得したくないテキストが駅名に含まれていたらフラグを下ろす
                    if non_proper_text in sta_name:
                        is_proper_name = False
                        break
                # フラグが立っているときだけ辞書に追加する.
                if is_proper_name:
                    result_dict[sta_name] = link.attrs["href"]
        if not result_dict:
            raise ElementNotFound(f"railroad section not found : {man_name}")
        return result_dict

    def get_year_data(self, man_name: str, force: bool = False) -> StationData:
        # manicipalityの名前からスクレイピングして最も古い・新しい駅の設置年をとってくる.
        # forceがTrueだと優先データを読み込むことをしない.
        if not force:
            if man_pri_data := self.priority_data.get(man_name, None):
                if man_pri_data.get("nodata", False):
                    # nodata属性がTrueなら決められたデータを返す.
                    return {"sta_data": [], "max": ["なし", 0], "min": ["なし", 0]}
                elif pri_data := man_pri_data.get("data", None):
                    # 優先データが指定されているならそれを返す.
                    # ただし, クロールの段階では全部のデータが揃っていないと不可とする.

                    if (
                        pri_data.get("sta_data", None)
                        and pri_data.get("max", None)
                        and pri_data.get("min", None)
                    ):
                        return pri_data
                    else:
                        error_storage.add(
                            f"{man_name} : priority data exists, "
                            "but not all attrs are available.",
                            "w",
                        )
        years_data: Dict[str, int] = {}
        # wikiに載っている駅データをとりあえずすべて取得
        sta_link_data: Dict[str, str] = self.get_station_links(man_name)
        # 住所チェック失敗した駅を登録しておくためのリスト
        address_error_stations: List[str] = []
        for sta_name, sta_link in sta_link_data.items():
            # 順番に開業年をチェックしていく. このときに住所チェックも行う.
            html: str = self.crawler.get_station_html(
                sta_name, "https://ja.wikipedia.org" + sta_link
            )
            soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
            address_list: List[str] = self.crawler.get_address_list(
                sta_name, self.address_data, soup
            )
            if not address_list:
                raise NoDateColumn(f"cannot find address data : {sta_name}")
            # 住所チェックしてだめならこの駅を飛ばす
            if not validate_man_name_and_address(man_name, address_list):
                address_error_stations.append(sta_name)
                continue
            if sta_year := self.crawler.get_opening_date(sta_name, soup):
                years_data[sta_name] = sta_year
                print(f"{sta_name} : {years_data[sta_name]}年")

        if address_error_stations:
            error_storage.add(
                f"{man_name} : address check failed for the following stations.", "w"
            )
            error_storage.add(str(address_error_stations), "w")
        if not years_data:
            raise ElementNotFound(f"railroad section not found : {man_name}")

        max_year_name = max(years_data, key=lambda key: years_data.get(key, 0))
        min_year_name = min(years_data, key=lambda key: years_data.get(key, 0))

        return {
            "sta_data": list(years_data.keys()),
            "max": [max_year_name, years_data[max_year_name]],
            "min": [min_year_name, years_data[min_year_name]],
        }

    def run(self) -> None:
        # 自治体リストを回してクローラに入れて結果を求める.
        for man_name in self.man_list[self.START_INDEX : self.END_INDEX]:  # noqa: E203
            if man_name in self.data:
                # データにすでにあるとき, 優先データで置き換えるか単純に飛ばす
                if pri_data := self.priority_data.get(man_name, {}).get("data", None):
                    # 優先データが指定されているならそれで置き換える.
                    # sta_data, max, minそれぞれについて個別に見る.
                    if pri_sta_data := pri_data.get("sta_data", None):
                        self.data[man_name]["sta_data"] = pri_sta_data
                    if pri_max_data := pri_data.get("max", None):
                        self.data[man_name]["max"] = pri_max_data
                    if pri_min_data := pri_data.get("min", None):
                        self.data[man_name]["min"] = pri_min_data
                    logger.info(
                        f"{man_name} : "
                        "priority data found. partially or fully replaced it."
                    )
                else:
                    logger.info(f"{man_name} : data already exists. skipped")
                continue
            try:
                result = self.get_year_data(man_name)
                self.data[man_name] = result
                logger.info(f"got data : {man_name} : {result}")
            except ThisAppException as e:
                file_manager.save_raw_data(self.data)
                error_storage.add(e, "e")
                continue
            except Exception:
                e = traceback.format_exc()
                error_storage.add(e, "e")
                file_manager.save_raw_data(self.data)
        self.crawler.close_browser()

    def save(self) -> None:
        file_manager.save_raw_data(self.data)
        file_manager.output_csv(self.data)
        logger.info("summary:")
        logger.info(f"got {len(self.data)} data correctly.")
        if error_storage.storage:
            logger.info("the following error caused.")
            for e in error_storage.storage:
                logger.info(e)
        logger.info("script finished.")
