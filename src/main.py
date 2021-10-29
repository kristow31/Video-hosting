import os
import json
from datetime import timedelta
from pathlib import Path
from typing import IO, Generator

import uvicorn as uvicorn
from fastapi import FastAPI, HTTPException
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
from fastapi_login.exceptions import InvalidCredentialsException #Exception class

if not os.path.isfile('auth.json'):
    DB = {"username": {"password": "qwertyuiop"}, "DEBUG": 0}
    with open('auth.json', 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(DB, ensure_ascii=False))
else:
    with open('auth.json', 'r', encoding='utf-8') as fh:
        DB = json.load(fh)


files = {
    item: os.path.join(r'samples_directory', item)
    for item in os.listdir(r'samples_directory')
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


@app.get("/get_video/{video_name}")
async def get_video(video_name: str, request: Request, response_class=FileResponse):
    video_path = files.get(video_name)
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


@app.get('/play_video/plyr/{video_name}')
async def play_video(video_name: str, request: Request, response_class=HTMLResponse):
    video_path = files.get(video_name)
    if video_path:
        return templates.TemplateResponse(
            'play_plyr.html', {'request': request, 'video': {'path': video_path, 'name': video_name}})
    else:
        return Response(status_code=404)


@app.get('/play_video/videojs/{video_name}')
async def play_video(video_name: str, request: Request, response_class=HTMLResponse):
    video_path = files.get(video_name)
    if video_path:
        return templates.TemplateResponse(
            'play_videojs.html', {'request': request, 'video': {'path': video_path, 'name': video_name}})
    else:
        return Response(status_code=404)


@app.get('/play_video/mediaelement/{video_name}')
async def play_video(video_name: str, request: Request, response_class=HTMLResponse):
    video_path = files.get(video_name)
    if video_path:
        return templates.TemplateResponse(
            'play_mediaelement.html', {'request': request, 'video': {'path': video_path, 'name': video_name}})
    else:
        return Response(status_code=404)


@app.get('/play_video/html5/{video_name}')
async def play_video(video_name: str, request: Request, response_class=HTMLResponse):
    video_path = files.get(video_name)
    if video_path:
        return templates.TemplateResponse(
            'play_html5.html', {'request': request, 'video': {'path': video_path, 'name': video_name}})
    else:
        return Response(status_code=404)


@app.get('/play_video_wasm/{video_name}')
async def play_video(video_name: str, request: Request, response_class=HTMLResponse):
    video_path = files.get(video_name)
    if video_path:
        return templates.TemplateResponse(
            'wasm_player.html', {'request': request, 'video': {'path': video_path, 'name': video_name}})
    else:
        return Response(status_code=404)


@app.get('/')
async def videos_list(request: Request, response_class=HTMLResponse, user=Depends(manager)):
    return templates.TemplateResponse("index.html", {'request': request, 'files': files})


@app.get('/ping')
async def ping_pong():
    return {'message': 'pong'}


if __name__ == "__main__":
    if "DEBUG" in DB:
        if DB["DEBUG"]:
            uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
        else:
            pass
            #print('DEBUG False')
    else:
        print('NOT DEBUG')
