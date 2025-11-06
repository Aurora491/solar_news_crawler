import glob
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin

import requests
from flask import Flask, jsonify, render_template, request

# 导入AI总结模块
try:
    from ai_summarizer import AISummarizer
    AI_ENABLED = True
except ImportError:
    print("⚠️ AI总结模块未安装或配置不正确")
    AI_ENABLED = False


def find_latest_file(pattern, directory="output/individual"):
    """查找指定模式的最新文件"""
    if not os.path.exists(directory):
        return None
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        return None
    # 按修改时间排序，最新的在前
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def find_latest_translator_file(directory="."):
    """查找最新的翻译文件"""
    return find_latest_file("translator_*.json", directory)


# Python路径配置已移除 - 不需要手动添加系统Python路径

app = Flask(__name__)

# 全局变量存储新闻数据和爬虫状态
news_data = []
irena_news_data = []
translated_news_data = []  # 新增：存储翻译合并后的新闻数据
is_crawling = False
is_irena_crawling = False
last_update_time = None
last_irena_update_time = None
last_translated_update_time = None  # 新增：翻译数据更新时间
last_manual_refresh_time = None  # 最后一次手动刷新的时间
MANUAL_REFRESH_COOLDOWN = 600  # 手动刷新冷却时间（秒），10分钟

# AI总结数据
domestic_ai_summary = {}  # 国内新闻AI总结
international_ai_summary = {}  # 国际新闻AI总结

# 数据文件哈希值缓存
file_hashes = {"combined": None, "irena": None, "translator": None}

# 数据文件路径 - 修复路径问题
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = find_latest_file("combined_*.json") or os.path.join(
    BASE_DIR, "combined_news.json"
)
IRENA_DATA_FILE = find_latest_file("irena_*.json") or os.path.join(
    BASE_DIR, "irena_news_load_more.json"
)
IRENA_TRANSLATED_FILE = find_latest_file("irena_*_translated.json") or os.path.join(
    BASE_DIR, "irena_translated.json"
)  # 定义IRENA翻译文件
TRANSLATED_FILE = find_latest_translator_file() or os.path.join(
    BASE_DIR, "translator.json"
)  # 新增：翻译合并文件

# AI总结文件路径
AI_SUMMARY_DOMESTIC_FILE = os.path.join(BASE_DIR, "summary_domestic.json")
AI_SUMMARY_INTERNATIONAL_FILE = os.path.join(BASE_DIR, "summary_international.json")

print(f"📁 数据文件路径: {DATA_FILE}")
print(f"📁 IRENA数据文件路径: {IRENA_DATA_FILE}")
print(f"📁 IRENA翻译文件路径: {IRENA_TRANSLATED_FILE}")
print(f"📁 翻译合并文件路径: {TRANSLATED_FILE}")
print(f"📁 国内AI总结文件: {AI_SUMMARY_DOMESTIC_FILE}")
print(f"📁 国际AI总结文件: {AI_SUMMARY_INTERNATIONAL_FILE}")


# 翻译相关配置
class Translator:
    def __init__(self):
        self.cache_file = os.path.join(BASE_DIR, "translation_cache.json")
        self.translation_cache = self._load_cache()

    def _load_cache(self):
        """加载翻译缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_cache(self):
        """保存翻译缓存"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.translation_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _get_cache_key(self, text, target_lang):
        """生成缓存键"""
        text_hash = hashlib.md5(f"{text}_{target_lang}".encode("utf-8")).hexdigest()
        return text_hash

    def translate_text(self, text, target_lang="zh-cn"):
        """翻译文本到目标语言"""
        if not text or not text.strip():
            return text

        # 检查缓存
        cache_key = self._get_cache_key(text, target_lang)
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]

        # 使用googletrans进行翻译
        try:
            from googletrans import Translator

            translator = Translator()
            result = translator.translate(text, dest=target_lang)

            if result and result.text:
                # 缓存结果
                self.translation_cache[cache_key] = result.text
                self._save_cache()
                return result.text
            else:
                return text

        except Exception as e:
            print(f"Googletrans翻译失败: {e}")
            # 翻译失败时返回原始文本
            return text

    def translate_news_item(self, news_item):
        """翻译新闻条目"""
        try:
            translated_item = news_item.copy()

            # 翻译标题
            if "title" in news_item and news_item["title"]:
                translated_title = self.translate_text(news_item["title"], "zh-cn")
                translated_item["title_translated"] = translated_title
                translated_item["title_original"] = news_item["title"]
            else:
                translated_item["title_translated"] = news_item.get("title", "")
                translated_item["title_original"] = news_item.get("title", "")

            # 翻译描述/摘要
            if "summary" in news_item and news_item["summary"]:
                translated_summary = self.translate_text(news_item["summary"], "zh-cn")
                translated_item["summary_translated"] = translated_summary
                translated_item["summary_original"] = news_item["summary"]
            elif "description" in news_item and news_item["description"]:
                translated_summary = self.translate_text(
                    news_item["description"], "zh-cn"
                )
                translated_item["summary_translated"] = translated_summary
                translated_item["summary_original"] = news_item["description"]
            else:
                translated_item["summary_translated"] = news_item.get(
                    "summary", ""
                ) or news_item.get("description", "")
                translated_item["summary_original"] = news_item.get(
                    "summary", ""
                ) or news_item.get("description", "")

            return translated_item
        except Exception as e:
            print(f"翻译新闻条目失败: {e}")
            # 返回原始数据
            news_item["title_translated"] = news_item.get("title", "")
            news_item["summary_translated"] = news_item.get(
                "summary", ""
            ) or news_item.get("description", "")
            return news_item


