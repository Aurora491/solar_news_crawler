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
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    
    class IrenaCrawler:
        def __init__(self):
            self.irena_url = "https://www.irena.org/News"
            self.driver = None
            self.content_data = []  # 初始化content_data属性，与其他爬虫保持一致
            self.search_keywords = [
                "solar energy",
                "photovoltaic",
                "solar power",
                "renewable energy"
            ]
            
        def _create_chrome_options(self):
            """创建Chrome选项（每次调用都生成新的唯一目录）"""
            chrome_options = Options()

            # 使用无头模式减少资源占用和冲突
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')

            # 修复ChromeDriver权限问题
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # 创建唯一的用户数据目录，避免多实例冲突
            unique_dir = os.path.join(tempfile.gettempdir(), f"chrome_irena_{uuid.uuid4().hex}")
            chrome_options.add_argument(f'--user-data-dir={unique_dir}')

            # 添加更多隔离参数
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument(f'--remote-debugging-port={9222 + random.randint(0, 1000)}')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_argument('--window-size=1920,1080')

            return chrome_options

        def setup_driver(self):
            """设置浏览器环境"""
            try:
                # 自动查找ChromeDriver
                try:
                    self.driver = webdriver.Chrome(options=self._create_chrome_options())
                except Exception as e:
                    print(f"   方法1失败: {e}")
                    # 尝试指定ChromeDriver路径（重新生成options避免目录冲突）
                    try:
                        possible_paths = [
                            "/usr/bin/chromedriver",
                            "/usr/local/bin/chromedriver",
                            "chromedriver"
                        ]

                        for path in possible_paths:
                            if os.path.exists(path):
                                service = Service(executable_path=path)
                                self.driver = webdriver.Chrome(service=service, options=self._create_chrome_options())
                                print(f"   ✅ 使用ChromeDriver路径: {path}")
                                break
                        else:
                            self.driver = webdriver.Chrome(options=self._create_chrome_options())
                    except Exception as e2:
                        print(f"   方法2失败: {e2}")
                        self.driver = webdriver.Chrome(options=self._create_chrome_options())
                
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                return True
                
            except Exception as e:
                print(f"❌ 浏览器启动失败: {e}")
                print("💡 请确保已安装Chrome浏览器和ChromeDriver")
                return False
        
        def close_driver(self):
            """关闭浏览器"""
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
        
        def perform_search_with_load_more(self, keyword, max_loads=5):
            """执行搜索并点击Load more加载更多内容"""
            all_news = []
            
            print(f"\n🔍 搜索关键词: '{keyword}' - 计划加载 {max_loads} 次")
            
            try:
                # 访问新闻页面
                self.driver.get(self.irena_url)
                time.sleep(3)
                
                # 执行搜索
                if self.find_and_use_search(keyword):
                    print(f"   ✅ 搜索 '{keyword}' 成功")
                    time.sleep(4)
                    
                    # 爬取多轮内容
                    for load_count in range(max_loads):
                        current_load = load_count + 1
                        print(f"   📄 第 {current_load} 轮加载...")
                        
                        # 如果是第一次加载，直接提取内容
                        # 如果是后续加载，先点击Load more再提取
                        if load_count > 0:
                            if not self.click_load_more():
                                print(f"   ⏹️ 无法加载更多内容，停止在第 {load_count} 轮")
                                break
                            # 等待新内容加载
                            time.sleep(3)
                        
                        # 提取当前加载的新闻
                        page_news = self.extract_detailed_news()
                        if page_news:
                            # 去重并添加
                            new_count = 0
                            for news in page_news:
                                if not any(n['title'] == news['title'] for n in all_news):
                                    news['search_keyword'] = keyword
                                    news['load_round'] = current_load
                                    all_news.append(news)
                                    new_count += 1
                            print(f"   ✅ 第 {current_load} 轮找到 {new_count} 条新新闻")
                        else:
                            print(f"   ⚠️ 第 {current_load} 轮未找到新新闻")
                        
                        # 显示当前进度
                        current_progress = self.get_current_progress()
                        if current_progress:
                            print(f"   📊 当前进度: {current_progress}")
                    
                    print(f"   ✅ 已完成 {max_loads} 轮加载")
                    
                else:
                    print(f"   ❌ 搜索 '{keyword}' 失败")
                    
            except Exception as e:
                print(f"   ❌ 搜索 '{keyword}' 过程出错: {e}")
            
            return all_news
        
        def click_load_more(self):
            """点击Load more按钮"""
            try:
                # 多种Load more按钮选择器
                load_more_selectors = [
                    "//button[contains(text(), 'Load more')]",
                    "//a[contains(text(), 'Load more')]",
                    "//div[contains(text(), 'Load more')]",
                    "//span[contains(text(), 'Load more')]",
                    "//*[contains(translate(., 'LOAD MORE', 'load more'), 'load more')]",
                    ".load-more",
                    "[class*='load-more']",
                    "button[class*='load']",
                    "a[class*='load']"
                ]
                
                for selector in load_more_selectors:
                    try:
                        if selector.startswith("//"):
                            elements = self.driver.find_elements(By.XPATH, selector)
                        else:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                print(f"   ✅ 找到Load more按钮: {selector}")
                                # 滚动到元素位置
                                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                                time.sleep(1)
                                # 点击按钮
                                self.driver.execute_script("arguments[0].click();", element)
                                print("   ✅ 已点击Load more按钮")
                                return True
                    except Exception as e:
                        continue
                
                print("   ❌ 未找到Load more按钮")
                return False
                
            except Exception as e:
                print(f"   ❌ 点击Load more失败: {e}")
                return False
        
        def get_current_progress(self):
            """获取当前加载进度（如：You've viewed 25 of 1905 results）"""
            try:
                # 查找进度文本
                progress_selectors = [
                    "//*[contains(text(), 'You') and contains(text(), 'viewed') and contains(text(), 'of') and contains(text(), 'results')]",
                    "//*[contains(text(), 'viewed') and contains(text(), 'of')]",
                    ".search-results-count",
                    ".results-count",
                    "[class*='progress']",
                    "[class*='count']"
                ]
                
                for selector in progress_selectors:
                    try:
                        if selector.startswith("//"):
                            elements = self.driver.find_elements(By.XPATH, selector)
                        else:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        for element in elements:
                            text = element.text.strip()
                            if 'viewed' in text.lower() and 'of' in text.lower():
                                print(f"   📈 加载进度: {text}")
                                return text
                    except:
                        continue
                
                return None
                
            except:
                return None
        
        def find_and_use_search(self, keyword):
            """查找并使用搜索功能"""
            try:
                # 等待页面加载
                time.sleep(3)
                
                # 方法1: 查找明显的搜索输入框
                search_input_selectors = [
                    "input[type='search']",
                    "input[name='search']",
                    "input[placeholder*='search' i]",
                    "input[placeholder*='Search' i]",
                    "#search",
                    ".search-input",
                    "input[type='text']"
                ]
                
                search_input = None
                for selector in search_input_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed():
                                search_input = element
                                print(f"   ✅ 找到搜索输入框: {selector}")
                                break
                        if search_input:
                            break
                    except:
                        continue
                
                if not search_input:
                    print("   ❌ 未找到搜索输入框，尝试其他方法...")
                    # 方法2: 查找所有输入框
                    all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    for input_elem in all_inputs:
                        try:
                            if input_elem.is_displayed() and input_elem.get_attribute('type') in ['text', 'search']:
                                placeholder = input_elem.get_attribute('placeholder') or ''
                                if 'search' in placeholder.lower():
                                    search_input = input_elem
                                    print("   ✅ 通过placeholder找到搜索框")
                                    break
                        except:
                            continue
                
                if search_input:
                    # 清除并输入搜索词
                    search_input.clear()
                    search_input.send_keys(keyword)
                    print(f"   ✅ 已输入搜索词: {keyword}")
                    time.sleep(1)
                    
                    # 查找搜索按钮
                    search_button_selectors = [
                        "button[type='submit']",
                        "input[type='submit']",
                        "button[class*='search']",
                        ".search-btn",
                        "button:contains('Search')",
                        "input[value*='Search' i]"
                    ]
                    
                    search_button = None
                    for selector in search_button_selectors:
                        try:
                            if selector == "button:contains('Search')":
                                # XPath方式查找包含Search文本的按钮
                                buttons = self.driver.find_elements(By.XPATH, "//button[contains(translate(., 'SEARCH', 'search'), 'search')]")
                            else:
                                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            
                            for button in buttons:
                                if button.is_displayed():
                                    search_button = button
                                    print(f"   ✅ 找到搜索按钮: {selector}")
                                    break
                            if search_button:
                                break
                        except:
                            continue
                    
                    # 如果没找到按钮，尝试按回车
                    if search_button:
                        self.driver.execute_script("arguments[0].click();", search_button)
                        print("   ✅ 点击搜索按钮")
                    else:
                        search_input.send_keys(Keys.ENTER)
                        print("   ✅ 按回车执行搜索")
                    
                    time.sleep(4)
                    return True
                else:
                    print("   ❌ 完全找不到搜索框")
                    return False
                    
            except Exception as e:
                print(f"   ❌ 搜索过程出错: {e}")
                return False
        
        def extract_detailed_news(self):
            """提取详细的新闻信息"""
            news_list = []
            
            try:
                # 等待页面加载
                time.sleep(2)
                
                # 多种可能的选择器来查找新闻项目
                news_selectors = [
                    ".news-item",
                    ".article-item",
                    ".search-result",
                    ".result-item",
                    "div[class*='news']",
                    "div[class*='article']",
                    "li[class*='news']",
                    ".listing-item",
                    ".card",
                    ".news-card"
                ]
                
                news_elements = []
                for selector in news_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            news_elements.extend(elements)
                    except:
                        continue
                
                # 如果没有找到特定类名的元素，尝试查找所有包含链接的块级元素
                if not news_elements:
                    all_links = self.driver.find_elements(By.TAG_NAME, "a")
                    link_elements = set()
                    
                    for link in all_links:
                        try:
                            href = link.get_attribute('href')
                            text = link.text.strip()
                            if href and text and len(text) > 20 and 'irena.org' in href:
                                # 获取链接的父级或祖先元素作为新闻项
                                parent = link.find_element(By.XPATH, "./..")
                                link_elements.add(parent)
                        except:
                            continue
                    
                    news_elements = list(link_elements)
                
                print(f"   当前轮次找到 {len(news_elements)} 个可能的新闻元素")
                
                for element in news_elements:
                    try:
                        news_item = self.extract_news_details(element)
                        if news_item and not any(n['title'] == news_item['title'] for n in news_list):
                            news_list.append(news_item)
                                
                    except Exception as e:
                        continue
                
                return news_list
                
            except Exception as e:
                print(f"   ❌ 提取新闻失败: {e}")
                return []
        
        def extract_news_details(self, element):
            """从元素中提取详细的新闻信息"""
            try:
                # 在元素内查找链接
                links = element.find_elements(By.TAG_NAME, "a")
                for link in links:
                    title = link.text.strip()
                    href = link.get_attribute('href')
                    
                    if (title and len(title) > 20 and 
                        href and 'irena.org' in href and
                        self.is_solar_related(title)):
                        
                        # 提取详细信息
                        date = self.extract_date_from_element(element)
                        summary = self.extract_summary_from_element(element)
                        category = self.extract_category_from_title(title)
                        
                        news_item = {
                            'title': title,
                            'link': href,
                            'date': date,
                            'summary': summary,
                            'category': category,
                            'source': 'IRENA',
                            'language': 'en',
                            'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        return news_item
                return None
            except:
                return None
        
        def extract_date_from_element(self, element):
            """从元素中提取日期"""
            try:
                element_text = element.text
                
                # 查找日期模式
                date_patterns = [
                    r'\d{1,2}\s+\w+\s+\d{4}',
                    r'\d{4}-\d{2}-\d{2}',
                    r'\w+\s+\d{1,2},\s+\d{4}',
                    r'\d{1,2}/\d{1,2}/\d{4}'
                ]
                
                for pattern in date_patterns:
                    matches = re.findall(pattern, element_text)
                    if matches:
                        return matches[0]
            except:
                pass
            
            return datetime.now().strftime('%Y-%m-%d')
        
        def extract_summary_from_element(self, element):
            """从元素中提取摘要"""
            try:
                element_text = element.text
                lines = element_text.split('\n')
                
                # 查找可能的摘要行（排除标题和日期）
                for line in lines:
                    line = line.strip()
                    if (len(line) > 50 and len(line) < 300 and 
                        not re.search(r'\d{1,2}\s+\w+\s+\d{4}', line) and
                        not re.search(r'\d{4}-\d{2}-\d{2}', line) and
                        not line.startswith('http')):
                        return line
                
                return ""
                    
            except:
                return ""
        
        def extract_category_from_title(self, title):
            """从标题中提取分类"""
            try:
                title_lower = title.lower()
                
                if any(word in title_lower for word in ['report', 'study', 'analysis']):
                    return 'report'
                elif any(word in title_lower for word in ['news', 'press', 'announcement']):
                    return 'news'
                elif any(word in title_lower for word in ['event', 'conference', 'meeting', 'webinar']):
                    return 'event'
                elif any(word in title_lower for word in ['data', 'statistics', 'figures']):
                    return 'data'
                else:
                    return 'general'
            except:
                return 'general'
        
        def is_solar_related(self, title):
            """判断是否与太阳能相关"""
            if not title:
                return False
                
            title_lower = title.lower()
            solar_keywords = [
                'solar', 'photovoltaic', 'pv', 'renewable energy',
                'solar energy', 'solar power', 'solar panel', 'clean energy',
                'renewables', 'green energy', 'solar technology'
            ]
            
            return any(keyword in title_lower for keyword in solar_keywords)
        
        def crawl_with_load_more(self, loads_per_keyword=5):
            """使用Load more的全面爬取"""
            if not self.driver and not self.setup_driver():
                return []
            
            all_news = []
            
            try:
                print("🚀 开始使用Load more加载更多内容的IRENA光伏新闻爬取...")
                
                # 多关键词搜索，每个关键词点击多次Load more
                for keyword in self.search_keywords:
                    keyword_news = self.perform_search_with_load_more(keyword, max_loads=loads_per_keyword)
                    if keyword_news:
                        all_news.extend(keyword_news)
                        print(f"✅ 关键词 '{keyword}' 共找到 {len(keyword_news)} 条新闻")
                    
                    # 随机延迟，避免请求过快
                    time.sleep(random.uniform(2, 4))
                
                # 去重
                unique_news = []
                seen_titles = set()
                for news in all_news:
                    if news['title'] not in seen_titles:
                        unique_news.append(news)
                        seen_titles.add(news['title'])
                
                print(f"\n🎯 去重后总共找到 {len(unique_news)} 条唯一新闻")
                
                return unique_news
                
            except Exception as e:
                print(f"❌ 爬取过程出错: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        def save_news_data(self, news_list, filename='irena_news_load_more.json'):
            """保存新闻数据"""
            try:
                # 添加统计信息
                output_data = {
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'total_load_rounds': len(set(n.get('load_round', 1) for n in news_list)),
                    'total_news': len(news_list),
                    'news_list': news_list
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)
                print(f"💾 数据已保存到 {filename}")
                return True
            except Exception as e:
                print(f"❌ 保存失败: {e}")
                return False
        
        def create_sample_data(self):
            """创建示例数据"""
            sample_news = [
                {
                    'title': 'IRENA Report: Solar Energy Leads Global Renewable Growth',
                    'link': 'https://www.irena.org/news/articles/2024/solar-energy-growth',
                    'date': '2024-09-15',
                    'summary': 'New report shows solar energy continuing to lead global renewable energy capacity growth.',
                    'source': 'IRENA',
                    'language': 'en',
                    'search_keyword': 'solar energy',
                    'load_round': 1
                }
            ]
            return sample_news
    
    # 独立运行测试
    def main():
        crawler = IrenaCrawler()
        
        try:
            print("=" * 60)
            print("🚀 IRENA光伏新闻Load More爬取开始")
            print("=" * 60)
            
            # 设置加载次数
            loads_to_perform = 5  # 可以调整这个数字来加载更多内容
            
            news_data = crawler.crawl_with_load_more(loads_per_keyword=loads_to_perform)
            
            if news_data:
                print(f"\n🎉 爬取完成！总共找到 {len(news_data)} 条光伏新闻")
                
                # 保存数据
                crawler.save_news_data(news_data)
                
                # 显示统计信息
                load_rounds = set()
                keywords_used = set()
                
                for news in news_data:
                    load_rounds.add(news.get('load_round', 1))
                    keywords_used.add(news.get('search_keyword', 'unknown'))
                
                print(f"\n📊 爬取统计:")
                print(f"   加载轮次: {len(load_rounds)} 轮")
                print(f"   使用关键词: {', '.join(keywords_used)}")
                print(f"   总新闻数: {len(news_data)} 条")
                
                print(f"\n📰 新闻列表 (显示前20条):")
                for i, news in enumerate(news_data[:20], 1):
                    print(f"{i:2d}. [第{news.get('load_round', 1)}轮] [{news['date']}] {news['title']}")
                    if news.get('summary'):
                        print(f"    摘要: {news['summary']}")
                    print()
                
            else:
                print("❌ 没有找到新闻数据，创建示例数据...")
                sample_data = crawler.create_sample_data()
                crawler.save_news_data(sample_data)
                print("✅ 示例数据已创建")
                
            return news_data
            
        finally:
            crawler.close_driver()
            print("\n✅ 程序执行完成")
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请安装Selenium: pip install selenium")