from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import re
import os
import tempfile
import uuid
import random

class PVMagazineSeleniumCrawler:
    def __init__(self):
        self.base_url = "https://www.pv-magazine.com"
        self.content_data = []
        
        # 设置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')  # 新版无头模式
        chrome_options.add_argument('--disable-gpu')

        # 创建唯一的用户数据目录，避免多实例冲突
        unique_dir = os.path.join(tempfile.gettempdir(), f"chrome_pvmag_{uuid.uuid4().hex}")
        chrome_options.add_argument(f'--user-data-dir={unique_dir}')

        # 添加更多隔离参数
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument(f'--remote-debugging-port={9222 + random.randint(0, 1000)}')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # 使用系统的ChromeDriver（适配Linux环境）
        try:
            # 尝试使用系统chromedriver
            self.driver = webdriver.Chrome(options=chrome_options)
        except:
            # 如果失败，尝试使用webdriver-manager
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
        
        # 设置日期范围
        self.one_month_ago = (datetime.now() - timedelta(days=30))
    
    # 其他方法保持不变...
    def extract_date(self, date_string):
        """提取和解析日期"""
        try:
            if not date_string:
                return None
                
            date_string = re.sub(r'\s+', ' ', date_string).strip()
            
            date_formats = [
                '%Y-%m-%d',
                '%d %B %Y',
                '%B %d, %Y',
                '%d/%m/%Y',
                '%m/%d/%Y',
                '%Y/%m/%d',
                '%b %d, %Y'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_string, fmt)
                except:
                    continue
                    
            return None
            
        except Exception as e:
            print(f"日期解析错误: {e}")
            return None
    
    def clean_title(self, title):
        """清理标题"""
        if not title:
            return title
            
        date_patterns = [
            r'\d{1,2}\s+\w+\s+\d{4}',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{2}-\d{2}',
            r'\w+\s+\d{1,2},\s+\d{4}'
        ]
        
        for pattern in date_patterns:
            title = re.sub(pattern, '', title)
        
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title
    
    def search_solar_content(self):
        """使用Selenium搜索光伏相关内容"""
        print("正在使用Selenium搜索PV Magazine光伏相关内容...")
        
        # 访问首页获取最新内容
        try:
            print("正在访问首页...")
            self.driver.get(self.base_url)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(3)
            
            # 获取页面内容
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 查找文章链接
            self.find_and_process_articles(soup, "首页")
            
        except Exception as e:
            print(f"访问首页时出错: {e}")
        
        # 尝试访问不同的栏目
        sections = [
            "news",
            "features", 
            "technology",
            "markets",
            "press-releases",
            "energy-storage"
        ]
        
        for section in sections:
            try:
                url = f"{self.base_url}/{section}/"
                print(f"正在访问: {url}")
                
                self.driver.get(url)
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(2)
                
                # 滚动页面以加载更多内容
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                self.find_and_process_articles(soup, section)
                
            except Exception as e:
                print(f"访问 {section} 时出错: {e}")
                continue
    
    def find_and_process_articles(self, soup, section_name):
        """查找并处理文章"""
        print(f"在 {section_name} 中查找文章...")
        
        # 多种可能的选择器
        article_selectors = [
            'article a',
            '.post-title a',
            '.entry-title a',
            '.news-title a',
            '.teaser__title a',
            '.title a',
            'h2 a',
            'h3 a',
            'h1 a',
            '.headline a',
            '.card-title a',
            '.news-item a',
            '.post-item a',
            '.elementor-heading-title a'
        ]
        
        found_count = 0
        for selector in article_selectors:
            try:
                articles = soup.select(selector)
                for article in articles:
                    href = article.get('href')
                    title = article.get_text().strip()
                    
                    if href and title and len(title) > 10:
                        # 构建完整URL
                        if href.startswith('/'):
                            full_url = self.base_url + href
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        
                        # 检查是否光伏相关
                        if self.is_solar_related(title):
                            found_count += 1
                            self.process_article(title, full_url)
                            
            except Exception as e:
                print(f"使用选择器 {selector} 时出错: {e}")
                continue
        
        print(f"在 {section_name} 中找到 {found_count} 篇相关文章")
    
    def is_solar_related(self, title):
        """检查标题是否与光伏相关"""
        solar_keywords = [
            'solar', 'photovoltaic', 'pv', 'renewable', 'battery', 'storage',
            'panel', 'module', 'inverter', 'grid', 'energy', 'clean energy'
        ]
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in solar_keywords)
    
    def process_article(self, title, link):
        """处理单篇文章"""
        try:
            print(f"处理文章: {title[:60]}...")
            
            cleaned_title = self.clean_title(title)
            
            # 从URL中提取日期
            publish_date = self.extract_date_from_url(link)
            
            # 如果没有从URL中提取到日期，尝试访问文章页面
            if not publish_date:
                publish_date = self.extract_date_from_article_page(link)
            
            # 检查日期是否在最近一个月内
            if publish_date and publish_date < self.one_month_ago:
                print(f"跳过旧文章: {cleaned_title[:50]}... - 日期: {publish_date.strftime('%Y-%m-%d')}")
                return
            
            content_type = self.determine_content_type(link, cleaned_title)
            
            content_item = {
                'title': cleaned_title,
                'link': link,
                'content_type': content_type,
                'publish_date': publish_date.strftime('%Y-%m-%d') if publish_date else "日期未知",
                'source': 'PV Magazine'
            }
            
            # 避免重复
            if not any(existing['link'] == content_item['link'] for existing in self.content_data):
                self.content_data.append(content_item)
                print(f"成功添加: {cleaned_title[:50]}... - 类型: {content_type}")
            
        except Exception as e:
            print(f"处理文章时出错: {e}")
    
    def extract_date_from_url(self, url):
        """从URL中提取日期"""
        try:
            # PV Magazine的URL格式通常是: /YYYY/MM/DD/article-title/
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if date_match:
                year, month, day = date_match.groups()
                date_str = f"{year}-{month}-{day}"
                return self.extract_date(date_str)
            return None
        except:
            return None
    
    def extract_date_from_article_page(self, url):
        """从文章页面提取日期"""
        try:
            print(f"访问文章页面提取日期: {url}")
            self.driver.get(url)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)
            
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 查找日期元素
            date_selectors = [
                'time',
                '.date',
                '.post-date', 
                '.publish-date',
                '.entry-date',
                '.article-date',
                '.meta-date',
                '.single__date',
                '.post-meta-date',
                '.published'
            ]
            
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date_str = date_elem.get_text().strip()
                    date = self.extract_date(date_str)
                    if date:
                        return date
                    
                    # 检查datetime属性
                    datetime_attr = date_elem.get('datetime')
                    if datetime_attr:
                        date = self.extract_date(datetime_attr)
                        if date:
                            return date
            
            # 查找元数据
            meta_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="publish_date"]',
                'meta[property="og:published_time"]',
                'meta[name="date"]'
            ]
            
            for selector in meta_selectors:
                meta_elem = soup.select_one(selector)
                if meta_elem and meta_elem.get('content'):
                    date_str = meta_elem['content']
                    date = self.extract_date(date_str)
                    if date:
                        return date
            
            return None
            
        except Exception as e:
            print(f"从文章提取日期时出错 {url}: {e}")
            return None
    
    def determine_content_type(self, url, title):
        """根据URL和标题确定内容类型"""
        url_lower = url.lower()
        title_lower = title.lower()
        
        if 'press-release' in url_lower or 'press' in title_lower:
            return 'press_release'
        elif 'feature' in url_lower or 'analysis' in title_lower:
            return 'feature'
        elif 'technology' in url_lower or 'tech' in title_lower or 'research' in title_lower:
            return 'technology'
        elif 'market' in url_lower or any(word in title_lower for word in ['market', 'price', 'finance', 'investment']):
            return 'market_analysis'
        elif 'storage' in url_lower or 'battery' in title_lower:
            return 'energy_storage'
        else:
            return 'news'
    
    def save_to_json(self):
        """保存数据到JSON文件"""
        if not self.content_data:
            print("没有找到符合条件的数据")
            return None
            
        output_dir = "output/pv_magazine"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        filename = f"pv_magazine_selenium_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(self.content_data, jsonfile, ensure_ascii=False, indent=2)
            
            print(f"数据已保存到 {filepath}")
            print(f"共找到 {len(self.content_data)} 条内容")
            
            # 显示结果预览
            if self.content_data:
                print("\n前5条结果预览:")
                for i, item in enumerate(self.content_data[:5]):
                    print(f"{i+1}. {item['title']}")
                    print(f"   日期: {item['publish_date']}")
                    print(f"   类型: {item['content_type']}")
                    print()
            
            return filepath
            
        except Exception as e:
            print(f"保存JSON文件时出错: {e}")
            return None
    
    def close(self):
        """关闭浏览器"""
        self.driver.quit()

def main():
    print("开始使用Selenium爬取PV Magazine光伏内容...")
    crawler = PVMagazineSeleniumCrawler()
    
    try:
        crawler.search_solar_content()
        
        json_file = crawler.save_to_json()
        
        if json_file:
            print(f"爬取完成！JSON文件已保存为: {json_file}")
        else:
            print("爬取完成，但未生成JSON文件。")
        
    except Exception as e:
        print(f"爬取过程中出错: {e}")
    
    finally:
        crawler.close()
    
    print("程序执行完毕!")

if __name__ == "__main__":
    main()