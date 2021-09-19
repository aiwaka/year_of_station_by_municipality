"""データ収集

駅データを収集・整理する.

"""

from filemanager import StationData
import traceback
import re
from typing import List, Dict, Final
from bs4.element import Tag
from bs4 import BeautifulSoup
from crawl import Crawler
from filemanager import file_manager
from error_storage import error_storage
from logzero import logger
from appexcp.my_exception import ElementNotFound, NoDateInfo, ThisAppException


def validate_man_name_and_address(man_name: str, address_list: List[str]) -> bool:
    """自治体名と住所の整合性チェック

    （MANDARA10の）自治体名と住所が一致しているか返す.

    Args:
        man_name (str): 自治体名. （[都道府県][自治体名]）または（[政令市][政令市区]）または（[東京都][特別区]）の形.
        address_list (List[str]): 住所リスト. 住所文字列を任意の個数リストに入れたもの.

    Returns:
        bool: Trueなら一つでも引っかかるものがある. Falseならすべて整合していない.

    Raises:
        ThisAppException: 入力された自治体名が形式に沿っていない場合発生.
    """
    # これで（都道府県または政令市）（市区町村または政令市区）に分けることができる.
    pattern = re.compile(r"(さいたま市|堺市|...??[都道府県市])(.+?[市区町村])")
    # （市区町村または政令市区）を取得
    partial_name = match.groups()[1] if (match := pattern.search(man_name)) else None
    if not partial_name:
        raise ThisAppException(f"cannot find pattern from man_name({man_name}).")
    return any([partial_name in address for address in address_list])


