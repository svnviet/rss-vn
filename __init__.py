import logging
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = "mongodb://localhost:27017/vn-news"
vn_url = "https://vnexpress.net/"
base_url = "http://127.0.0.1:5000/"
detail_url = "http://127.0.0.1:5000/vn-vi/news/"
