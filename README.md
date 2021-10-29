## Video-hosting работает на FASTAPI.
Предназначен для совместной работы с qbittorent.
Android клиент я устанавливаю, и настраиваю доступ к серверу Qbittorrent.
Через него загружаю torrent файлы...

Когда видео скачалось, то его можно смотреть через этот сайт.

### Команда для установки qbittorrent на сервер:
```
sudo add-apt-repository ppa:qbittorrent-team/qbittorrent-stable ;\
sudo apt install qbittorrent-nox -y ;\
sudo adduser --system --group qbittorrent-nox ;\
sudo adduser ubuntu qbittorrent-nox
```
Создаем nginx файл для qbittorent:
```
sudo nano /etc/nginx/sites-available/torrent.conf

server {
    listen      80;
    server_name ваш_сайт.ru;
    return 301 https://ваш_сайт.ru;
}
server {
        listen 443;
        server_name ваш_сайт.ru
        access_log  /var/log/nginx/ваш_сайт.ru.access.log;
        error_log   /var/log/nginx/ваш_сайт.ru.error.log;
        ssl_certificate         /etc/letsencrypt/live/ваш_сайт.ru/fullchain.pem;
        ssl_trusted_certificate /etc/letsencrypt/live/ваш_сайт.ru/fullchain.pem;
        ssl_certificate_key     /etc/letsencrypt/live/ваш_сайт.ru-/privkey.pem;
  location / {
    proxy_pass              http://IP_адрес_qbittorrent:8080;
  }
}
```


### Регистрация nginx файла:
```
project_path=`pwd`
sudo ln -s $project_path/nginx/video.conf /etc/nginx/sites-enabled/
sudo service nginx restart
```

### Регистрация systemd файла приложения:
```
project_path=`pwd`
sudo ln -s $project_path/systemd/video.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start video.service
sudo systemctl enable video.service
sudo systemctl status video.service
```