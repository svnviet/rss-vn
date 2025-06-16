import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from base import SyncBase

MONGO_URI = "mongodb://localhost:27017/vn-news"
mongo_uri = MONGO_URI
client = MongoClient(mongo_uri)
db = client["vn-news"]  # Create or connect to a database
news_collection = db["vn-news"]
collection = db["vn-news"]  # Create or connect to a collection
collection.create_index("src_id", unique=True)
collection_detail = db["vn-nld-detail"]

vn_url = "https://nld.com.vn/"
base_url = "http://127.0.0.1:5000/"
detail_url = "http://127.0.0.1:5000/vn-vi/news/"


class SyncNLD(SyncBase):
    rss_url = vn_url + "rss.htm"
    code = "nld"
    rss_endpoint = vn_url + "rss/"

    def __init__(self):
        pass

    def get_rss_list(self):
        response = requests.get(self.rss_url)
        soup = BeautifulSoup(response.content, "html.parser")
        rss_wrap = soup.find("ul", {"class": "cate-content"})
        rss_list = [rss_data.get("href") for rss_data in rss_wrap.find_all("a")]
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
            self.insert_rss(vn_url + url)

    def insert_rss(self, rss_url=None):
        # Load RSS feed
        response = requests.get(rss_url)
        soup = BeautifulSoup(response.content, "xml")

        data = []
        src_data = []
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
                return article
            src_ids.append(src_id)
            category = self.get_category_from_url(rss_url)

            row = {
                "src_id": src_id,
                "title": title,
                "link": link,
                "image_url": image_url,
                "source_logo_url": "logo/vne_logo_rss.png",
                "source_type": "NLD",
                "description": description,
                "published": published,
                "category": category,
            }

            src_row = {
                "title": title,
                "link": link,
                "image_url": image_url,
                "source_logo_url": "logo/vne_logo_rss.png",
                "source_type": "VNExpress",
                "description": description,
                "published": published,
                "category": category,
            }
            if not row:
                continue

            data.append(row)
            src_data.append(src_row)
        try:
            if data:
                result = collection.insert_many(data, ordered=False)
                news_collection.insert_many(src_data, ordered=False)
                print(f"RSS {self.rss_url}")
                print(f"Inserted {len(result.inserted_ids)} new items.")
        except BulkWriteError as bwe:
            inserted_count = bwe.details.get("nInserted", 0)
            print(f"Inserted {inserted_count} new items. Some were skipped due to errors (likely duplicates).")

        return data


if __name__ == "__main__":
    m = SyncNLD()
    print(m.insert_rss_all())
