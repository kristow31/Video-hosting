import os
import sys
import time
import asyncio
import json

from telethon import TelegramClient, events, utils
from telethon.tl.types import DocumentAttributeVideo
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from loguru import logger

from qbittorrentapi import Client, LoginFailed
from qbittorrentapi import TorrentStates


api_id = 1710889
api_hash = '310b05ef37925de1a15b83ea40aa1574'
session = os.environ.get('TG_SESSION', 'printer')

with open('auth.json', 'r', encoding='utf-8') as fh:
    DB = json.load(fh)

if "qbittorrent_login" in DB:

    qb = Client(
        host='localhost',
        port=8080,
        username=DB["qbittorrent_login"],
        password=DB["qbittorrent_password"],
    )

    try:
        qb.auth_log_in()
        logger.success("START QB")
    except LoginFailed as e:
        #print(e)
        logger.error("qbittorrentapi >> {}", e)


async def start():
    print("START !!!")
    client = TelegramClient('my_video', api_id, api_hash)
    await client.start()


    files = []
    file_log = 'static/Save/telegram_video.log'

    with open(file_log, 'r') as file:
        lines = file.readlines()
        for line in lines:
            files.append(line.strip())
    
    logger.info("LINES = {}", files)

    for torrent in qb.torrents_info():

        if torrent.state_enum.is_downloading:
            continue
        
        content_path = torrent.content_path
        logger.info("content_path = {}", content_path)

        if content_path not in files:
            logger.info("OK = {}", content_path)
            if content_path.find('.mp4') != -1:
            
                metadata = extractMetadata(createParser(content_path))
                msg = await client.send_file('@v2021_2021', open(content_path, 'rb'),
                            caption=torrent.name,
                            supports_streaming=True,
                            progress_callback=callback,
                            use_cache=False,
                            attributes=(
                            DocumentAttributeVideo(
                                (0, metadata.get('duration').seconds)[metadata.has('duration')],
                                (0, metadata.get('width'))[metadata.has('width')],
                                (0, metadata.get('height'))[metadata.has('height')],
                                supports_streaming=True
                            ),))
                #print('MSG', msg)
                with open(file_log, 'a') as file:
                    file.write(f"{content_path}\n")

            else:
                # для папки с видео
                my_patch = content_path
                videos = os.listdir(content_path)
                #Фильтруем список
                videos = list(filter(lambda x: x.endswith('.mp4'), videos))
                for video in videos:
                    
                    content_path = f"{my_patch}/{video}"
                    logger.info("FOLDER OK = {}", content_path)

                    metadata = extractMetadata(createParser(content_path))
                    msg = await client.send_file('@v2021_2021', open(content_path, 'rb'),
                                caption=torrent.name,
                                supports_streaming=True,
                                progress_callback=callback,
                                use_cache=False,
                                attributes=(
                                DocumentAttributeVideo(
                                    (0, metadata.get('duration').seconds)[metadata.has('duration')],
                                    (0, metadata.get('width'))[metadata.has('width')],
                                    (0, metadata.get('height'))[metadata.has('height')],
                                    supports_streaming=True
                                ),))        

            with open(file_log, 'a') as file:
                file.write(f"{content_path}\n")

def callback(current, total):
    print('Uploaded: {:.2%}'.format(current / total))

if "__main__" in __name__:
    
    asyncio.run(start())