import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

MONGO_URI = "mongodb://localhost:27017/vn-news"
mongo_uri = MONGO_URI
client = MongoClient(mongo_uri)
db = client["vn-news"]  # Create or connect to a database
news_collection = db["vn-news"]
collection = db["vn-nld"]  # Create or connect to a collection
collection.create_index("src_id", unique=True)
collection_detail = db["vn-nld-detail"]

vn_url = "https://nld.com.vn/"
base_url = "http://127.0.0.1:5000/"
detail_url = "http://127.0.0.1:5000/vn-vi/news/"