# 创建翻译器实例
translator = Translator()


def calculate_file_hash(filepath):
    """计算文件的MD5哈希值"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash
    except Exception as e:
        print(f"❌ 计算文件哈希失败 {filepath}: {e}")
        return None


def check_and_reload_data():
    """检查数据文件是否有更新，如果有则重新加载"""
    global file_hashes, news_data, irena_news_data, translated_news_data
    global last_update_time, last_irena_update_time, last_translated_update_time

    reload_flags = {"combined": False, "irena": False, "translator": False}

    # 检查combined文件
    latest_combined = find_latest_file("combined_*.json") or DATA_FILE
    if os.path.exists(latest_combined):
        current_hash = calculate_file_hash(latest_combined)
        if current_hash and current_hash != file_hashes["combined"]:
            print(f"🔄 检测到combined数据文件更新: {latest_combined}")
            file_hashes["combined"] = current_hash
            reload_flags["combined"] = True

    # 检查irena翻译文件
    latest_irena_translated = (
        find_latest_file("irena_*_translated.json") or IRENA_TRANSLATED_FILE
    )
    if os.path.exists(latest_irena_translated):
        current_hash = calculate_file_hash(latest_irena_translated)
        if current_hash and current_hash != file_hashes["irena"]:
            print(f"🔄 检测到IRENA数据文件更新: {latest_irena_translated}")
            file_hashes["irena"] = current_hash
            reload_flags["irena"] = True

    # 检查translator文件
    latest_translator = find_latest_translator_file() or TRANSLATED_FILE
    if os.path.exists(latest_translator):
        current_hash = calculate_file_hash(latest_translator)
        if current_hash and current_hash != file_hashes["translator"]:
            print(f"🔄 检测到翻译数据文件更新: {latest_translator}")
            file_hashes["translator"] = current_hash
            reload_flags["translator"] = True

    # 根据标志重新加载数据
    if reload_flags["combined"]:
        if load_news_from_file():
            last_update_time = datetime.now()
            print(f"✅ 已重新加载combined数据: {len(news_data)} 条")

    if reload_flags["irena"]:
        if load_irena_news_from_file():
            last_irena_update_time = datetime.now()
            print(f"✅ 已重新加载IRENA数据: {len(irena_news_data)} 条")

    if reload_flags["translator"]:
        if load_translated_news_from_file():
            last_translated_update_time = datetime.now()
            print(f"✅ 已重新加载翻译数据: {len(translated_news_data)} 条")

    return any(reload_flags.values())


def load_news_from_file():
    """从JSON文件加载国内新闻数据"""
    global news_data
    try:
        # 动态查找最新的combined文件
        latest_file = find_latest_file("combined_*.json") or DATA_FILE

        if os.path.exists(latest_file):
            with open(latest_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)

            if isinstance(loaded_data, list):
                news_data = loaded_data
                print(f"✅ 从 {latest_file} 加载了 {len(news_data)} 条国内新闻")
                return True
            else:
                print(f"❌ 数据文件格式错误，期望列表，得到 {type(loaded_data)}")
                return False
        else:
            print(f"❌ 数据文件 {latest_file} 不存在")
            alternative_files = [
                "gov_solar_news.json",
                "nea_solar_news.json",
                "solar_news.json",
            ]
            for file in alternative_files:
                alt_path = os.path.join(BASE_DIR, file)
                if os.path.exists(alt_path):
                    print(f"🔍 尝试加载替代文件: {file}")
                    with open(alt_path, "r", encoding="utf-8") as f:
                        news_data = json.load(f)
                    print(f"✅ 从 {file} 加载了 {len(news_data)} 条新闻")
                    return True
            return False
    except Exception as e:
        print(f"❌ 加载数据文件失败: {e}")
        create_test_data()
        return True


def load_irena_news_from_file():
    """从JSON文件加载IRENA新闻数据"""
    global irena_news_data
    try:
        # 动态查找最新的irena翻译文件
        latest_translated_file = (
            find_latest_file("irena_*_translated.json") or IRENA_TRANSLATED_FILE
        )
        latest_irena_file = find_latest_file("irena_*.json") or IRENA_DATA_FILE

        # 优先尝试加载翻译后的文件
        if os.path.exists(latest_translated_file):
            print(f"🔍 找到翻译后的文件: {latest_translated_file}")
            with open(latest_translated_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)

            if isinstance(loaded_data, list):
                irena_news_data = loaded_data
                print(f"✅ 从翻译文件加载了 {len(irena_news_data)} 条IRENA新闻")
                return True

        # 如果翻译文件不存在，回退到原始文件
        if os.path.exists(latest_irena_file):
            with open(latest_irena_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)

            if isinstance(loaded_data, list):
                irena_news_data = loaded_data
            elif isinstance(loaded_data, dict) and "news_list" in loaded_data:
                irena_news_data = loaded_data["news_list"]
            else:
                print(f"❌ IRENA数据文件格式错误: {type(loaded_data)}")
                return False

            print(
                f"✅ 从 {latest_irena_file} 加载了 {len(irena_news_data)} 条IRENA新闻"
            )
            return True
        else:
            print(f"❌ IRENA数据文件 {latest_irena_file} 不存在")
            irena_alternative_files = [
                "irena_news.json",
                "irena_news_comprehensive.json",
                "irena_news_paginated.json",
            ]
            for file in irena_alternative_files:
                alt_path = os.path.join(BASE_DIR, file)
                if os.path.exists(alt_path):
                    print(f"🔍 尝试加载IRENA替代文件: {file}")
                    with open(alt_path, "r", encoding="utf-8") as f:
                        alt_data = json.load(f)

                    if isinstance(alt_data, list):
                        irena_news_data = alt_data
                    elif isinstance(alt_data, dict) and "news_list" in alt_data:
                        irena_news_data = alt_data["news_list"]
                    else:
                        continue

                    print(f"✅ 从 {file} 加载了 {len(irena_news_data)} 条IRENA新闻")
                    return True
            return False
    except Exception as e:
        print(f"❌ 加载IRENA数据文件失败: {e}")
        return False


def load_translated_news_from_file():
    """从翻译合并文件加载数据"""
    global translated_news_data, last_translated_update_time
    try:
        # 动态查找最新的translator文件
        latest_file = find_latest_translator_file() or TRANSLATED_FILE

        if os.path.exists(latest_file):
            with open(latest_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)

            if isinstance(loaded_data, dict) and "news_list" in loaded_data:
                translated_news_data = loaded_data["news_list"]
                print(
                    f"✅ 从翻译文件 {latest_file} 加载了 {len(translated_news_data)} 条多来源新闻"
                )
                last_translated_update_time = datetime.now()
                return True
            elif isinstance(loaded_data, list):
                translated_news_data = loaded_data
                print(
                    f"✅ 从翻译文件 {latest_file} 加载了 {len(translated_news_data)} 条多来源新闻"
                )
                last_translated_update_time = datetime.now()
                return True
            else:
                print(f"❌ 翻译文件格式错误: {type(loaded_data)}")
                return False
        else:
            print(f"❌ 翻译文件 {latest_file} 不存在")
            return False
    except Exception as e:
        print(f"❌ 加载翻译文件失败: {e}")
        return False


def create_test_data():
    """创建测试数据"""
    global news_data
    print("🔄 创建测试数据...")

    test_news = []

    nea_titles = [
        "国家能源局发布光伏产业发展指导意见",
        "光伏发电项目审批流程优化方案",
        "新能源政策支持光伏技术创新",
        "分布式光伏发电推广应用通知",
        "光伏扶贫项目成效显著",
        "太阳能光伏产业链发展报告",
        "光伏电站建设标准更新",
        "可再生能源光伏发电统计",
        "光伏组件质量监管加强",
        "光伏产业国际合作交流",
    ]

    gov_titles = [
        "国务院推进光伏产业发展政策",
        "光伏发电补贴政策调整通知",
        "新能源光伏技术创新支持计划",
        "分布式光伏发电推广应用",
        "光伏扶贫助力乡村振兴",
        "太阳能光伏产业发展规划",
        "光伏电站安全运行管理",
        "可再生能源光伏发电数据",
        "光伏组件质量标准提升",
        "光伏产业国际合作成果",
    ]

    for i, title in enumerate(nea_titles):
        date = datetime(2024, 9, 1) + timedelta(days=random.randint(0, 47))
        test_news.append(
            {
                "title": title,
                "link": f"https://www.nea.gov.cn/news_{i}",
                "date": date.strftime("%Y-%m-%d"),
                "source": "国家能源局",
            }
        )

    for i, title in enumerate(gov_titles):
        date = datetime(2024, 9, 1) + timedelta(days=random.randint(0, 47))
        test_news.append(
            {
                "title": title,
                "link": f"https://www.gov.cn/news_{i}",
                "date": date.strftime("%Y-%m-%d"),
                "source": "中国政府网",
            }
        )

    news_data = test_news
    print(f"✅ 创建了 {len(news_data)} 条测试数据")


def save_news_to_file(data, filename=DATA_FILE):
    """保存新闻数据到JSON文件"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 数据已保存到 {filename}")
        return True
    except Exception as e:
        print(f"❌ 保存数据文件失败: {e}")
        return False