class Collector:
    """データ収集クラス

    自治体名から駅データを集めてくる本体クラス.

    Attributes:
        RAILWAY_TAG_ID (List[str]): 鉄道のことが記載されているWikiの見出しの名前のリスト.
        ABANDONED_LINE_TEXT (List[str]): 廃線として記載されている可能性がある言葉のリスト.
        NON_PROPER_NAME (List[str]): リンクとして考えられるが駅名ではないものをリストにしておく.
        crawler (Cralwer): ウェブから情報を持ってくるためのクローラ.
        man_list (List[str]): 自治体名リスト.
        START_INDEX ((constant) int): 検索し始める番号.
        END_INDEX ((constant) int): この番号まで検索.
        data (Dict[str, StationData]): 自治体名に対する駅データを保存する. ローデータを最初に読み込む.
        priority_data (Dict[str, Dict[str, Any]]): 優先データ. キーは自治体名.
        address_data (Dict[str, List[str]]): 住所録. 自治体名に対して住所のリストが保存される.

    Args:
        config (dict, optional): START_INDEX, GET_NUM属性をもたせた辞書を渡す.
    """

    RAILWAY_TAG_ID: Final[List[str]] = [
        "鉄道",
        "鉄道路線",
        "鉄道・軌道",
        "鉄道・索道",
        "BRT",
        "鉄道と駅",
        "鉄道・ケーブルカー・ロープウェイ",
        "鉄道路線・駅",
    ]
    ABANDONED_LINE_TEXT: Final[List[str]] = [
        "廃線",
        "廃止路線",
        "廃止鉄道路線",
        "廃止鉄道線",
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
    NON_PROPER_NAME: Final[List[str]] = [
        "旅客",
        "鉄道",
        "無人",
        "休止",
        "臨時",
        "請願",
        "貨物",
        "貨物ターミナル",
    ]

    def __init__(self, config: dict = {}) -> None:
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
        """駅リンクのリストを取得

        自治体名からそこに属する駅のリンクのリストを持ってくる. このとき住所チェックはしない.

        Args:
            man_name (str): 自治体名.

        Returns:
            Dict[str, str]: 駅名がキー, リンクが値の辞書を返す.

        Raises:
            ElementNotFound: 鉄道駅のリンクを取得できなかった場合に発生.
        """
        html = self.crawler.get_source(man_name)
        soup = BeautifulSoup(html, "html.parser")

        # まずh3タグで検索
        base_tag_name: str = "h3"
        base_tags = soup.select(
            ",".join([f"h3:has( > span#{text})" for text in self.RAILWAY_TAG_ID])
        )
        if not base_tags:
            # だめならh4タグで検索
            base_tag_name = "h4"
            base_tags = soup.select(
                ",".join([f"h4:has( > span#{text})" for text in self.RAILWAY_TAG_ID])
            )
        if not base_tags:
            # 現状高松市のみだがh2でも検索
            base_tag_name = "h2"
            base_tags = soup.select(
                ",".join([f"h2:has( > span#{text})" for text in self.RAILWAY_TAG_ID])
            )
        if not base_tags:
            # それでもだめなら例外
            raise ElementNotFound(man_name)
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
        # 取ってきたタグの中で駅や停留所を探して順番に検査する.
        for block in railroad_blocks:
            # どうせ住所チェックするので, 駅を含むリンクすべて取ってくることにする.
            # ただし少なくとも敦賀市では失敗する.
            link_list = block.select("a:-soup-contains('駅'),a:-soup-contains('停留場')")
            for link in link_list:
                sta_name = link.get_text()
                # 取得したくないテキストのリストを回して全てに対して問題なければ辞書に追加する.
                if all(
                    (
                        sta_name.endswith(("駅", "停留場"))
                        and (non_proper_text not in re.sub("駅|停留場", "", sta_name))
                        and sta_name != "駅"
                        and sta_name != "停留場"
                    )
                    for non_proper_text in self.NON_PROPER_NAME
                ):
                    result_dict[sta_name] = link.attrs["href"]
        if not result_dict:
            raise ElementNotFound(man_name)
        return result_dict

    def get_year_data(self, man_name: str, force: bool = False) -> StationData:
        """駅設置年データを取得.

        自治体名に対して駅一覧と, 最近・最古の駅設置年のデータを返す.

        Args:
            man_name (str): 自治体名.
            force (bool, optional): 本来一度取得した自治体はスキップするが, そうせずにもう一度クロールから行うフラグ.

        Returns:
            StationData: sta_data, max, minを含む辞書を返す.

        Raises:
            NoDateInfo: 年データが取れなかった場合に発生.
        """
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
            # wikiへのリンクではないならもう飛ばす
            if "/wiki/" not in sta_link:
                continue
            # 順番に開業年をチェックしていく. このときに住所チェックも行う.
            html: str = self.crawler.get_station_html(
                sta_name, "https://ja.wikipedia.org" + sta_link
            )
            soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
            if not (
                address_list := self.crawler.get_address_list(
                    sta_name, self.address_data, soup
                )
            ):
                error_message: Final[
                    str
                ] = f"{man_name} : cannot find address data : {sta_name}"
                error_storage.add(error_message)
                logger.error(error_message)
                continue
            # 住所チェックしてだめならこの駅を飛ばす
            if not validate_man_name_and_address(man_name, address_list):
                address_error_stations.append(sta_name)
                continue
            if sta_year := self.crawler.get_opening_date(soup):
                years_data[sta_name] = sta_year
                print(f"{sta_name} : {years_data[sta_name]}年")
            else:
                logger.warning(f"no date column ({sta_name})")
                error_storage.add(f"no date column ({sta_name})")

        if address_error_stations:
            error_storage.add(
                f"{man_name} : address check failed for the following stations.", "w"
            )
            error_storage.add(str(address_error_stations), "w")
        if not years_data:
            raise NoDateInfo(man_name)

        max_year_name = max(years_data, key=lambda key: years_data.get(key, 0))
        min_year_name = min(years_data, key=lambda key: years_data.get(key, 0))

        return {
            "sta_data": list(years_data.keys()),
            "max": [max_year_name, years_data[max_year_name]],
            "min": [min_year_name, years_data[min_year_name]],
        }

    def run(self) -> None:
        """実行

        自治体リストを回してクローラに入れて結果を求める.
        """
        for man_name in self.man_list[self.START_INDEX : self.END_INDEX]:  # noqa: E203
            if man_name in self.data:
                # 既存データにすでにあるとき, 優先データで置き換えるか単純に飛ばす
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
                logger.error(e)
                error_storage.add(e)
                continue
            except Exception:
                e = traceback.format_exc()
                error_storage.add(e)
                logger.error(e)
                file_manager.save_raw_data(self.data)
        self.crawler.close_browser()

    def save(self) -> None:
        """実行結果をファイルに保存"""
        file_manager.save_raw_data(self.data)
        file_manager.output_csv(self.data)
        logger.info("summary:")
        logger.info(f"got {len(self.data)} data correctly.")
        if error_storage.storage:
            logger.info("the following error caused.")
            for e in error_storage.storage:
                logger.info(e)
        logger.info("script finished.")
