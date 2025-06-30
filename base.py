from abc import abstractmethod
from pymongo import MongoClient


class SyncBase:
    """
    This base class for crawling data from rss - interaction with database and other services rss
    """

    MONGO_URI = "mongodb://localhost:27017/vn-news"
    mongo_uri = MONGO_URI
    client = MongoClient(mongo_uri)
    db = client["vn-news"]  # Create or connect to a database
    news_collection = db["vn-news"]
    news_errors = ["ads", "removed", "podcast", "video"]
    source_types = ["VNExpress", "NLD"]

    def __init__(self, rss_url, local_url):
        self.rss_url = rss_url
        self.local_url = local_url

    @abstractmethod
    def get_rss_list(self):
        pass

    @abstractmethod
    def insert_rss(self):
        pass
