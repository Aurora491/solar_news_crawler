# solar_news_crawler
# 项目简介
这是一个多来源国际太阳能新闻聚合系统，从中国政府网、国家能源局、PV Magazine、IRENA、IEA等权威来源自动抓取新闻，并提供中英文翻译功能。
快速开始
第一步：安装依赖
pip install -r requirements.txt
第二步：运行数据抓取程序（每周更新）
1. 首先运行PV Magazine爬虫
python pv_magazine_crawler.py
2. 然后运行IRENA爬虫
python irena_crawler.py
3. 接着运行IEA数据处理器
python deepseek_json.py
4. 接着运行翻译程序
python translator.py
5. 最后运行组合爬虫（整合中国政府网和国家能源局）
python combined_crawler.py
第三步：启动Web应用
python app.py
第四步：访问系统
在浏览器中打开：http://localhost:5000

