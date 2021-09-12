import re
from time import sleep
import chromedriver_binary  # noqa: F401
from logzero import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote
from urllib.request import urlopen
from bs4 import BeautifulSoup
from my_exception import NonWikipediaLink, ElementNotFound, CannotOpenURL, NoDateColumn
from filemanager import DataFilesIO


class Crawler:
    def __init__(self, file_manager: DataFilesIO):
        self.file_manager = file_manager
        # 優先データを辞書として持っておく.
        # URLが見つけられない場合のURLや, データが誤りのときのデータなどを手動で書いておく.
        self.priority_data = file_manager.load_priority_data()

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
        traffic_elem = soup.select_one("h2:has( > span#交通)")
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
        return str(soup)

    def get_source(self, man_name):
        # 自治体名からwikipediaのhtmlを返す.
        # 一度ウェブから取ったら保存するようにして時間とトラフィック削減
        FILE_PATH = f"./wiki_page_html/{man_name}.html"

        html = self.file_manager.load_local_html(FILE_PATH)
        if html is None:
            # ソースのhtmlが存在しなければ取ってきて保存し, あるならそれを使う.
            self.open_browser()
            link = self.get_wiki_link(man_name)
            if "ja.wikipedia.org" not in link:
                # wikipediaのサイトではなかったら, 優先データを見に行く.
                # エラーを見つけたら手動で追加する.
                if self.priority_data.get(man_name, {}).get("url", None):
                    link = self.priority_data[man_name]["url"]
                else:
                    # それでもみつからなかったら例外を送る
                    raise NonWikipediaLink(link + " [" + man_name + "]")
            logger.info(f"{man_name} : source not exists. fetching from {link}")
            self.driver.get(link)
            sleep(1)
            # ヘッダーなどが長くて邪魔なので交通以外の項やヘッダーを除去してからhtmlソースとする.
            html = self.driver.page_source
            with open(FILE_PATH, mode="w") as f:
                f.write(self.source_formatting(html))
            logger.info(f"saved as {man_name}.html")
        else:
            logger.info(f"{man_name} is found.")
        return html

    def get_station_links(self, man_name) -> list:
        # 自治体名からそこに属する駅のリンクのリストを持ってくる.
        # "駅名": リンクの辞書で返す.
        html = self.get_source(man_name)
        soup = BeautifulSoup(html, "html.parser")
        railroad_blocks = []
        base_tag = soup.select_one("h3:has( > span#鉄道),h3:has(> span#鉄道路線)")
        if base_tag is None:
            raise ElementNotFound(man_name)
        next_tag = base_tag.find_next_sibling()
        # 鉄道が書いてあるh3から次のh3までの間のタグを保存する.
        # ただしclassにgalleryを含むものは不要なので取り除きたい.
        while next_tag.name != "h3":
            if (
                "class" not in next_tag.attrs
                or "gallery" not in next_tag.attrs["class"]
            ):
                railroad_blocks.append(next_tag)
            next_tag = next_tag.find_next_sibling()

        result_dict = {}
        pattern = re.compile(r"(?<!臨時|請願)(駅|停留場)$")
        # 取ってきたタグの中で駅や停留所を探して順番に検査する.
        for block in railroad_blocks:
            link_list = block.select("li > a,li > b > a")
            if link_list is []:
                raise ElementNotFound(man_name + " (<li> or <a> tag not found)")
            for link in link_list:
                name = link.get_text()
                if pattern.search(name) is not None and name not in result_dict:
                    # 辞書に保存する形なので重複は排除される.
                    result_dict[name] = link.attrs["href"]

        if not result_dict:
            raise ElementNotFound(man_name)
        return result_dict

    def get_opening_date(self, sta_name, sta_link):
        # 生成した辞書を使ってその駅が開業した年月を引っ張ってくる.
        # URLを開く
        try:
            with urlopen(sta_link) as response:
                html = response.read()
                sleep(3)
        except Exception as e:
            print(e)
            raise CannotOpenURL(f"cannot open URL : {sta_link} ({sta_name})")

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
        if force:
            logger.info(f"{man_name} : force mode")
        # manicipalityの名前からスクレイピングして最も新しい駅の設置年をとってくる.
        # forceがTrueだと優先データを読み込むことをしない.
        years_data = {}

        try:
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
            sta_data: dict = self.get_station_links(man_name)
        except NonWikipediaLink as e:
            raise NonWikipediaLink(f"link is not wikipedia : {e}")
        except ElementNotFound as e:
            raise ElementNotFound(f"railroad section not found : {e}")

        for name, link in sta_data.items():
            try:
                years_data[name] = self.get_opening_date(
                    name, "https://ja.wikipedia.org" + link
                )
                # logger.info(f"{name} : {years_data[name]}年")
            except CannotOpenURL as e:
                logger.error(f"cannot open url : {e}")
            except NoDateColumn as e:
                logger.error(f"no date column in webpage : {e}")

        max_year_name = max(years_data, key=years_data.get)
        min_year_name = min(years_data, key=years_data.get)

        return {
            "sta_data": list(sta_data.keys()),
            "max": [max_year_name, years_data[max_year_name]],
            "min": [min_year_name, years_data[min_year_name]],
        }
