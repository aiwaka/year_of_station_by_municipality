import time
import os
import re
import chromedriver_binary
from logzero import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote
from urllib.request import urlopen
from bs4 import BeautifulSoup
from my_exception import NonWikipediaLink, ElementNotFound, CannotOpenURL, NoDateColumn


class Crawler:
    def open_browser(self):
        # ブラウザーを起動. すでに起動しているならなにもしない.
        if not hasattr(self, "driver"):
            options = Options()
            options.add_argument("--headless")
            options.add_argument("incognito")
            self.driver = webdriver.Chrome(options=options)

    def close_browser(self):
        # デストラクタでquitしようとするとエラーで落ちるのでこのようにしている.
        # 必ず最後にこれを呼ぶ
        if hasattr(self, "driver"):
            self.driver.quit()

    def get_wiki_link(self, man_name):
        # seleniumでchromeを操作して検索結果のリンクを取ってくる
        self.driver.get(f"https://www.google.com/search?q={quote(man_name)}+wikipedia")
        time.sleep(2)  # 待機
        # 検索結果のブロックはgクラスがつけられている.
        search_result = self.driver.find_elements_by_css_selector(".g > div > div")
        link = search_result[0].find_element_by_tag_name("a").get_attribute("href")
        return link

    def get_source(self, man_name):
        # 自治体名からwikipediaのhtmlを返す.
        # 一度ウェブから取ったら保存するようにして時間とトラフィック削減
        FILE_PATH = f"./wiki_page_html/{man_name}.html"
        if not os.path.exists(FILE_PATH):
            # ソースのhtmlが存在しなければ取ってきて保存し, あるならそれを使う.
            self.open_browser()
            link = self.get_wiki_link(man_name)
            if "ja.wikipedia.org" not in link:
                raise NonWikipediaLink(link + " [" + man_name + "]")
            logger.info(f"{man_name} : source not exists. fetching from {link}")
            self.driver.get(link)
            time.sleep(1)
            # ヘッダーがやたら長くて邪魔なので除去してからhtmlソースとする.
            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            soup.select_one("head").decompose()
            with open(FILE_PATH, mode="w") as f:
                f.write(str(soup))
            logger.info(f"saved as {man_name}.html")
        else:
            with open(FILE_PATH) as f:
                logger.info(f"{man_name} is found.")
                html = f.read()
        return html

    def get_station_links(self, man_name) -> list:
        # 自治体名からそこに属する駅のリンクのリストを持ってくる.
        # "駅名": リンクの辞書で返す.
        html = self.get_source(man_name)
        soup = BeautifulSoup(html, "html.parser")
        railroad_blocks = []
        base_tag = soup.select_one("h3:has( > span#鉄道)")
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
        pattern = re.compile(r"(駅|停留場|停留所)$")
        for block in railroad_blocks:
            link_list = block.select("li > a")
            for link in link_list:
                name = link.get_text()
                if pattern.search(name) is not None and name not in result_dict:
                    result_dict[name] = link.attrs["href"]

        return result_dict

    def get_opening_date(self, sta_name, sta_link):
        # 生成した辞書を使ってその駅が開業した年月を引っ張ってくる.
        print(sta_name + " fetching...")
        try:
            with urlopen(sta_link) as response:
                html = response.read()
                time.sleep(2.5)
        except Exception as e:
            print(e)
            raise CannotOpenURL(f"cannot open URL : {sta_link} ({sta_name})")

        soup = BeautifulSoup(html, "html.parser")
        row_tags = soup.select("th:-soup-contains('開業年月日')")
        if row_tags is []:
            raise NoDateColumn(f"at {sta_link} ({sta_name})")
        year_pattern = re.compile(r"([0-9]{4})年")
        years = [
            int(
                year_pattern.search(
                    row.find_next_sibling().get_text().replace("\n", "")
                ).groups()[0]
            )
            for row in row_tags
        ]
        return min(years)

    def get_year_data(self, man_name):
        # manicipalityの名前からスクレイピングして最も新しい駅の設置年をとってくる.
        years_data = {}

        try:
            sta_data: dict = self.get_station_links(man_name)
        except NonWikipediaLink as e:
            logger.warning(f"link is not wikipedia : {e}")
        except ElementNotFound as e:
            logger.warning(f"railroad section not found : {e}")
            sta_data = "None"

        for name, link in sta_data.items():
            try:
                years_data[name] = self.get_opening_date(
                    name, "https://ja.wikipedia.org" + link
                )
                logger.info(f"{name} : {years_data[name]}年")
            except CannotOpenURL as e:
                logger.error(f"{e}")
            except NoDateColumn as e:
                logger.error(f"{e}")

        min_year_name = min(years_data)

        return min_year_name, years_data[min_year_name]


# # resultを使ってcsv出力
# with open("result.csv", mode="w", encoding="utf-8") as f:
#     writer = csv.writer(f, lineterminator="\n")
#     writer.writerows(result)

crawler = Crawler()
