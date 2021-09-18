import re
import chromedriver_binary  # noqa: F401
from bs4.element import Tag
from typing import Any, Dict, List, Union
from time import sleep
from logzero import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote
from urllib.request import urlopen
from bs4 import BeautifulSoup
from appexcp.my_exception import (
    NonWikipediaLink,
    CannotOpenURL,
    # NoDateColumn,
)

# from error_storage import error_storage
from filemanager import file_manager


class Crawler:
    def __init__(self) -> None:
        # 優先データを辞書として持っておく.
        # URLが見つけられない場合のURLや, データが誤りのときのデータなどを手動で書いておく.
        self.priority_data: Dict[str, Any] = file_manager.load_priority_data()

    def open_browser(self) -> None:
        """ブラウザーを起動. すでに起動しているならなにもしない."""
        if not hasattr(self, "driver"):
            options = Options()
            options.add_argument("--headless")  # ヘッドレスモード
            # options.add_argument("incognito")  # シークレットモード
            self.driver = webdriver.Chrome(options=options)

    def close_browser(self) -> None:
        """ブラウザを開いているなら閉じる.

        デストラクタでquitしようとするとエラーで落ちるのでこのようにしている. 必ず最後にこれを呼ぶ.
        """
        if hasattr(self, "driver"):
            self.driver.quit()

    def get_wiki_link(self, man_name: str) -> str:
        """wikipediaのリンクを取得.

        seleniumでchromeを操作して自治体名から検索結果のリンクを取ってくる.
        与えられた自治体名 + wikipediaで検索する.
        エラーを見つけたら手動で優先データに追加しておくこと.

        Args:
            man_name (str): 自治体名.

        Returns:
            str: リンクを文字列で返す.

        Raises:
            NonWikipediaLink: 取得したリンクがWikipediaのものでない場合に発生.
        """
        self.open_browser()
        if self.priority_data.get(man_name, {}).get("url", None):
            link: str = self.priority_data[man_name]["url"]
            return link
        self.driver.get(f"https://www.google.com/search?q={quote(man_name)}+wikipedia")
        sleep(2)  # 待機
        # 検索結果のブロックはgクラスがつけられている.
        search_result = self.driver.find_elements_by_css_selector(".g > div > div")
        link: str = search_result[0].find_element_by_tag_name("a").get_attribute("href")
        if "ja.wikipedia.org" not in link:
            # wikipediaのサイトではなかったら例外を送る
            # raise NonWikipediaLink(
            #     "link is not wikipedia : " + link + " [" + man_name + "]"
            # )
            raise NonWikipediaLink(man_name, link)
        return link

    def source_formatting(self, html: str) -> str:
        """htmlを整形.

        与えられたhtmlの交通に関する部分以外をできるだけ潰して容量を削減する.
        具体的には交通以外のh2タグとヘッダーを除いたものを返す.

        Args:
            html (str): htmlソース.

        Returns:
            str: 整形済みhtmlソース.
        """
        soup = BeautifulSoup(html, "html.parser")
        # soup.select_one("head").decompose()
        if head_elem := soup.select_one("head"):
            head_elem.decompose()
        if content_elem := soup.select_one("div#content"):  # idがcontentのタグ
            # 兄弟要素を全て潰す
            for elem in content_elem.find_previous_siblings():
                elem.replace_with("")
            for elem in content_elem.find_next_siblings():
                elem.replace_with("")

        if traffic_elem := soup.select_one("h2:has( > span[id*='交通'])"):
            # 前の兄弟要素を全て潰す
            for elem in traffic_elem.find_previous_siblings():
                elem.replace_with("")
            # 次のh2タグをみつけ, それ以降をすべて潰す
            next_tag = traffic_elem.find_next_sibling()
            while next_tag is not None and next_tag.name != "h2":
                next_tag = next_tag.find_next_sibling()
            if next_tag is not None:
                for elem in next_tag.find_next_siblings():
                    elem.replace_with("")
                next_tag.replace_with("")
        # 空行を消す. 改行で分割し, stripで空白文字を消して空白になるものを空行と判断する.
        result_html = "\n".join(
            filter(lambda line: line.strip(), str(soup).split("\n"))
        )
        return result_html

    def get_source(self, man_name: str) -> str:
        """自治体のhtmlソースを取得.

        自治体名からwikipediaのhtmlを返す.
        一度ウェブから取ったら保存するようにして時間とトラフィック削減する.

        Args:
            man_name (str): 自治体名.

        Returns:
            str: htmlソース（整形済み）.
        """
        html = file_manager.load_local_html(man_name)
        # ソースのhtmlが存在しなければ取ってきて保存し, あるならそれを使う.
        if html is None:
            link = self.get_wiki_link(man_name)
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

    def get_station_html(self, sta_name: str, sta_link: str) -> str:
        """駅のリンク先のhtmlを返す.

        駅名とリンクを入力し, リンク先のhtmlを正しく取得する. 取得に成功したら適当な秒数待つ.

        Args:
            sta_name (str): 駅名. ログ表示にしか使っていないので必要ないかもしれない...
            sta_link (str): 駅のリンク. 特にチェックはしないので正しいリンクを入れる必要がある.

        Returns:
            str: htmlソースを返す.

        Raises:
            CannotOpenURL: 入力されたリンクが開けない, またはエラーが発生した場合に発生.
        """
        # 駅のリンク先htmlを返す.
        try:
            with urlopen(sta_link) as response:
                html: str = response.read()
                sleep(2.8)
        except Exception as e:
            print(e)
            raise CannotOpenURL(f"cannot open URL : {sta_link} ({sta_name})")
        return html

    def get_address_list(
        self, sta_name: str, address_dict: Dict[str, List[str]], soup: BeautifulSoup
    ) -> List[str]:
        """駅に対する所在地リストを取得

        整形された所在地リストを返す. 住所録に自治体名があるならそのデータも追加する.

        Args:
            sta_name (str): 駅名.
            address_dict (Dict[str, List[str]]): 住所録. wikiに加えてこのデータを付加する.
            soup (BeautifulSoup): オブジェクトを渡す. これを使って所在地を取得.

        Returns:
            List[str]: 所在地リスト. 含まれる"ケ"の字はすべて小文字に置き換えられている.
        """
        result: List[str] = []
        # 全駅データの辞書には「駅」を省いた名前が書いてあるのでそれに対応して一文字消す
        result.extend(address_dict.get(sta_name[:-1], []))
        address_header_tag_list = soup.select("th:-soup-contains('所在地')")
        for address_header_tag in address_header_tag_list:
            # 所在地タグの隣のタグのテキストを取得し, とりあえずいらない文字を省く
            if type(address_elem := address_header_tag.find_next_sibling()) is Tag:
                text = re.sub("[\n\ufeff/]", "", address_elem.get_text())
                # 空白で分けた最初の部分を取得すれば住所の主要部分はまず取得できる.
                result.append(text.split(" ")[0])
        # 取得した住所の大きいケはすべて小文字にしておく.
        # 日本市町村人口.csvの自治体名は全て小文字なのでこれで統一される.
        return [text.replace("ケ", "ヶ") for text in result]

    def get_opening_date(
        self,
        soup: BeautifulSoup,
    ) -> Union[int, None]:
        """開業年を返す.

        渡されたhtmlオブジェクトから開業年を取得して返す. 取得できない場合は例外は出さずNoneを返す.
        複数取得できる場合は最古のものを返す.

        Args:
            soup (BeautifulSoup): オブジェクトを渡す. これを使って開業年を取得.

        Returns:
            int | None: 整数で開業年, またはNone.
        """
        # 開業年月日というテキストを持つthタグの隣のタグを持ってくる.
        date_header_tag_list = soup.select("th:-soup-contains('開業年月日')")
        # そのような部分がない場合はNoneを返す.
        if not date_header_tag_list:
            return None
        # 正規表現で年を抜き出して整数にしてリストに格納
        year_pattern = re.compile(r"([0-9]{4})年")
        years: List[int] = []
        for row in date_header_tag_list:
            if type(date_elem := row.find_next_sibling()) is Tag:
                if year_matched := year_pattern.search(
                    date_elem.get_text().replace("\n", "")
                ):
                    years.append(int(year_matched.groups()[0]))
        # 最大の数字を返す.
        # ->ここは最小にしておく（最近wikiページでの別枠ができることは少ないだろうので）
        # 最後でも空の場合例外を送出
        if not years:
            return None
        return min(years)
