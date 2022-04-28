import requests
from bs4 import BeautifulSoup
from loguru import logger
import json, os, time
from qbittorrentapi import Client, LoginFailed
from qbittorrentapi import TorrentStates





def save_img(url, name):

    proxies = {
        "http": "http://alfard2022:russ2022alfard@vpn.pazoom.info:3128"
    }

    html = requests.get(url, proxies=proxies)
    logger.info("STATUS > {}", html.status_code)
    soup = BeautifulSoup(html.text, "lxml")
    var_all = soup.find_all('var', class_='postImg')
    for one in var_all:
        url_img = one['title']
        logger.debug("URL > {}", url_img)

        if url_img.find("fastpic.org/big/") != -1:
            try:
                response = requests.get(url_img, proxies=proxies)
                if response.status_code == 200:
                    with open(name, 'wb') as f:
                        f.write(response.content)
            except:
                logger.error("Ошибка записи >> {}", url_img)
            return 1


with open('auth.json', 'r', encoding='utf-8') as fh:
    DB = json.load(fh)

qb = Client(
    host='localhost',
    port=8080,
    username=DB["qbittorrent_login"],
    password=DB["qbittorrent_password"],
)

key = 1
for torrent in qb.torrents_info():

    properties = torrent.properties
    print(">>>>>>>>", properties.comment)
    if properties.comment:
        img_url = f'static/img_save/{torrent.hash}.jpg'
        try:
            save_img(url=properties.comment, name=img_url)
        except:
            logger.error("Что-то не так >> {}", properties.comment)
    time.sleep(1)