import sys
import os
import json
import time
import re
import random
import tempfile
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.common.action_chains import ActionChains
    
    class CombinedSolarCrawler:
        def __init__(self):
            self.gov_search_url = "https://sousuo.www.gov.cn/sousuo/search.shtml"
            self.nea_search_url = "https://www.nea.gov.cn/search.htm"
            self.driver = None
            
        def setup_driver(self):
            """设置浏览器环境"""
            chrome_options = Options()

            # 使用无头模式
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')

            # 反检测配置
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # 不使用user-data-dir，让Chrome自动处理（避免冲突）
            # unique_dir = os.path.join(tempfile.gettempdir(), f"chrome_combined_{uuid.uuid4().hex}")
            # chrome_options.add_argument(f'--user-data-dir={unique_dir}')

            # 添加更多隔离参数
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'--remote-debugging-port={9222 + random.randint(0, 1000)}')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_argument('--window-size=1920,1080')
            
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                return True
            except Exception as e:
                print(f"❌ 浏览器启动失败: {e}")
                return False
        
        def close_driver(self):
            """关闭浏览器"""
            if self.driver:
                self.driver.quit()
                self.driver = None

        def crawl_all_sources(self, pages=5):
            """爬取所有数据源"""
            all_news = []
            
            # 1. 中国政府网 - 多个关键词
            gov_keywords = ['光伏', '太阳能', '新能源', '能源', '电力', '环保', '可持续发展']
            for keyword in gov_keywords:
                print(f"\n🔍 开始爬取中国政府网关键词: '{keyword}'")
                gov_news = self.crawl_gov_news(keyword, pages=3)
                all_news.extend(gov_news)
                time.sleep(2)
            
            # 2. 国家能源局 - 多个关键词
            print(f"\n🔍 开始爬取国家能源局")
            nea_news = self.crawl_nea_news(pages=pages)
            all_news.extend(nea_news)
            
            return all_news

        def crawl_gov_news(self, keyword="光伏", pages=5):
            """爬取中国政府网新闻"""
            if not self.driver and not self.setup_driver():
                return []
            
            all_news = []
            
            try:
                # 构建初始搜索URL
                initial_url = f"{self.gov_search_url}?code=17da70961a7&dataTypeId=107&searchWord={quote(keyword)}"
                print(f"   访问初始URL: {initial_url}")
                
                self.driver.get(initial_url)
                
                # 等待页面加载
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                time.sleep(5)
                
                # 提取第一页数据
                page_news = self.extract_gov_news(keyword)
                all_news.extend(page_news)
                print(f"   ✅ 第 1 页找到 {len(page_news)} 条新闻")
                
                # 显示前3条新闻标题
                for i, news in enumerate(page_news[:3]):
                    print(f"      {i+1}. {news['title'][:50]}...")
                
                # 模拟点击翻页获取后续页面
                for page in range(2, pages + 1):
                    print(f"🔍 正在获取第 {page} 页...")
                    
                    if self.click_gov_next_page():
                        time.sleep(4)
                        
                        page_news = self.extract_gov_news(keyword)
                        all_news.extend(page_news)
                        
                        print(f"   ✅ 第 {page} 页找到 {len(page_news)} 条新闻")
                        
                        # 显示前3条新闻标题
                        for i, news in enumerate(page_news[:3]):
                            print(f"      {i+1}. {news['title'][:50]}...")
                        
                        if page < pages:
                            delay = random.uniform(2, 4)
                            time.sleep(delay)
                    else:
                        print(f"   ❌ 第 {page} 页翻页失败，停止爬取")
                        break
                
                return all_news
                
            except Exception as e:
                print(f"❌ 中国政府网爬取失败: {e}")
                return []
        
        def click_gov_next_page(self):
            """模拟点击中国政府网下一页按钮"""
            try:
                # 多种下一页按钮选择器
                next_selectors = [
                    "a.next",
                    ".next-page", 
                    "li.next > a",
                    "div.page > a:last-child",
                    "//a[contains(text(), '下一页')]",
                    "//a[contains(text(), '>')]",
                    "//a[contains(@class, 'next')]"
                ]
                
                for selector in next_selectors:
                    try:
                        if selector.startswith("//"):
                            next_buttons = self.driver.find_elements(By.XPATH, selector)
                        else:
                            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        for button in next_buttons:
                            if button.is_displayed() and button.is_enabled():
                                print(f"   找到下一页按钮: {button.text}")
                                
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                                time.sleep(1)
                                
                                actions = ActionChains(self.driver)
                                actions.move_to_element(button).click().perform()
                                
                                print("   ✅ 成功点击下一页")
                                return True
                    except:
                        continue
                
                # 尝试查找页码链接
                print("   尝试查找页码链接...")
                page_links = self.driver.find_elements(By.CSS_SELECTOR, "a.page, .page a, li a, .pagination a")
                current_page = self.get_current_page()
                
                for link in page_links:
                    try:
                        link_text = link.text.strip()
                        if link_text.isdigit() and int(link_text) == current_page + 1:
                            if link.is_displayed() and link.is_enabled():
                                print(f"   找到页码链接: {link_text}")
                                
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
                                time.sleep(1)
                                
                                actions = ActionChains(self.driver)
                                actions.move_to_element(link).click().perform()
                                
                                print("   ✅ 成功点击页码链接")
                                return True
                    except:
                        continue
                
                print("   ❌ 未找到有效的下一页按钮")
                return False
                
            except Exception as e:
                print(f"   ❌ 翻页失败: {e}")
                return False

        def crawl_nea_news(self, pages=5):
            """爬取国家能源局新闻"""
            if not self.driver and not self.setup_driver():
                return []
            
            all_news = []
            
            try:
                # 国家能源局多个关键词
                nea_keywords = ['光伏', '太阳能', '新能源', '能源', '电力', '环保', '碳达峰', '碳中和']
                
                for keyword in nea_keywords:
                    print(f"\n🔍 开始搜索国家能源局关键词: '{keyword}'")
                    
                    encoded_keyword = quote(keyword, encoding='utf-8')
                    search_url = f"{self.nea_search_url}?kw={encoded_keyword}"
                    
                    print(f"   访问URL: {search_url}")
                    
                    self.driver.get(search_url)
                    
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    time.sleep(6)
                    
                    # 提取当前关键词的新闻
                    keyword_news = self.extract_nea_news(keyword)
                    all_news.extend(keyword_news)
                    
                    print(f"   ✅ 关键词 '{keyword}' 找到 {len(keyword_news)} 条新闻")
                    
                    # 显示前3条新闻标题
                    for i, news in enumerate(keyword_news[:3]):
                        print(f"      {i+1}. {news['title'][:50]}...")
                    
                    # 关键词间延迟
                    if keyword != nea_keywords[-1]:
                        time.sleep(3)
                
                return all_news
                
            except Exception as e:
                print(f"❌ 国家能源局爬取失败: {e}")
                return []
        
        def extract_nea_news(self, keyword):
            """提取国家能源局新闻 - 不过滤"""
            news_list = []
            
            try:
                # 获取所有链接
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                print(f"   页面共有 {len(all_links)} 个链接")
                
                for link in all_links:
                    try:
                        title = link.text.strip()
                        href = link.get_attribute('href')
                        
                        # 宽松的过滤条件 - 只排除明显无关的导航链接
                        if (title and len(title) > 8 and 
                            href and ('nea.gov.cn' in href or href.startswith('/')) and
                            not any(word in title for word in ['首页', '上一页', '下一页', '网站', '导航', '更多', '返回'])):
                            
                            # 构建完整URL
                            if href.startswith('/'):
                                full_url = f"https://www.nea.gov.cn{href}"
                            else:
                                full_url = href
                            
                            # 提取日期
                            date = self._extract_date_near_element(link)
                            
                            news_data = {
                                'title': title,
                                'link': full_url,
                                'date': date,
                                'source': '国家能源局',
                                'keyword': keyword
                            }
                            
                            # 去重检查
                            if not any(n['title'] == title for n in news_list):
                                news_list.append(news_data)
                                
                    except:
                        continue
                
                print(f"   找到 {len(news_list)} 条国家能源局新闻")
                return news_list
                        
            except Exception as e:
                print(f"   提取国家能源局新闻失败: {e}")
                return []
        
        def extract_gov_news(self, keyword):
            """提取中国政府网新闻内容 - 不过滤"""
            news_list = []
            
            try:
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                print(f"   页面共有 {len(all_links)} 个链接")
                
                for link in all_links:
                    try:
                        title = link.text.strip()
                        href = link.get_attribute('href')
                        
                        # 宽松的过滤条件 - 只排除明显无关的导航链接
                        if (title and len(title) > 8 and 
                            href and 'gov.cn' in href and
                            not any(word in title for word in ['首页', '上一页', '下一页', '网站', '导航', '更多', '>>', '>', '返回'])):
                            
                            date = self._extract_date_near_element(link)
                            
                            news_data = {
                                'title': title,
                                'link': href,
                                'date': date,
                                'source': '中国政府网',
                                'keyword': keyword
                            }
                            
                            if not any(n['title'] == title for n in news_list):
                                news_list.append(news_data)
                                    
                    except:
                        continue
                
                print(f"   找到 {len(news_list)} 条中国政府网新闻")
                return news_list
                        
            except Exception as e:
                print(f"   提取新闻失败: {e}")
                return []
        
        def get_current_page(self):
            """获取当前页码"""
            try:
                active_selectors = [
                    ".page .active", ".current", "li.active a", "span.current"
                ]
                
                for selector in active_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            text = elem.text.strip()
                            if text.isdigit():
                                return int(text)
                    except:
                        continue
                
                return 1
            except:
                return 1
        
        def _extract_date_near_element(self, element):
            """在元素附近提取日期"""
            try:
                parent = element.find_element(By.XPATH, "./..")
                parent_text = parent.text
                
                date_patterns = [
                    r'\d{4}-\d{2}-\d{2}',
                    r'\d{4}年\d{1,2}月\d{1,2}日',
                    r'\d{4}/\d{1,2}/\d{1,2}',
                    r'入库时间：(\d{4}-\d{2}-\d{2})',
                    r'发布时间：(\d{4}-\d{2}-\d{2})'
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, parent_text)
                    if match:
                        date_str = match.group(1) if len(match.groups()) > 0 else match.group()
                        date_str = re.sub(r'[年月/]', '-', date_str.replace('日', ''))
                        return date_str
                        
                siblings = parent.find_elements(By.XPATH, "./*")
                for sibling in siblings:
                    try:
                        sibling_text = sibling.text
                        for pattern in date_patterns:
                            match = re.search(pattern, sibling_text)
                            if match:
                                date_str = match.group(1) if len(match.groups()) > 0 else match.group()
                                date_str = re.sub(r'[年月/]', '-', date_str.replace('日', ''))
                                return date_str
                    except:
                        continue
            except:
                pass
            
            return datetime.now().strftime('%Y-%m-%d')
        
        def process_and_save_news(self, news_list, filename='combined_news.json'):
            """处理并保存新闻数据"""
            seen_titles = set()
            unique_news = []
            
            for news in news_list:
                clean_title = re.sub(r'\s+', ' ', news['title']).strip()
                if clean_title and clean_title not in seen_titles:
                    seen_titles.add(clean_title)
                    unique_news.append(news)
            
            # 按日期排序
            unique_news.sort(key=lambda x: x['date'], reverse=True)
            
            # 保存到JSON文件
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(unique_news, f, ensure_ascii=False, indent=2)
                print(f"💾 数据已保存到 {filename}，共 {len(unique_news)} 条新闻")
                return True
            except Exception as e:
                print(f"❌ 保存文件失败: {e}")
                return False
        
        def get_news_data(self, pages=5, save_file='combined_news.json'):
            """主方法：获取所有新闻数据"""
            print(f"🚀 开始爬取所有数据源的新闻...")
            
            news_data = self.crawl_all_sources(pages)
            
            if news_data:
                print(f"\n🎉 所有数据源爬取完成！")
                print(f"📊 原始数据总计：{len(news_data)} 条")
                
                # 按来源统计
                gov_count = len([n for n in news_data if n['source'] == '中国政府网'])
                nea_count = len([n for n in news_data if n['source'] == '国家能源局'])
                print(f"   中国政府网: {gov_count} 条")
                print(f"   国家能源局: {nea_count} 条")
                
                # 处理并保存数据
                self.process_and_save_news(news_data, save_file)
                
                print(f"\n📰 前20条最新新闻:")
                for i, news in enumerate(news_data[:20], 1):
                    print(f"{i:2d}. [{news['source']}][{news['date']}] {news['title'][:60]}...")
                
                return news_data
            else:
                print("❌ 没有找到任何新闻数据")
                return []
    
    # 独立运行测试
    def main():
        crawler = CombinedSolarCrawler()
        
        try:
            # 获取所有新闻数据
            news_data = crawler.get_news_data(
                pages=5, 
                save_file='combined_news.json'
            )
            
            return news_data
            
        finally:
            crawler.close_driver()
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请安装Selenium: pip install selenium")