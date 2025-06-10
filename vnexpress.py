import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

MONGO_URI = "mongodb://localhost:27017/vn-news"
mongo_uri = MONGO_URI
client = MongoClient(mongo_uri)
db = client["vn-news"]  # Create or connect to a database
news_collection = db["vn-news"]
collection = db["vn-express"]  # Create or connect to a collection
collection.create_index("src_id", unique=True)
collection_detail = db["vn-express-detail"]

vn_url = "https://vnexpress.net/"
base_url = "http://127.0.0.1:5000/"
detail_url = "http://127.0.0.1:5000/vn-vi/news/"


def get_rss_list():
    response = requests.get(vn_url + "rss")
    soup = BeautifulSoup(response.content, "html.parser")
    rss_wrap = soup.find("div", {"class": "wrap-list-rss"})
    rss_list = [rss_data.get("href") for rss_data in rss_wrap.find_all("a")]
    return rss_list


def get_id_from_url(link):
    dt = link.split("-")[-1]
    return dt.replace(".html", "")


def get_category_from_url(link):
    dt = link.split("/")[-1]
    return dt.replace(".rss", "")


def insert_rss(rss_url, src_ids=[]):
    # Load RSS feed
    response = requests.get(rss_url)
    soup = BeautifulSoup(response.content, "xml")

    data = []
    src_data = []
    for idx, item in enumerate(soup.find_all("item")):
        title = item.title.text
        link = item.link.text.replace(vn_url, "")
        description = item.description.text
        published = item.pubDate.text

        # Extract image URL from description using BeautifulSoup again (HTML inside CDATA)
        desc_soup = BeautifulSoup(description, "html.parser")
        img_tag = desc_soup.find("img")
        image_url = img_tag["src"] if img_tag else None
        src_id = get_id_from_url(link)
        if src_id in src_ids:
            continue

        article = collection_detail.find_one({"src_id": src_id})
        if article:
            return article
        src_ids.append(src_id)
        category = get_category_from_url(rss_url)

        row = {
            "src_id": src_id,
            "title": title,
            "link": link,
            "image_url": image_url,
            "source_logo_url": "logo/vne_logo_rss.png",
            "source_type": "VNExpress",
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
            print(f"RSS {rss_url}")
            print(f"Inserted {len(result.inserted_ids)} new items.")
    except BulkWriteError as bwe:
        inserted_count = bwe.details.get("nInserted", 0)
        print(f"Inserted {inserted_count} new items. Some were skipped due to errors (likely duplicates).")

    return data


def save_get_bs(content, attribute):
    try:
        return content.get(attribute)
    except AttributeError:
        return ""


def make_picture(soup, tag):
    # Create <figure>
    figure = soup.new_tag('figure', attrs={
        'data-size': 'true',
        'itemprop': 'associatedMedia image',
        'itemscope': '',
        'itemtype': 'http://schema.org/ImageObject',
        'class': 'tplCaption action_thumb_added'
    })

    meta_image_url = tag.find('meta', itemprop='url')
    meta_width = tag.find('meta', itemprop='width')
    meta_height = tag.find('meta', itemprop='height')
    meta_caption = tag.find('figcaption', itemprop='description')
    image_url = meta_image_url['content'].replace("amp;", "") if meta_image_url else ""
    width = meta_width['content'] if meta_height else 0
    height = meta_height['content'] if meta_width else 0
    caption = meta_caption.text if meta_caption else ""

    # Add <meta> tags
    for prop, val in [
        ('url', image_url),
        ('width', width),
        ('height', height),
        ('href', '')
    ]:
        meta = soup.new_tag('meta', itemprop=prop, content=val)
        figure.append(meta)

    # fig-picture
    fig_div = tag.find('div', class_='fig-picture')
    fig_picture = soup.new_tag('div', attrs={
        'class': 'fig-picture el_valid',
        'style': save_get_bs(fig_div, 'style'),
        'data-src': image_url,
        'data-sub-html': f'<div class="ss-wrapper"><div class="ss-content"><p class="Image">{caption}</p></div></div>'
    })

    # <picture> with <source> and <img>
    picture = soup.new_tag('picture')
    source = soup.new_tag('source', attrs={
        'data-srcset': f'{image_url} 1x'
    })
    fig_img_src = fig_div.find('img', itemprop="contentUrl")
    intrinsicsize = fig_img_src['intrinsicsize']
    fig_img_style = fig_img_src['style']

    img = soup.new_tag('img', attrs={
        'itemprop': 'contentUrl',
        'src': image_url,
        'alt': caption,
        'class': 'lazy lazied',
        'loading': 'lazy',
        'intrinsicsize': intrinsicsize,
        'style': fig_img_style,
    })
    picture.append(source)
    picture.append(img)
    fig_picture.append(picture)
    figure.append(fig_picture)

    # figcaption
    figcaption = soup.new_tag('figcaption', itemprop='description')
    p_caption = soup.new_tag('p', attrs={'class': 'Image'})
    p_caption.string = caption
    figcaption.append(p_caption)
    figure.append(figcaption)

    return figure


def insert_or_get_detail(link):
    resp = requests.get(link)
    soup = BeautifulSoup(resp.text, 'html.parser')

    title = soup.find("h1").get_text(strip=True)
    article_end = soup.find('span', id='article-end')
    if article_end is None:
        author = None
    else:
        p_tag = article_end.find_previous_sibling('p')
        author = p_tag.decode_contents() if p_tag else None

    description = soup.find("p", class_="description")
    description = str(description) if description else None
    content_div = soup.select_one(".fck_detail")

    slide_show_tag = soup.find_all("div", class_="item_slide_show")
    video_show_tag = soup.find_all("div", class_="wrap_video")
    for slide in slide_show_tag:
        slide.decompose()
    for video in video_show_tag:
        video.decompose()

    for tag in content_div.find_all(True):  # True means find all tags
        if tag.name == 'figure':
            try:
                new_tag = make_picture(soup, tag)
                tag.insert_before(new_tag)
                tag.decompose()  # Removes the tag from the tree
            except Exception as e:
                tag.decompose()
        if tag.name == 'a':
            tag['target'] = "_blank"
            tag['href'] = tag['href'].replace(vn_url, detail_url)

    content_html = str(content_div) if content_div else ""

    published_at_tag = soup.find("span", class_="date")
    published_at = published_at_tag.text.strip() if published_at_tag else ""
    src_id = get_id_from_url(link)
    article = collection_detail.find_one({"src_id": src_id})
    if article:
        return article

    data = {
        "src_id": src_id,
        "title": title,
        "author": author,
        "description": description,
        "content": content_html,
        "published_at": published_at,
        "article_url": link,
        "source_logo_url": "logo/vne_logo_rss.png"
    }
    try:
        if data:
            result = collection_detail.insert_one(data)
            print(f"Inserted id{(result.inserted_id)} new items.")
            return collection_detail.find_one({"src_id": src_id})
    except BulkWriteError as bwe:
        inserted_count = bwe.details.get("nInserted", 0)
        print(f"Inserted error {inserted_count} new item.")
