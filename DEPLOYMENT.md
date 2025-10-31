# 部署文档

## 环境要求

- Python 3.8+
- pip
- Chrome/Chromium 浏览器（用于selenium爬虫）
- ChromeDriver（会自动下载）

## 部署步骤

### 1. 安装系统依赖（Linux）

**Ubuntu/Debian:**
```bash
# 安装Python虚拟环境支持
sudo apt update
sudo apt install -y python3-venv python3-pip

# 安装Chrome浏览器（用于selenium）
sudo apt install -y chromium-browser chromium-chromedriver

# 或者安装Google Chrome
# wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
# sudo apt install -y ./google-chrome-stable_current_amd64.deb
```

**CentOS/RHEL:**
```bash
sudo yum install -y python3-venv python3-pip
sudo yum install -y chromium chromium-chromedriver
```

### 2. 克隆项目

```bash
git clone <repository_url>
cd solar_news_crawler
```

### 3. 创建虚拟环境

```bash
python3 -m venv venv
```

### 4. 激活虚拟环境

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 5. 安装Python依赖

```bash
pip install -r solar_news_crawler/requirements.txt
```

### 6. 运行数据抓取

进入代码目录：
```bash
cd solar_news_crawler
```

#### 方式1：立即运行一次
```bash
python master_crawler.py now
```
此命令会自动执行：
1. 爬取所有新闻源数据
2. 自动翻译成中文
3. 保存到output目录

#### 方式2：每日定时运行（推荐）
```bash
python master_crawler.py daily
```
程序会在每天上午9点自动运行爬虫和翻译。

**优点**：简单易用，无需配置cron
**注意**：需要保持程序运行在后台，建议配合systemd或screen使用

#### 方式3：使用Cron定时任务（生产环境推荐）
使用系统cron更稳定，不需要程序一直运行。详见下文"定时任务（Cron）"部分。

### 7. 启动Web应用

```bash
python app.py
```

### 8. 访问应用

打开浏览器访问：`http://localhost:5000`

## 生产环境部署建议

### 使用 Gunicorn

```bash
pip install gunicorn
cd solar_news_crawler
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 使用 systemd 服务（Linux）

创建服务文件 `/etc/systemd/system/solar-news.service`:

```ini
[Unit]
Description=Solar News Crawler Web Application
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/solar_news_crawler/solar_news_crawler
Environment="PATH=/path/to/solar_news_crawler/venv/bin"
ExecStart=/path/to/solar_news_crawler/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl enable solar-news
sudo systemctl start solar-news
sudo systemctl status solar-news
```

### 定时任务（Cron）- 推荐

使用cron定时运行爬虫，而不是让 `daily` 模式一直运行。

编辑 crontab：
```bash
crontab -e
```

添加定时任务（每天凌晨2点运行）：
```bash
# 每天凌晨2点运行爬虫和翻译
0 2 * * * cd /path/to/solar_news_crawler/solar_news_crawler && /path/to/solar_news_crawler/venv/bin/python master_crawler.py now >> /var/log/solar-crawler.log 2>&1
```

**说明**：
- 使用 `master_crawler.py now` 而不是 `daily`，因为cron会定时触发
- 程序会自动完成爬虫抓取和翻译两个步骤
- 日志输出到 `/var/log/solar-crawler.log`

### 使用 Nginx 反向代理

创建配置文件 `/etc/nginx/sites-available/solar-news`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/solar-news /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 注意事项

1. **系统依赖**：确保已安装Chrome/Chromium和ChromeDriver
2. **文件权限**：确保 `output/` 目录有写入权限
3. **路径问题**：所有Python脚本需要在 `solar_news_crawler/` 目录下运行
4. **反向代理**：生产环境建议使用Nginx
5. **日志管理**：定期清理日志文件，避免磁盘占满
6. **数据备份**：定期备份 `output/` 目录下的数据
7. **定时任务**：推荐使用cron + `now` 模式，程序会自动完成爬虫和翻译
8. **翻译功能**：master_crawler.py已集成自动翻译，无需单独运行translator.py

## 快速启动脚本

创建 `start.sh` 方便启动：

```bash
#!/bin/bash
cd "$(dirname "$0")/solar_news_crawler"
source ../venv/bin/activate
python app.py
```

赋予执行权限：
```bash
chmod +x start.sh
./start.sh
```
