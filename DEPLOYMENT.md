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

### 6. 运行数据抓取和Web应用（推荐使用tmux）

进入代码目录：
```bash
cd solar_news_crawler
```

#### 🚀 推荐方式：使用scheduler.py + tmux（生产环境）

这是最推荐的部署方式，使用独立的调度器脚本和tmux管理进程：

**启动步骤：**

```bash
# 1. 启动Web应用（Session 1）
tmux new -s webapp
cd solar_news_crawler
source ../venv/bin/activate  # 激活虚拟环境
gunicorn -w 4 -b 0.0.0.0:5000 app:app
# 按 Ctrl+B 然后按 D 分离session

# 2. 启动定时调度器（Session 2）
tmux new -s scheduler
cd solar_news_crawler
source ../venv/bin/activate  # 激活虚拟环境
python scheduler.py
# 按 Ctrl+B 然后按 D 分离session
```

**管理tmux会话：**
```bash
# 查看所有会话
tmux ls

# 重新连接到webapp会话
tmux attach -t webapp

# 重新连接到scheduler会话
tmux attach -t scheduler

# 杀死会话
tmux kill-session -t webapp
tmux kill-session -t scheduler
```

**调度器说明：**
- `scheduler.py` 每天凌晨2点自动运行爬虫和翻译
- 独立进程，不影响Web服务
- 日志直接输出到终端，可通过tmux查看
- 可选参数 `--run-now` 启动时立即执行一次：`python scheduler.py --run-now`

#### 方式2：立即运行一次
```bash
python master_crawler.py now
```
此命令会自动执行：
1. 爬取所有新闻源数据
2. 自动翻译成中文
3. 保存到output目录

#### 方式3：使用Cron定时任务（备选方案）
如果不想使用scheduler.py，也可以用系统cron。详见下文"定时任务（Cron）"部分。

### 7. 访问应用

打开浏览器访问：`http://服务器IP:5000`

## 生产环境部署建议

### 使用 Gunicorn（已包含在推荐方式中）

如果不使用tmux，也可以直接运行：
```bash
pip install gunicorn
cd solar_news_crawler
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

**Worker数量建议：**
- 公式：`worker数 = (2 × CPU核心数) + 1`
- 2核CPU → 5个worker：`-w 5`
- 4核CPU → 9个worker：`-w 9`

### 使用 systemd 服务（Linux - 更稳定的生产环境）

#### Web应用服务

创建服务文件 `/etc/systemd/system/solar-news-webapp.service`:

```ini
[Unit]
Description=Solar News Crawler Web Application
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/solar_news_crawler/solar_news_crawler
Environment="PATH=/path/to/solar_news_crawler/venv/bin"
ExecStart=/path/to/solar_news_crawler/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 调度器服务

创建服务文件 `/etc/systemd/system/solar-news-scheduler.service`:

```ini
[Unit]
Description=Solar News Crawler Scheduler
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/solar_news_crawler/solar_news_crawler
Environment="PATH=/path/to/solar_news_crawler/venv/bin"
ExecStart=/path/to/solar_news_crawler/venv/bin/python scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
# 启用并启动Web应用
sudo systemctl enable solar-news-webapp
sudo systemctl start solar-news-webapp
sudo systemctl status solar-news-webapp

# 启用并启动调度器
sudo systemctl enable solar-news-scheduler
sudo systemctl start solar-news-scheduler
sudo systemctl status solar-news-scheduler

# 查看日志
sudo journalctl -u solar-news-webapp -f
sudo journalctl -u solar-news-scheduler -f
```

### 定时任务（Cron）- 备选方案

**注意：推荐使用上面的 scheduler.py 方式，更简单易管理。**

如果确实想用cron替代scheduler.py，可以这样配置：

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
- **缺点**：需要单独管理cron配置，不如scheduler.py直观

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
7. **定时任务**：**推荐使用 scheduler.py**，它会每天凌晨2点自动运行爬虫和翻译
8. **翻译功能**：master_crawler.py已集成自动翻译，无需单独运行translator.py
9. **自动重载**：Flask应用会自动检测数据文件变化并重新加载，无需重启
10. **手动刷新**：用户手动刷新有10分钟冷却时间，避免频繁触发爬虫
11. **Worker数量**：gunicorn的worker数量建议为 `(2 × CPU核心数) + 1`
12. **进程管理**：推荐使用tmux（开发/测试）或systemd（生产环境）管理进程

## 快速启动脚本

### 方式1：tmux启动脚本（推荐）

创建 `start_with_tmux.sh` 方便一键启动：

```bash
#!/bin/bash
# 快速启动Web应用和调度器

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PATH="$PROJECT_DIR/venv/bin/activate"
WORK_DIR="$PROJECT_DIR/solar_news_crawler"

echo "🚀 启动Solar News Crawler..."

# 检查tmux是否已安装
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux未安装，请先安装: sudo apt install tmux"
    exit 1
fi

# 启动Web应用
echo "📱 启动Web应用..."
tmux new-session -d -s webapp "cd $WORK_DIR && source $VENV_PATH && gunicorn -w 4 -b 0.0.0.0:5000 app:app"

# 启动调度器
echo "⏰ 启动定时调度器..."
tmux new-session -d -s scheduler "cd $WORK_DIR && source $VENV_PATH && python scheduler.py"

echo "✅ 启动完成！"
echo ""
echo "查看会话: tmux ls"
echo "连接到Web应用: tmux attach -t webapp"
echo "连接到调度器: tmux attach -t scheduler"
echo "访问应用: http://localhost:5000"
```

赋予执行权限并运行：
```bash
chmod +x start_with_tmux.sh
./start_with_tmux.sh
```

### 方式2：简单启动脚本

创建 `start.sh` 启动Web应用：

```bash
#!/bin/bash
cd "$(dirname "$0")/solar_news_crawler"
source ../venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

赋予执行权限：
```bash
chmod +x start.sh
./start.sh
```

## 架构说明

### 新架构设计（推荐）

```
┌─────────────────────────────────────────────────┐
│              部署架构                            │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────┐        ┌──────────────┐      │
│  │   Gunicorn   │        │  scheduler.py│      │
│  │  (4 workers) │        │  (独立进程)   │      │
│  └──────┬───────┘        └──────┬───────┘      │
│         │                       │               │
│         ├─ Worker 1 (Flask)     │               │
│         ├─ Worker 2 (Flask)     │               │
│         ├─ Worker 3 (Flask)     │               │
│         └─ Worker 4 (Flask)     │               │
│                │                │               │
│                │                │               │
│         每次请求时自动检查  每天02:00运行       │
│         文件哈希，有变化    master_crawler.py   │
│         自动重新加载                            │
│                                                  │
└─────────────────────────────────────────────────┘
```

**优点：**
- ✅ 职责清晰：Web服务和定时任务分离
- ✅ 无需锁：两个独立进程，无竞争
- ✅ 易维护：可以单独重启任一服务
- ✅ 自动更新：Flask检测文件变化自动重载
- ✅ 防滥用：手动刷新有10分钟冷却
