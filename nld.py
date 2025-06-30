import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from .base import SyncBase
import urllib3

# Suppress only InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MONGO_URI = "mongodb://localhost:27017/vn-news"
mongo_uri = MONGO_URI
client = MongoClient(mongo_uri)
db = client["vn-news"]  # Create or connect to a database
collection = db["vn-news"]  # Create or connect to a collection
collection.create_index("src_id", unique=True)
collection_detail = db["vn-nld-detail"]
collection_detail.create_index("src_id", unique=True)

vn_url = "https://nld.com.vn/"
base_url = "http://127.0.0.1:5000/"
detail_url = "http://127.0.0.1:5000/vn-vi/news/"


class SyncNLD(SyncBase):
    code = "nld"
    rss_endpoint = vn_url + "rss/"

    def __init__(self, local_url=base_url):
        self.rss_url = vn_url + "rss.htm"
        super().__init__(self.rss_url, local_url)

    def get_rss_list(self):
        response = requests.get(self.rss_url, verify=False)
        soup = BeautifulSoup(response.content, "html.parser")
        rss_wrap = soup.find("ul", {"class": "cate-content"})
        rss_list = []
        for rss_data in rss_wrap.find_all("a"):
            rss_url = rss_data.get("href")
            if "home.rss" in rss_url:
                continue
            rss_list.append(rss_data.get("href"))
        return rss_list

    def get_id_from_url(self, link):
        dt = f"{self.code}-" + link.split("-")[-1]
        return dt.replace(".htm", "")

    def get_detail_url(self, url):
        pass

    def get_category_from_url(self, link):
        dt = link.split("/")[-1]
        return dt.replace(".rss", "")

    def insert_rss_all(self):
        for url in self.get_rss_list():
            if vn_url in url:
                self.insert_rss(url)
            else:
                self.insert_rss(vn_url + url)

    def insert_rss(self, rss_url=None):
        # Load RSS feed
        response = requests.get(rss_url, verify=False)
        soup = BeautifulSoup(response.content, "xml")

        data = []
        src_ids = []
        for idx, item in enumerate(soup.find_all("item")):
            title = item.title.text
            link = item.link.text.replace(vn_url, "")
            description = item.description.text
            published = item.pubDate.text

            # Extract image URL from description using BeautifulSoup again (HTML inside CDATA)
            desc_soup = BeautifulSoup(description, "html.parser")
            img_tag = desc_soup.find("img")
            image_url = img_tag["src"] if img_tag else None
            src_id = self.get_id_from_url(link)
            article = collection_detail.find_one({"src_id": src_id})
            if article:
                if article.get("type", None) in self.news_errors:
                    raise Exception("News errors")
                return article
            src_ids.append(src_id)
            category = self.get_category_from_url(rss_url)

            row = {
                "src_id": src_id,
                "title": title,
                "link": link,
                "image_url": image_url,
                "source_logo_url": "logo/nld_logo_rss.png",
                "source_type": "NLD",
                "description": description,
                "published": published,
                "category": category,
            }

            if not row:
                continue

            data.append(row)
        try:
            if data:
                result = collection.insert_many(data, ordered=False)
                print(f"RSS {self.rss_url}")
                print(f"Inserted {len(result.inserted_ids)} new items.")
        except BulkWriteError as bwe:
            inserted_count = bwe.details.get("nInserted", 0)
            print(f"Inserted {inserted_count} new items. Some were skipped due to errors (likely duplicates).")

        return data

    def insert_or_get_detail(self, link, ads=False):

        print(link)
        resp = requests.get(link, verify=False)
        soup = BeautifulSoup(resp.text, 'html.parser')
        src_id = self.get_id_from_url(link)
        article = collection_detail.find_one({"src_id": src_id})
        print(src_id)
        if article:
            return article

        if soup.find("a", class_="detail-category"):
            ads = True

        if ads:
            collection.update_one({"src_id": src_id}, {"$set": {"type": "ads"}})
            raise Exception("News Error!")

        header_video_div = soup.find("div", class_="header__video")
        if header_video_div:
            collection.update_one({"src_id": src_id}, {"$set": {"type": "video"}})
            raise Exception("News Error!")

        podcast_player = soup.find("div", class_="player-funcs")
        if podcast_player:
            collection.update_one({"src_id": src_id}, {"$set": {"type": "podcast"}})
            raise Exception("News Error!")

        try:
            title = soup.find("h1").get_text(strip=True)
        except AttributeError:
            collection.update_one({"src_id": src_id}, {"$set": {"type": "removed"}})
            raise Exception("News Error!")

        content = soup.find("div", class_="detail__cmain-main")
        category = soup.find("div", class_="detail-cate")
        author = content.find("div", class_="detail-author")
        if author:
            author = author.get_text(strip=True)
        else:
            author = "NLĐO" + " " + category.get_text()

        description = soup.select_one("h2.detail-sapo")
        content_html = content.find("div", class_="detail-cmain")
        published_at = content.find("div", class_="detail-time").get_text(strip=True)

        data = {
            "src_id": src_id,
            "title": title,
            "author": author,
            "description": str(description),
            "content": str(content_html),
            "published_at": published_at,
            "article_url": link,
            "source_logo_url": "logo/nld_logo_rss.png"
        }

        try:
            if data:
                print(data)
                result = collection_detail.insert_one(data)
                print(f"Inserted id{(result.inserted_id)} new items.")
                return collection_detail.find_one({"src_id": src_id})
        except BulkWriteError as bwe:
            inserted_count = bwe.details.get("nInserted", 0)
            print(f"Inserted error {inserted_count} new item.")


if __name__ == "__main__":
    m = SyncNLD()
    m.insert_rss_all()
    # records = collection.find({"source_type": "NLD"})
    # link = "https://nld.com.vn/hai-nguoi-dan-bac-lieu-trung-10-to-ve-so-giai-doc-dac-196250611131143485.htm"
    # m.insert_or_get_detail(link)
    # for record in records:
    #     link = record["link"]
    #     if "https://" in link:
    #         m.insert_or_get_detail(link, True)
    #     else:
    #         m.insert_or_get_detail(vn_url + link)
