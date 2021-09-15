import re
import chromedriver_binary  # noqa: F401
from typing import Union
from time import sleep
from logzero import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote
from urllib.request import urlopen
from bs4 import BeautifulSoup
from my_exception import NonWikipediaLink, ElementNotFound, CannotOpenURL, NoDateColumn
from error_storage import error_storage
from filemanager import file_manager


def validate_man_name_and_address(man_name: str, address_list: list) -> bool:
    # （MANDARA10の）自治体名と住所が一致しているか返す
    # これで（都道府県または政令市）（市区町村または政令市区）に分けることができる.
    pattern = re.compile(r"(さいたま市|堺市|...??[都道府県市])(.+?[市区町村])")
    # （市区町村または政令市区）を取得
    partial_name = pattern.search(man_name).groups()[1]
    for address in address_list:
        # 住所のリストにその名前が入っていればOKとする.
        if partial_name in address:
            return True
    return False


class Crawler:
    def __init__(self):
        # 優先データを辞書として持っておく.
        # URLが見つけられない場合のURLや, データが誤りのときのデータなどを手動で書いておく.
        self.priority_data = file_manager.load_priority_data()
        self.address_data = file_manager.load_address_dict()

    def open_browser(self):
        # ブラウザーを起動. すでに起動しているならなにもしない.
        if not hasattr(self, "driver"):
            options = Options()
            options.add_argument("--headless")  # ヘッドレスモード
            # options.add_argument("incognito")  # シークレットモード
            self.driver = webdriver.Chrome(options=options)

    def close_browser(self):
        # デストラクタでquitしようとするとエラーで落ちるのでこのようにしている.
        # 必ず最後にこれを呼ぶ
        if hasattr(self, "driver"):
            self.driver.quit()

    def get_wiki_link(self, man_name):
        # seleniumでchromeを操作して検索結果のリンクを取ってくる
        # 与えられた自治体名 + wikipediaで検索する.
        self.driver.get(f"https://www.google.com/search?q={quote(man_name)}+wikipedia")
        sleep(2)  # 待機
        # 検索結果のブロックはgクラスがつけられている.
        search_result = self.driver.find_elements_by_css_selector(".g > div > div")
        link = search_result[0].find_element_by_tag_name("a").get_attribute("href")
        return link

    def source_formatting(self, html) -> str:
        # 自治体のhtmlソースから, 交通以外のh2タグと, ヘッダーを除いたものを返す.
        soup = BeautifulSoup(html, "html.parser")
        soup.select_one("head").decompose()
        content_elem = soup.select_one("div#content")  # idがcontentのタグ
        # 兄弟要素を全て潰す
        for elem in content_elem.find_previous_siblings():
            elem.decompose()
        for elem in content_elem.find_next_siblings():
            elem.decompose()
        # idが交通のspanを子要素に持つh2タグ
        # traffic_elem = soup.select_one("h2:has( > span#交通),h2:has( > span#交通機関)")
        traffic_elem = soup.select_one("h2:has( > span[id*='交通'])")
        # 前の兄弟要素を全て潰す
        for elem in traffic_elem.find_previous_siblings():
            elem.decompose()
        # 次のh2タグをみつけ, それ以降をすべて潰す
        next_tag = traffic_elem.find_next_sibling()
        while next_tag is not None and next_tag.name != "h2":
            next_tag = next_tag.find_next_sibling()
        if next_tag is not None:
            for elem in next_tag.find_next_siblings():
                elem.decompose()
            next_tag.decompose()
        # 空行を消す. 改行で分割し, stripで空白文字を消して空白になるものを空行と判断する.
        result_html = "\n".join(
            filter(lambda line: line.strip(), str(soup).split("\n"))
        )
        return result_html

    def get_source(self, man_name):
        # 自治体名からwikipediaのhtmlを返す.
        # 一度ウェブから取ったら保存するようにして時間とトラフィック削減
        html = file_manager.load_local_html(man_name)
        if html is None:
            # ソースのhtmlが存在しなければ取ってきて保存し, あるならそれを使う.
            self.open_browser()
            link = self.get_wiki_link(man_name)
            if "ja.wikipedia.org" not in link:
                # wikipediaのサイトではなかったら, 優先データを見に行く.
                # エラーを見つけたら手動で優先データに追加しておく.
                if self.priority_data.get(man_name, {}).get("url", None):
                    link = self.priority_data[man_name]["url"]
                else:
                    # それでもみつからなかったら例外を送る
                    raise NonWikipediaLink(
                        "link is not wikipedia : " + link + " [" + man_name + "]"
                    )
            logger.info(f"{man_name} : source not exists. fetching from {link}")
            self.driver.get(link)
            sleep(1)
            # ヘッダーなどが長くて邪魔なので交通以外の項やヘッダーを除去してからhtmlソースとする.
            html = self.source_formatting(self.driver.page_source)
            file_manager.save_local_html(man_name, html)
            logger.info(f"saved as {man_name}.html")
        else:
            logger.info(f"{man_name} is found.")
        return html

    def get_station_links(self, man_name) -> dict:
        # 自治体名からそこに属する駅のリンクのリストを持ってくる.
        # {"駅名": "リンク"}の辞書で返す.
        html = self.get_source(man_name)
        soup = BeautifulSoup(html, "html.parser")

        # 鉄道やBRTなどのh3項目を取得する.
        railroad_blocks = []
        RAILWAY_TAG_ID = ["鉄道", "鉄道路線", "鉄道・索道", "BRT", "鉄道と駅"]
        # base_tags = soup.select(
        #     "h3:has( > span#鉄道),h3:has(> span#鉄道路線),"
        #     "h3:has( > span#鉄道・索道),h3:has( > span#BRT)"
        # )
        base_tags = soup.select(
            ",".join(map(lambda text: f"h3:has( > span#{text})", RAILWAY_TAG_ID))
        )
        if base_tags is None:
            raise ElementNotFound(f"railroad section not found : {man_name}")
        for base_tag in base_tags:
            next_tag = base_tag.find_next_sibling()
            # 鉄道が書いてあるh3から次のh3までの間のタグを保存する.
            # ただしclassにgalleryを含むものは不要なので取り除きたい.
            while next_tag is not None and next_tag.name != "h3":
                if (
                    "class" not in next_tag.attrs
                    or "gallery" not in next_tag.attrs["class"]
                ):
                    railroad_blocks.append(next_tag)
                next_tag = next_tag.find_next_sibling()

        # 「廃線」や「廃止された鉄道」などがあるなら警告として出しておく.
        warning_text = None
        ABANDONED_TEXT = [
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
        # "#廃線,#廃止路線,#廃止された鉄道路線,#廃線となった路線,#廃止された鉄道,#かつてあった路線,#かつて存在した鉄道路線"
        # まずidから探す. セレクタを作り, 一つでもあればOK.
        abandoned_line = soup.select_one(
            ",".join(map(lambda text: "#" + text, ABANDONED_TEXT))
        )
        if abandoned_line:
            warning_text = (
                f"abandoned line may exist : {abandoned_line.attrs['id']} : {man_name}"
            )
        else:
            # なければ個別にテキスト検索する.
            # 鉄道の記述箇所を順番に検索
            for block in railroad_blocks:
                # まずそれらしいテキストで検索.
                for text in ABANDONED_TEXT:
                    abandoned_line = block.select_one(f"*:-soup-contains('{text}')")
                    if abandoned_line:
                        warning_text = f"abandoned line may exist : {text} : {man_name}"
                        break
                if warning_text:
                    break
                else:
                    # まだなければ「かつては」で検索
                    abandoned_line = block.select_one("p:-soup-contains('かつては')")
                    if abandoned_line:
                        warning_text = (
                            f"abandoned line may exist : かつては... : {man_name}"
                        )
                        break
        if warning_text:
            logger.warning(warning_text)
            error_storage.add(warning_text)

        result_dict = {}
        pattern = re.compile(r"(?<!旅客|鉄道|休止|臨時|請願)(駅|停留場)$")
        # 取ってきたタグの中で駅や停留所を探して順番に検査する.
        for block in railroad_blocks:
            # li > b > a,p > b > aとしていたのを修正.
            link_list = block.select("li a,b > a,dd a")
            if link_list == []:
                continue
                # raise ElementNotFound(man_name + " (<li> or <a> tag not found)")
            for link in link_list:
                name = link.get_text()
                if pattern.search(name) is not None and name != "駅":
                    # 辞書に保存する形なので重複は排除される.
                    result_dict[name] = link.attrs["href"]

        if not result_dict:
            raise ElementNotFound(f"railroad section not found : {man_name}")
        return result_dict

    def get_station_html(self, sta_name, sta_link):
        # 駅のリンク先htmlを返す.
        try:
            with urlopen(sta_link) as response:
                html = response.read()
                sleep(3)
        except Exception as e:
            print(e)
            raise CannotOpenURL(f"cannot open URL : {sta_link} ({sta_name})")
        return html

    def get_address_list(self, sta_name, html) -> list:
        # 駅の住所（の一部）を持ってくる. 複数あることも考えてリストで返す.
        # 住所録に名前があるならそれを返せば良い.
        if sta_name[:-1] in self.address_data:
            # 全駅データの辞書には「駅」を省いた名前が書いてあるのでそれに対応して一文字消す
            result = self.address_data[sta_name[:-1]]
        else:
        # ないならhtmlから抽出する.
        soup = BeautifulSoup(html, "html.parser")
        row_tags = soup.select("th:-soup-contains('所在地')")
        result = []
        for row in row_tags:
            # 所在地タグの隣のタグのテキストを取得し, とりあえずいらない文字を省く
            text = re.sub("[\n\ufeff/]", "", row.find_next_sibling().get_text())
            # 空白で分けた最初の部分を取得すれば住所の主要部分はまず取得できる.
            result.append(text.split(" ")[0])
        # 取得した住所の大きいケはすべて小文字にしておく.
        # 日本市町村人口.csvの自治体名は全て小文字なのでこれで統一される.
        return [text.replace("ケ", "ヶ") for text in result]

    def get_opening_date(self, man_name, sta_name, sta_link) -> Union[int, None]:
        html = self.get_station_html(sta_name, sta_link)
        address_list = self.get_address_list(sta_name, html)
        if not address_list:
            raise NoDateColumn(f"cannot find address data : {sta_name}")
        # 住所がおかしいならNoneを返す.
        if not validate_man_name_and_address(man_name, address_list):
            validation_failed_message = (
                f"address validation failed : "
                f"{sta_name} : {man_name}? {str(address_list)} "
                "are correct by data."
            )
            logger.warning(validation_failed_message)
            error_storage.add(validation_failed_message)
            return None
        # 生成した辞書を使ってその駅が開業した年月を引っ張ってくる.
        soup = BeautifulSoup(html, "html.parser")
        # 開業年月日というテキストを持つthタグの隣のタグを持ってくる.
        row_tags = soup.select("th:-soup-contains('開業年月日')")
        # そのような部分がない場合は例外を投げる
        if not row_tags:
            raise NoDateColumn(f"at {sta_link} ({sta_name})")
        # 正規表現で年を抜き出して整数にしてリストに格納
        year_pattern = re.compile(r"([0-9]{4})年")
        years = [
            int(
                year_pattern.search(
                    row.find_next_sibling().get_text().replace("\n", "")
                ).groups()[0]
            )
            for row in row_tags
        ]
        # 最大の数字を返す.
        # ->ここは最小にしておく（最近wikiページでの別枠ができることは少ないだろうので）
        # 最後でも空の場合例外を送出
        if not years:
            raise NoDateColumn(f"at {sta_link} ({sta_name})")
        return min(years)

    def get_year_data(self, man_name, force=False):
        # manicipalityの名前からスクレイピングして最も古い・新しい駅の設置年をとってくる.
        # forceがTrueだと優先データを読み込むことをしない.
        if not force and man_name in self.priority_data:
            # 強制モードでなく優先データに指定された名前があるならそれを返して終わりにする.
            if self.priority_data[man_name].get("nodata", False):
                # nodata属性がTrueなら決められたデータを返す.
                return {"sta_data": [], "max": ["なし", 0], "min": ["なし", 0]}
            elif self.priority_data[man_name].get("data", None):
                # 優先データが指定されているならそれを返す.
                # ただし, クロールの段階では全部のデータが揃っていないと不可とする.
                pri_data = self.priority_data[man_name]["data"]
                pri_sta_data = pri_data.get("sta_data", None)
                pri_max_data = pri_data.get("max", None)
                pri_min_data = pri_data.get("min", None)
                if pri_sta_data and pri_max_data and pri_min_data:
                    return self.priority_data[man_name]["data"]
                else:
                    logger.warning(
                        f"{man_name} : "
                        "priority data exists, "
                        "but not all attrs are available."
                    )

        years_data = {}
        # wikiに載っている駅データをとりあえずすべて取得
        # 例外はcollector側で補足される.
        sta_data: dict = self.get_station_links(man_name)

        for sta_name, sta_link in sta_data.items():
            try:
                # 自治体名と駅ページの住所が合っていなければNoneが返ってくる.
                sta_year = self.get_opening_date(
                    man_name, sta_name, "https://ja.wikipedia.org" + sta_link
                )
                # ちゃんとデータが返ってきているなら名前リストに追加し, 辞書に登録
                if sta_year:
                    years_data[sta_name] = sta_year
                    print(f"{sta_name} : {years_data[sta_name]}年")
                else:
                    pass
                    # logger.warning(f"{sta_name} is not in {man_name}")
                    # error_storage.add(f"{sta_name} is not in {man_name}")
            except CannotOpenURL as e:
                logger.error(f"cannot open url : {e}")
            except NoDateColumn as e:
                logger.error(f"no date column in webpage : {e}")

        if not years_data:
            raise ElementNotFound(f"railroad section not found : {man_name}")
        # max, minに辞書を入れるとキーが比較されるが,
        # キーを引数として呼び出せるメソッドをkeyに指定するとそれで比較してくれる.
        max_year_name = max(years_data, key=years_data.get)
        min_year_name = min(years_data, key=years_data.get)

        return {
            "sta_data": list(years_data.keys()),
            "max": [max_year_name, years_data[max_year_name]],
            "min": [min_year_name, years_data[min_year_name]],
        }
