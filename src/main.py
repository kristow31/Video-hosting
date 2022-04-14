import os
import json
from time import strftime, gmtime
from datetime import timedelta, datetime
from pathlib import Path
from typing import IO, Generator, List
from qbittorrentapi import Client, LoginFailed
from qbittorrentapi import TorrentStates

from loguru import logger

import uvicorn as uvicorn
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Depends, status # Assuming you have the FastAPI class for routing
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_login import LoginManager #Loginmanager Class

if not os.path.isfile('auth.json'):
    DB = {
        "username": {"password": "qwertyuiop"},
        "DEBUG": 0,
        "video_dir": "samples_directory",
        "qbittorrent_login": "admin",
        "qbittorrent_password": "adminadmin"

    }
    with open('auth.json', 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(DB, ensure_ascii=False))
else:
    with open('auth.json', 'r', encoding='utf-8') as fh:
        DB = json.load(fh)

video_dir = r'samples_directory'
if "video_dir" in DB:
    if DB["video_dir"]:
        video_dir = DB["video_dir"]

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


files = {
    item: os.path.join(video_dir, item)
    for item in os.listdir(video_dir)
}


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
SECRET = "dfglkd4gdf3453sfdk2lfsdlfi983244fsd;lf,sasc"

origins = [
    "http://localhost",
    "http://localhost:5000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
	"http://192.168.0.1:8000",
	"http://192.168.0.21:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = LoginManager(SECRET, token_url="/login", use_cookie=True)
manager.cookie_name = "tor-video"


class NotAuthenticatedException(Exception):
    pass


def exc_handler(request, exc):
    return RedirectResponse(url='/login')


manager.not_authenticated_exception = NotAuthenticatedException
app.add_exception_handler(NotAuthenticatedException, exc_handler)


@manager.user_loader()
def load_user(username: str):
    user = DB.get(username)
    return user


def ranged(
        file: IO[bytes],
        start: int = 0,
        end: int = None,
        block_size: int = 8192,
) -> Generator[bytes, None, None]:
    consumed = 0

    file.seek(start)
    while True:
        data_length = min(block_size, end - start - consumed) if end else block_size
        if data_length <= 0:
            break
        data = file.read(data_length)
        if not data:
            break
        consumed += data_length
        yield data

    if hasattr(file, 'close'):
        file.close()


def open_file(request, video_path) -> tuple:

    path = Path(video_path)
    file = path.open('rb')
    file_size = path.stat().st_size

    content_length = file_size
    status_code = 200
    content_range = request.headers.get('Range')

    if content_range is not None:
        content_ranges = content_range.strip().lower().split('=')[-1]
        range_start, range_end, *_ = map(str.strip, (content_ranges + '-').split('-'))
        range_start = max(0, int(range_start)) if range_start else 0
        range_end = min(file_size - 1, int(range_end)) if range_end else file_size - 1
        content_length = (range_end - range_start) + 1
        file = ranged(file, start=range_start, end=range_end + 1)
        status_code = 206
        content_range = f'bytes {range_start}-{range_end}/{file_size}'

    return file, status_code, content_length, content_range


@app.get("/get_video/{video_hash}")
async def get_video(video_hash: str, request: Request, response_class=FileResponse):

    torrent = list(qb.torrents_info(torrent_hashes=video_hash))[0]
    video_path = torrent.content_path

    file, status_code, content_length, content_range = open_file(request, video_path)
    if video_path:
        return StreamingResponse(file, status_code=status_code, media_type='video/mp4', headers={
            'Accept-Ranges': 'bytes',
            'Content-Length': str(content_length),
            'Cache-Control': 'no-cache',
            'Content-Range': content_range
        })
    else:
        return Response(status_code=404)


@app.get("/get_video_folder/{video_hash}/{index}")
async def get_video(video_hash: str, index: int, request: Request, response_class=FileResponse):

    torrent = list(qb.torrents_info(torrent_hashes=video_hash))[0]
    video_path = torrent.content_path

    files_all = qb.torrents_files(torrent_hash=video_hash, SIMPLE_RESPONSES=True)
    for f in files_all:
        if f.get('name')[-3:] == 'mp4':
            if f.get('index') == index:
                video_path += '/' + f.get('name').split('/')[-1]
                break

    logger.info("get_video_folder >> {}",video_path)

    file, status_code, content_length, content_range = open_file(request, video_path)
    if video_path:
        return StreamingResponse(file, status_code=status_code, media_type='video/mp4', headers={
            'Accept-Ranges': 'bytes',
            'Content-Length': str(content_length),
            'Cache-Control': 'no-cache',
            'Content-Range': content_range
        })
    else:
        return Response(status_code=404)


@app.post("/login")
def login(data: OAuth2PasswordRequestForm = Depends()):
    username = data.username
    password = data.password
    user = load_user(username)
    if not user:
        raise HTTPException(status_code=401, detail="Нет такого пользователя!")
    elif password != user['password']:
        raise HTTPException(status_code=401, detail="Пароль не верный!")
    access_token = manager.create_access_token(
        data={"sub": username}, expires=timedelta(hours=24)
    )
    resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    manager.set_cookie(resp, access_token)
    return resp


@app.get('/login')
async def videos_list(request: Request, response_class=HTMLResponse):
    return templates.TemplateResponse("login.html", {'request': request})


@app.post("/add-torrent")
async def add_torrent(torr: str = Form(...)):
    logger.info("ADD = {}", torr)
    if torr.find('http') != -1:
        logger.success("URL = {}", torr)
        qb.torrents_add(urls=f"{torr}")

    
    resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return resp


@app.post("/add-file")
async def upload(files: List[UploadFile] = File(...)):

    for file in files:
        contents = await file.read()
        logger.success("FILE = {}", file.filename)
        qb.torrents_add(torrent_files=contents)

    logger.success({"Uploaded Filenames": [file.filename for file in files]})
    resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return resp


@app.get('/add-torrent')
async def add_torrent(request: Request, response_class=HTMLResponse):
    return templates.TemplateResponse("add_torrent.html", {'request': request})


@app.get('/play_video/{video_hash}')
async def play_video(video_hash: str, request: Request, response_class=HTMLResponse):

    torrent = list(qb.torrents_info(torrent_hashes=video_hash))[0]
    video_path = torrent.content_path
    video_name = torrent.name
    logger.success('TORRENT >> {}', torrent)

    logger.info("{} = {}", video_name, video_hash)

    if video_path:

        if video_path.find('.mp4') != -1:
            return templates.TemplateResponse('play_plyr.html', {'request': request, 'video': {'hash': video_hash, 'name': video_name}})
        else:
            files_all = qb.torrents_files(torrent_hash=video_hash, SIMPLE_RESPONSES=True)
            files = []
            for f in files_all:
                if f.get('name')[-3:] == 'mp4':

                    files.append({
                        'video': f.get('name'),
                        'id': f.get('index'),
                        'name': f.get('name').split('/')[-1]
                    })
            logger.info("FILES >> {}", files)
            return templates.TemplateResponse('play_plyr_folder.html', {'request': request, 'hash': video_hash, 'files': files})

    else:
        return Response(status_code=404)


def modification_date(filename):
    t = os.path.getmtime(filename)
    return str(datetime.fromtimestamp(t)).split()[0]


def humanbytes(B):
   'Return the given bytes as a human friendly KB, MB, GB, or TB string'
   B = float(B)
   KB = float(1024)
   MB = float(KB ** 2) # 1,048,576
   GB = float(KB ** 3) # 1,073,741,824
   TB = float(KB ** 4) # 1,099,511,627,776

   if B < KB:
      return '{0} {1}'.format(B, 'Bytes' if 0 == B > 1 else 'Byte')
   elif KB <= B < MB:
      return '{0:.2f} KB'.format(B/KB)
   elif MB <= B < GB:
      return '{0:.2f} MB'.format(B/MB)
   elif GB <= B < TB:
      return '{0:.2f} GB'.format(B/GB)
   elif TB <= B:
      return '{0:.2f} TB'.format(B/TB)


@app.get('/delete/{hash}')
async def delete_file(hash: str, request: Request, response_class=HTMLResponse, user=Depends(manager)):
    if "qbittorrent_login" in DB:
        qb.torrents_delete(delete_files=True, torrent_hashes=hash)
        response = RedirectResponse('/')
        return response
    else:
        return Response(status_code=404)


@app.get('/')
async def videos_list(request: Request, response_class=HTMLResponse, user=Depends(manager)):

    global files
    files = []
    if "qbittorrent_login" in DB:

        for torrent in qb.torrents_info():

            if torrent.state_enum.is_downloading:
                status = int((torrent.downloaded / torrent.total_size) *100)
            else:
                status = "OK"

            dt = strftime("%d.%m.%Y %H:%M", gmtime(torrent.added_on))
            files.append({
                "name": f"[{dt}]  {torrent.name}",
                "file": torrent.content_path,
                "hash": torrent.hash,
                "size": humanbytes(torrent.size),
                "status": status,
                "dt": strftime("%Y%m%d%H:%M", gmtime(torrent.added_on))
            })
        files.sort(key=lambda dictionary: dictionary['dt'], reverse=True)
        
    else:
        files0 = {
            item: os.path.join(video_dir, item)
            for item in os.listdir(video_dir)
        }
        for file in files0:
            mod = modification_date(files0[file])
            files.append({
                "name": f"[{mod}]  {file}",
                "file": file,
                "hash": '000',
                "size": '0',
                "status": "OK"
            })

    return templates.TemplateResponse("index.html", {'request': request, 'files': files})


@app.get('/ping')
async def ping_pong():

    files = []

    for torrent in qb.torrents_info():

        if torrent.state_enum.is_downloading:
            continue
        
        content_path = torrent.content_path
        #logger.info("content_path = {}", content_path)

        if content_path.find('.mp4') != -1:
            pass
        else:
            logger.debug('folder {}', content_path)
            videos = os.listdir(content_path)
            #logger.debug('videos {}', videos)
            #Фильтруем список
            videos = list(filter(lambda x: x.endswith('.mp4'), videos))
            logger.debug('FILTER {}', videos)
            

    files2 = qb.torrents_files(torrent_hash='da3a6afe9790080a9d3c6775e51965b2e0ed07c9', SIMPLE_RESPONSES=True)
    logger.success(files2)

    return {'message': 'pong'}


if __name__ == "__main__":
    if "DEBUG" in DB:
        if DB["DEBUG"]:
            uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
    else:
        print('NOT DEBUG')
