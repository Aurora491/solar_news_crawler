# solar_news_crawler
# 项目简介
这是一个多来源国际太阳能新闻聚合系统，从中国政府网、国家能源局、PV Magazine、IRENA、IEA等权威来源自动抓取新闻，并提供中英文翻译功能。
# 快速开始
## 第一步：安装依赖
pip install -r requirements.txt
## 第二步：运行数据抓取程序（每周更新）
### 1. 首先每日自动运行
python master_crawler.py daily
### 2. 接着运行翻译程序
python translator.py
## 第三步：启动Web应用
python app.py
## 第四步：访问系统
在浏览器中打开：http://localhost:5000