def run_crawler():
    """运行国内爬虫脚本"""
    try:
        print("🚀 启动国内爬虫脚本...")
        crawler_path = os.path.join(BASE_DIR, "combined_crawler.py")
        print(f"📝 爬虫脚本路径: {crawler_path}")

        result = subprocess.run(
            [sys.executable, crawler_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=BASE_DIR,
        )

        print(f"📊 爬虫输出: {result.stdout}")
        if result.stderr:
            print(f"❌ 爬虫错误: {result.stderr}")

        if result.returncode == 0:
            print("✅ 国内爬虫脚本执行成功")
            return True
        else:
            print(f"❌ 国内爬虫脚本执行失败，返回码: {result.returncode}")
            return False
    except Exception as e:
        print(f"❌ 运行国内爬虫脚本时出错: {e}")
        return False


def run_irena_crawler():
    """运行IRENA爬虫脚本"""
    try:
        print("🚀 启动IRENA爬虫脚本...")
        crawler_path = os.path.join(BASE_DIR, "irena_crawler.py")

        result = subprocess.run(
            [sys.executable, crawler_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=BASE_DIR,
        )

        print(f"📊 IRENA爬虫输出: {result.stdout}")
        if result.stderr:
            print(f"❌ IRENA爬虫错误: {result.stderr}")

        if result.returncode == 0:
            print("✅ IRENA爬虫脚本执行成功")
            return True
        else:
            print(f"❌ IRENA爬虫脚本执行失败，返回码: {result.returncode}")
            return False
    except Exception as e:
        print(f"❌ 运行IRENA爬虫脚本时出错: {e}")
        return False


def initialize_data():
    """初始化数据"""
    global \
        news_data, \
        irena_news_data, \
        translated_news_data, \
        last_update_time, \
        last_irena_update_time, \
        last_translated_update_time
    global file_hashes

    print("🔄 初始化数据...")

    # 初始化combined数据和哈希
    if load_news_from_file():
        last_update_time = datetime.now()
        latest_combined = find_latest_file("combined_*.json") or DATA_FILE
        file_hashes["combined"] = calculate_file_hash(latest_combined)
        print(f"✅ 国内数据初始化完成: {len(news_data)} 条新闻")
    else:
        print("❌ 国内数据初始化失败")

    # 初始化IRENA数据和哈希
    if load_irena_news_from_file():
        last_irena_update_time = datetime.now()
        latest_irena = (
            find_latest_file("irena_*_translated.json") or IRENA_TRANSLATED_FILE
        )
        file_hashes["irena"] = calculate_file_hash(latest_irena)
        print(f"✅ IRENA数据初始化完成: {len(irena_news_data)} 条新闻")
    else:
        print("❌ IRENA数据初始化失败")

    # 初始化翻译数据和哈希
    if load_translated_news_from_file():
        last_translated_update_time = datetime.now()
        latest_translator = find_latest_translator_file() or TRANSLATED_FILE
        file_hashes["translator"] = calculate_file_hash(latest_translator)
        print(f"✅ 翻译数据初始化完成: {len(translated_news_data)} 条新闻")
    else:
        print("❌ 翻译数据初始化失败")


# 在模块加载时初始化数据（支持gunicorn等WSGI服务器）
initialize_data()

# ==================== 国内新闻路由 ====================


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/news_search")
def news_search():
    return render_template("news_search.html")


@app.route("/translated_news")
def translated_news():
    return render_template("translated_news.html")


@app.route("/get_news")
def get_news():
    """获取筛选后的国内新闻数据"""
    global news_data

    # 自动检查并重新加载数据文件（如果有更新）
    check_and_reload_data()

    try:
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        keyword = request.args.get("keyword", "").strip()
        source_filter = request.args.get("source", "").strip()

        print(
            f"🔍 筛选参数: start_date={start_date_str}, end_date={end_date_str}, keyword={keyword}, source={source_filter}"
        )

        if not news_data:
            load_news_from_file()

        filtered_news = []
        for news in news_data:
            include = True

            if start_date_str and end_date_str:
                try:
                    news_date = datetime.strptime(news["date"], "%Y-%m-%d").date()
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    if not (start_date <= news_date <= end_date):
                        include = False
                except ValueError:
                    include = False

            if include and keyword and keyword.lower() not in news["title"].lower():
                include = False

            if include and source_filter and news["source"] != source_filter:
                include = False

            if include:
                filtered_news.append(news)

        filtered_news.sort(key=lambda x: x["date"], reverse=True)

        source_stats = {}
        for news in filtered_news:
            source = news["source"]
            source_stats[source] = source_stats.get(source, 0) + 1

        print(f"📊 筛选结果: 总数={len(news_data)}, 筛选后={len(filtered_news)}")

        return jsonify(
            {
                "success": True,
                "data": filtered_news,
                "count": len(filtered_news),
                "total_count": len(news_data),
                "filtered_source_stats": source_stats,
                "last_update": last_update_time.strftime("%Y-%m-%d %H:%M:%S")
                if last_update_time
                else None,
            }
        )

    except Exception as e:
        print(f"❌ 获取新闻数据错误: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/get_stats")
def get_stats():
    """获取国内数据统计信息"""
    global news_data

    try:
        source_stats = {}
        for news in news_data:
            source = news["source"]
            source_stats[source] = source_stats.get(source, 0) + 1

        return jsonify(
            {
                "success": True,
                "total_count": len(news_data),
                "source_stats": source_stats,
                "last_update": last_update_time.strftime("%Y-%m-%d %H:%M:%S")
                if last_update_time
                else None,
            }
        )

    except Exception as e:
        print(f"❌ 获取统计信息错误: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/refresh_news")
def refresh_news():
    """触发国内新闻数据更新 - 运行爬虫脚本"""
    global is_crawling, last_manual_refresh_time

    # 检查冷却时间
    if last_manual_refresh_time:
        elapsed = (datetime.now() - last_manual_refresh_time).total_seconds()
        if elapsed < MANUAL_REFRESH_COOLDOWN:
            remaining = int(MANUAL_REFRESH_COOLDOWN - elapsed)
            return jsonify(
                {"success": False, "error": f"数据已是最新，请 {remaining} 秒后再试"}
            )

    if is_crawling:
        return jsonify({"success": False, "error": "正在更新中，请稍候..."})

    def crawl_news():
        global news_data, is_crawling, last_update_time

        is_crawling = True
        print("🚀 开始运行爬虫更新数据...")

        try:
            if run_crawler():
                if load_news_from_file():
                    last_update_time = datetime.now()
                    print(f"🎉 数据更新完成！总计：{len(news_data)} 条新闻")
                else:
                    print("❌ 数据加载失败")
            else:
                print("❌ 爬虫运行失败")

        except Exception as e:
            print(f"❌ 数据更新失败: {e}")
        finally:
            is_crawling = False

    # 更新最后刷新时间
    last_manual_refresh_time = datetime.now()

    thread = threading.Thread(target=crawl_news)
    thread.daemon = True
    thread.start()

    return jsonify(
        {"success": True, "message": "开始更新数据，这可能需要几分钟时间..."}
    )


@app.route("/check_update")
def check_update():
    """检查国内更新状态"""
    global is_crawling, last_update_time

    if is_crawling:
        return jsonify(
            {"success": True, "updated": False, "message": "正在更新数据..."}
        )
    else:
        if last_update_time:
            return jsonify(
                {
                    "success": True,
                    "updated": True,
                    "message": f"数据更新完成！最后更新：{last_update_time.strftime('%Y-%m-%d %H:%M:%S')}",
                }
            )
        else:
            return jsonify({"success": True, "updated": True, "message": "数据已就绪"})


# ==================== IRENA新闻路由 ====================


@app.route("/get_irena_news")
def get_irena_news():
    """获取筛选后的IRENA新闻数据"""
    global irena_news_data

    # 自动检查并重新加载数据文件（如果有更新）
    check_and_reload_data()

    try:
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        keyword = request.args.get("keyword", "").strip()

        print(
            f"🔍 IRENA筛选参数: start_date={start_date_str}, end_date={end_date_str}, keyword={keyword}"
        )

        if not irena_news_data:
            load_irena_news_from_file()

        filtered_news = []
        for news in irena_news_data:
            include = True

            if start_date_str and end_date_str:
                try:
                    news_date_str = news.get("date", "")
                    if not news_date_str:
                        continue

                    if re.match(r"\d{4}-\d{2}-\d{2}", news_date_str):
                        news_date = datetime.strptime(news_date_str, "%Y-%m-%d").date()
                    elif re.match(r"\d{1,2}\s+\w+\s+\d{4}", news_date_str):
                        news_date = datetime.strptime(news_date_str, "%d %B %Y").date()
                    else:
                        continue

                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

                    if not (start_date <= news_date <= end_date):
                        include = False
                except ValueError as e:
                    print(f"日期解析错误: {e}, 日期: {news_date_str}")
                    include = False

            if include and keyword:
                keyword_lower = keyword.lower()
                title = news.get("title", "").lower()
                summary = news.get("summary", "").lower()
                search_keyword = news.get("search_keyword", "").lower()

                if (
                    keyword_lower not in title
                    and keyword_lower not in summary
                    and keyword_lower not in search_keyword
                ):
                    include = False

            if include:
                filtered_news.append(news)

        filtered_news.sort(key=lambda x: x.get("date", ""), reverse=True)

        print(
            f"📊 IRENA筛选结果: 总数={len(irena_news_data)}, 筛选后={len(filtered_news)}"
        )

        return jsonify(
            {
                "success": True,
                "data": filtered_news,
                "count": len(filtered_news),
                "total_count": len(irena_news_data),
                "last_update": last_irena_update_time.strftime("%Y-%m-%d %H:%M:%S")
                if last_irena_update_time
                else None,
            }
        )

    except Exception as e:
        print(f"❌ 获取IRENA新闻数据错误: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/refresh_irena_news")
def refresh_irena_news():
    """触发IRENA新闻数据更新"""
    global is_irena_crawling, last_manual_refresh_time

    # 检查冷却时间
    if last_manual_refresh_time:
        elapsed = (datetime.now() - last_manual_refresh_time).total_seconds()
        if elapsed < MANUAL_REFRESH_COOLDOWN:
            remaining = int(MANUAL_REFRESH_COOLDOWN - elapsed)
            return jsonify(
                {"success": False, "error": f"数据已是最新，请 {remaining} 秒后再试"}
            )

    if is_irena_crawling:
        return jsonify({"success": False, "error": "IRENA数据正在更新中，请稍候..."})

    def crawl_irena_news():
        global irena_news_data, is_irena_crawling, last_irena_update_time

        is_irena_crawling = True
        print("🚀 开始运行IRENA爬虫更新数据...")

        try:
            if run_irena_crawler():
                if load_irena_news_from_file():
                    last_irena_update_time = datetime.now()
                    print(f"🎉 IRENA数据更新完成！总计：{len(irena_news_data)} 条新闻")
                else:
                    print("❌ IRENA数据加载失败")
            else:
                print("❌ IRENA爬虫运行失败")

        except Exception as e:
            print(f"❌ IRENA数据更新失败: {e}")
        finally:
            is_irena_crawling = False

    # 更新最后刷新时间
    last_manual_refresh_time = datetime.now()

    thread = threading.Thread(target=crawl_irena_news)
    thread.daemon = True
    thread.start()

    return jsonify(
        {"success": True, "message": "开始更新IRENA数据，这可能需要几分钟时间..."}
    )


@app.route("/check_irena_update")
def check_irena_update():
    """检查IRENA更新状态"""
    global is_irena_crawling, last_irena_update_time

    if is_irena_crawling:
        return jsonify(
            {"success": True, "updated": False, "message": "正在更新IRENA数据..."}
        )
    else:
        if last_irena_update_time:
            return jsonify(
                {
                    "success": True,
                    "updated": True,
                    "message": f"IRENA数据更新完成！最后更新：{last_irena_update_time.strftime('%Y-%m-%d %H:%M:%S')}",
                }
            )
        else:
            return jsonify(
                {"success": True, "updated": True, "message": "IRENA数据已就绪"}
            )


# ==================== 翻译合并新闻路由 ====================


@app.route("/refresh_translated_news")
def refresh_translated_news():
    """重新加载最新的翻译文件（不运行爬虫，只刷新数据）"""
    global translated_news_data, last_translated_update_time, last_manual_refresh_time

    # 检查冷却时间
    if last_manual_refresh_time:
        elapsed = (datetime.now() - last_manual_refresh_time).total_seconds()
        if elapsed < MANUAL_REFRESH_COOLDOWN:
            remaining = int(MANUAL_REFRESH_COOLDOWN - elapsed)
            return jsonify(
                {"success": False, "error": f"数据已是最新，请 {remaining} 秒后再试"}
            )

    try:
        print("🔄 开始刷新翻译数据...")

        # 更新最后刷新时间
        last_manual_refresh_time = datetime.now()

        # 重新加载最新的翻译文件
        if load_translated_news_from_file():
            print(f"✅ 翻译数据刷新成功！总计：{len(translated_news_data)} 条新闻")
            return jsonify(
                {
                    "success": True,
                    "message": f"数据刷新成功！共 {len(translated_news_data)} 条新闻",
                    "count": len(translated_news_data),
                    "last_update": last_translated_update_time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if last_translated_update_time
                    else None,
                }
            )
        else:
            print("❌ 翻译数据加载失败")
            return jsonify({"success": False, "error": "数据加载失败，请稍后重试"})

    except Exception as e:
        print(f"❌ 刷新翻译数据失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/get_translated_news")
def get_translated_news():
    """获取翻译合并后的多来源新闻数据"""
    global translated_news_data

    # 自动检查并重新加载数据文件（如果有更新）
    check_and_reload_data()

    try:
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        keyword = request.args.get("keyword", "").strip()
        source_filter = request.args.get("source", "").strip()

        print(
            f"🔍 翻译新闻筛选参数: start_date={start_date_str}, end_date={end_date_str}, keyword={keyword}, source={source_filter}"
        )

        if not translated_news_data:
            load_translated_news_from_file()

        filtered_news = []
        for news in translated_news_data:
            include = True

            # 日期筛选
            if start_date_str and end_date_str:
                try:
                    news_date_str = news.get("publish_date", "") or news.get("date", "")
                    if not news_date_str:
                        continue

                    if re.match(r"\d{4}-\d{2}-\d{2}", news_date_str):
                        news_date = datetime.strptime(news_date_str, "%Y-%m-%d").date()
                        start_date = datetime.strptime(
                            start_date_str, "%Y-%m-%d"
                        ).date()
                        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

                        if not (start_date <= news_date <= end_date):
                            include = False
                except ValueError as e:
                    print(f"日期解析错误: {e}, 日期: {news_date_str}")
                    include = False

            # 关键词筛选
            if include and keyword:
                keyword_lower = keyword.lower()
                title_original = news.get("title_original", "").lower()
                title_translated = news.get("title_translated", "").lower()
                summary = news.get("summary", "").lower()

                if (
                    keyword_lower not in title_original
                    and keyword_lower not in title_translated
                    and keyword_lower not in summary
                ):
                    include = False

            # 来源筛选
            if (
                include
                and source_filter
                and news.get("source", "").lower() != source_filter.lower()
            ):
                include = False

            if include:
                filtered_news.append(news)

        # 按日期排序
        filtered_news.sort(
            key=lambda x: x.get("publish_date", "") or x.get("date", ""), reverse=True
        )

        # 统计各来源数量
        source_stats = {}
        for news in filtered_news:
            source = news.get("source", "Unknown")
            source_stats[source] = source_stats.get(source, 0) + 1

        print(
            f"📊 翻译新闻筛选结果: 总数={len(translated_news_data)}, 筛选后={len(filtered_news)}"
        )

        return jsonify(
            {
                "success": True,
                "data": filtered_news,
                "count": len(filtered_news),
                "total_count": len(translated_news_data),
                "source_stats": source_stats,
                "last_update": last_translated_update_time.strftime("%Y-%m-%d %H:%M:%S")
                if last_translated_update_time
                else None,
            }
        )

    except Exception as e:
        print(f"❌ 获取翻译新闻数据错误: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/get_translated_stats")
def get_translated_stats():
    """获取翻译新闻统计信息"""
    global translated_news_data

    try:
        source_stats = {}
        for news in translated_news_data:
            source = news.get("source", "Unknown")
            source_stats[source] = source_stats.get(source, 0) + 1

        return jsonify(
            {
                "success": True,
                "total_count": len(translated_news_data),
                "source_stats": source_stats,
                "last_update": last_translated_update_time.strftime("%Y-%m-%d %H:%M:%S")
                if last_translated_update_time
                else None,
            }
        )

    except Exception as e:
        print(f"❌ 获取翻译统计信息错误: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/translate_news")
def translate_news():
    """翻译单条新闻"""
    try:
        title = request.args.get("title", "")
        description = request.args.get("description", "")

        # 调用翻译器进行实际翻译
        translated_title = translator.translate_text(title, "zh-cn")
        translated_description = (
            translator.translate_text(description, "zh-cn") if description else ""
        )

        return jsonify(
            {
                "success": True,
                "translated_title": translated_title,
                "translated_description": translated_description,
                "original_title": title,
                "original_description": description,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==================== AI总结相关功能 ====================


def load_ai_summary(file_path):
    """从文件加载AI总结（返回今天的，如果没有就返回最新的）"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 如果是列表格式（新格式）
            if isinstance(data, list) and len(data) > 0:
                today = datetime.now().strftime("%Y-%m-%d")
                # 优先返回今天的简报
                for item in data:
                    if item.get("date") == today:
                        print(f"✅ AI总结加载成功 (今日): {file_path}")
                        return item
                # 如果没有今天的，返回最新的（列表第一条）
                print(f"✅ AI总结加载成功 (最新): {file_path}")
                return data[0]

            # 兼容旧格式（字典）
            print(f"✅ AI总结加载成功: {file_path}")
            return data
        else:
            print(f"⚠️ AI总结文件不存在: {file_path}")
            return {}
    except Exception as e:
        print(f"❌ 加载AI总结失败: {e}")
        return {}


@app.route("/get_ai_summary/<news_type>")
def get_ai_summary(news_type):
    """
    获取AI总结
    news_type: domestic(国内) 或 international(国际)
    """
    global domestic_ai_summary, international_ai_summary

    try:
        if news_type == "domestic":
            # 重新加载国内新闻AI总结
            summary = load_ai_summary(AI_SUMMARY_DOMESTIC_FILE)
            domestic_ai_summary = summary
        elif news_type == "international":
            # 重新加载国际新闻AI总结
            summary = load_ai_summary(AI_SUMMARY_INTERNATIONAL_FILE)
            international_ai_summary = summary
        else:
            return jsonify({"success": False, "error": "无效的新闻类型"})

        if not summary:
            return jsonify({
                "success": False,
                "error": "暂无AI总结数据，请先生成总结"
            })

        return jsonify({
            "success": True,
            "data": summary
        })

    except Exception as e:
        print(f"❌ 获取AI总结错误: {e}")
        return jsonify({"success": False, "error": str(e)})




if __name__ == "__main__":
    if not os.path.exists("templates"):
        os.makedirs("templates")

    # 数据已在模块级别初始化，此处无需重复调用

    print("🌐 启动Flask应用...")
    print("📱 访问 http://127.0.0.1:5000 查看网站")
    print("📰 访问 http://127.0.0.1:5000/translated_news 查看多来源翻译新闻")
    app.run(debug=True, host="127.0.0.1", port=5000)
