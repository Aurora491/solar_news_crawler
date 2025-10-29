import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import re
import os

class IEASolarContentCrawler:
    def __init__(self):
        self.base_url = "https://www.iea.org"
        self.content_data = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 设置日期范围
        self.one_month_ago = (datetime.now() - timedelta(days=30))
        self.five_years_ago = (datetime.now() - timedelta(days=5*365))
        
        # 定义内容类型关键词
        self.content_types = {
            'news': ['/news/', '/articles/', '/updates/'],
            'reports': ['/reports/', '/publications/', '/report/'],
            'data': ['/data-and-statistics/', '/data/', '/statistics/'],
            'policies': ['/policies/', '/policy/'],
            'analysis': ['/analysis/', '/commentary/'],
            'events': ['/events/', '/calendar/'],
            'topics': ['/topics/', '/energy-system/']
        }
        
        # 需要过滤的非具体内容页面模式
        self.filter_patterns = [
            '/energy-system/',
            '/data-and-statistics/data-product/',
            '/data-and-statistics/data-sets/',
            '/data-and-statistics/data-explorers/',
            '/data-and-statistics/chart-library/',
            '/about/',
            '/contact/'
        ]
        
    def extract_date(self, date_string):
        """提取和解析日期"""
        try:
            if date_string == "N/A" or not date_string:
                return None
                
            # 清理日期字符串
            date_string = re.sub(r'\s+', ' ', date_string).strip()
            
            # 尝试多种日期格式
            date_formats = [
                '%Y-%m-%d',
                '%d %B %Y',
                '%B %d, %Y',
                '%d/%m/%Y',
                '%m/%d/%Y',
                '%Y/%m/%d'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_string, fmt)
                except:
                    continue
                    
            # 如果标准格式都不行，尝试从字符串中提取日期部分
            date_patterns = [
                r'(\d{4}-\d{2}-\d{2})',
                r'(\d{1,2}\s+\w+\s+\d{4})',
                r'(\w+\s+\d{1,2},\s+\d{4})',
                r'(\d{1,2}/\d{1,2}/\d{4})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, date_string)
                if match:
                    date_str = match.group(1)
                    for fmt in date_formats:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except:
                            continue
                            
            print(f"无法解析日期: {date_string}")
            return None
            
        except Exception as e:
            print(f"日期解析错误: {e}")
            return None
    
    def get_content_type(self, url):
        """根据URL确定内容类型"""
        for content_type, patterns in self.content_types.items():
            for pattern in patterns:
                if pattern in url:
                    return content_type
        return "other"
    
    def should_filter_url(self, url):
        """判断URL是否应该被过滤"""
        # 检查URL是否包含过滤模式
        for pattern in self.filter_patterns:
            if pattern in url:
                return True
        
        # 检查是否是数据产品页面（不是具体内容）
        if '/data-and-statistics/data-product/' in url:
            return True
            
        return False
    
    def clean_title(self, title):
        """清理标题，移除日期和其他无关信息"""
        if not title:
            return title
            
        # 移除日期模式
        date_patterns = [
            r'\d{1,2}\s+\w+\s+\d{4}',  # 22 September 2025
            r'\d{1,2}/\d{1,2}/\d{4}',   # 22/09/2025
            r'\d{4}-\d{2}-\d{2}',       # 2025-09-22
            r'\d{1,2}:\d{2}—\d{1,2}:\d{2}',  # 14:30—15:30
            r'\d{1,2}\s+\w+\s+\d{4}\s+\d{1,2}:\d{2}—\d{1,2}:\d{2}'  # 19 Jul 2022 14:30—15:30
        ]
        
        for pattern in date_patterns:
            title = re.sub(pattern, '', title)
        
        # 移除常见的关键词
        keywords_to_remove = [
            'News',
            'Calendar',
            'Report launch',
            'Special Report',
            'Public Webinar'
        ]
        
        for keyword in keywords_to_remove:
            title = title.replace(keyword, '')
        
        # 清理多余的换行符和空格
        title = re.sub(r'\s+', ' ', title).strip()
        
        # 移除首尾的标点符号
        title = re.sub(r'^[^\w]+|[^\w]+$', '', title)
        
        return title
    
    def search_solar_content(self):
        """搜索光伏相关内容"""
        print("正在搜索IEA光伏相关内容...")
        
        # 尝试多个可能的内容页面
        search_urls = [
            "https://www.iea.org/news",
            "https://www.iea.org/reports",
            "https://www.iea.org/data-and-statistics",
            "https://www.iea.org/policies",
            "https://www.iea.org/search?q=solar",
            "https://www.iea.org/search?q=photovoltaic",
            "https://www.iea.org/search?q=PV"
        ]
        
        for url in search_urls:
            try:
                print(f"正在访问: {url}")
                self.crawl_content_page(url)
                time.sleep(2)  # 礼貌性延迟
            except Exception as e:
                print(f"爬取 {url} 时出错: {e}")
                continue
    
    def crawl_content_page(self, url):
        """爬取内容页面"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 查找所有可能的内容链接
            content_links = self.find_content_links(soup)
            
            print(f"找到 {len(content_links)} 个内容链接")
            
            # 处理每个内容链接
            for title, link in content_links:
                try:
                    self.process_content_link(title, link)
                except Exception as e:
                    print(f"处理内容链接时出错: {e}")
                    continue
                    
        except Exception as e:
            print(f"爬取内容页面时出错: {e}")
    
    def find_content_links(self, soup):
        """查找内容链接"""
        content_links = []
        
        # 查找所有链接
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link['href']
            title = link.get_text().strip()
            
            # 过滤条件：标题长度和关键词
            if len(title) > 10 and any(keyword in title.lower() for keyword in ['solar', 'photovoltaic', 'pv', 'renewable']):
                
                # 构建完整URL
                if href.startswith('/'):
                    full_url = self.base_url + href
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                
                # 过滤非具体内容页面
                if self.should_filter_url(full_url):
                    continue
                    
                content_links.append((title, full_url))
        
        # 去重
        return list(set(content_links))
    
    def process_content_link(self, title, link):
        """处理单个内容链接"""
        try:
            print(f"处理内容: {title}")
            
            # 获取内容类型
            content_type = self.get_content_type(link)
            
            # 过滤掉"other"类型的内容
            if content_type == "other":
                print(f"跳过其他类型内容: {title}")
                return
            
            # 清理标题
            cleaned_title = self.clean_title(title)
            
            # 直接从详情页提取日期
            publish_date = self.extract_date_from_page(link)
            
            # 根据内容类型应用日期筛选
            if content_type == 'news' and publish_date and publish_date < self.one_month_ago:
                print(f"跳过旧新闻: {cleaned_title} - 日期: {publish_date.strftime('%Y-%m-%d')}")
                return
            elif content_type == 'policies' and publish_date and publish_date < self.five_years_ago:
                print(f"跳过旧政策: {cleaned_title} - 日期: {publish_date.strftime('%Y-%m-%d')}")
                return
            
            content_item = {
                'title': cleaned_title,
                'link': link,
                'content_type': content_type,
                'publish_date': publish_date.strftime('%Y-%m-%d') if publish_date else "日期未知"
            }
            
            # 避免重复
            if not any(existing['link'] == content_item['link'] for existing in self.content_data):
                self.content_data.append(content_item)
                print(f"成功添加内容: {cleaned_title} - 类型: {content_type} - 发布日期: {content_item['publish_date']}")
            
        except Exception as e:
            print(f"处理内容链接时出错: {e}")
    
    def extract_date_from_page(self, url):
        """从页面提取日期"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 方法1: 查找时间元素
            time_elem = soup.find('time')
            if time_elem and time_elem.get('datetime'):
                date = self.extract_date(time_elem['datetime'])
                if date:
                    return date
            
            # 方法2: 查找IEA特有的元数据区域
            meta_selectors = [
                '.o-hero-freepage__meta',  # 政策页面的元数据
                '.hero__meta',
                '.page-meta',
                '.content-meta',
                '.publication-meta',
                '.article-meta'
            ]
            
            for selector in meta_selectors:
                meta_elems = soup.select(selector)
                for meta_elem in meta_elems:
                    meta_text = meta_elem.get_text().strip()
                    # 从元数据文本中提取日期
                    date = self.extract_date_from_meta_text(meta_text)
                    if date:
                        return date
            
            # 方法3: 查找其他日期类元素
            date_selectors = [
                '.date', '.publish-date', '.post-date', '.news-date',
                '.timestamp', '.time', '.article-date', '.event-date',
                '.report-date', '.data-date', '.publication-date',
                '.meta-date', '.content-date'
            ]
            
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date_str = date_elem.get_text().strip()
                    date = self.extract_date(date_str)
                    if date:
                        return date
            
            # 方法4: 在页面元数据中查找
            meta_selectors = [
                'meta[property="article:published_time"]',
                'meta[property="og:published_time"]',
                'meta[name="publish_date"]',
                'meta[name="publication_date"]'
            ]
            
            for selector in meta_selectors:
                meta_elem = soup.select_one(selector)
                if meta_elem and meta_elem.get('content'):
                    date = self.extract_date(meta_elem['content'])
                    if date:
                        return date
            
            # 方法5: 在页面头部区域查找日期
            header_selectors = ['.header', '.page-header', '.content-header']
            for selector in header_selectors:
                header_elem = soup.select_one(selector)
                if header_elem:
                    header_text = header_elem.get_text()
                    date = self.extract_date_from_meta_text(header_text)
                    if date:
                        return date
            
            # 方法6: 对于政策页面，特别查找"Last updated"文本
            if url and '/policies/' in url:
                # 在整个页面中查找"Last updated"文本
                full_text = soup.get_text()
                last_updated_match = re.search(r'Last updated:\s*([^\n]+)', full_text, re.IGNORECASE)
                if last_updated_match:
                    date_str = last_updated_match.group(1).strip()
                    date = self.extract_date(date_str)
                    if date:
                        return date
            
            return None
            
        except Exception as e:
            print(f"从页面提取日期时出错 {url}: {e}")
            return None
    
    def extract_date_from_meta_text(self, text):
        """从元数据文本中提取日期"""
        # 查找包含日期关键词的文本模式
        date_patterns = [
            r'Last updated:\s*([^\n]+)',
            r'Published:\s*([^\n]+)',
            r'Date:\s*([^\n]+)',
            r'Publication date:\s*([^\n]+)',
            r'Release date:\s*([^\n]+)',
            r'Updated:\s*([^\n]+)'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                date = self.extract_date(date_str)
                if date:
                    return date
        
        # 如果没有找到特定模式，直接尝试从文本中提取日期
        date = self.extract_date(text)
        if date:
            return date
            
        return None
    
    def save_to_json(self):
        """保存数据到JSON文件"""
        if not self.content_data:
            print("没有找到符合条件的数据")
            return
            
        # 确保输出目录存在
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        filename = f"IEA_solar_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(output_dir, filename)
        
        try:
            # 过滤掉content_type为"other"的记录
            filtered_data = [item for item in self.content_data if item['content_type'] != 'other']
            
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(filtered_data, jsonfile, ensure_ascii=False, indent=2)
            
            print(f"数据已保存到 {filepath}")
            print(f"共找到 {len(filtered_data)} 条内容 (过滤后)")
            
            # 显示结果预览
            self.preview_results(filtered_data)
            
            return filepath
            
        except Exception as e:
            print(f"保存JSON文件时出错: {e}")
            return None
    
    def preview_results(self, data=None):
        """显示结果预览"""
        if data is None:
            data = self.content_data
            
        if data:
            print("\n结果预览:")
            for i, item in enumerate(data[:5]):  # 只显示前5条
                print(f"{i+1}. 标题: {item['title']}")
                print(f"   类型: {item['content_type']}")
                print(f"   发布日期: {item['publish_date']}")
                print(f"   链接: {item['link']}")
                print()

def main():
    print("开始爬取IEA光伏相关内容...")
    crawler = IEASolarContentCrawler()
    
    try:
        # 搜索光伏相关内容
        crawler.search_solar_content()
        
        # 保存数据到JSON
        json_file = crawler.save_to_json()
        
        if json_file:
            print(f"\n爬取完成！JSON文件已保存为: {json_file}")
            print("您可以使用文本编辑器或JSON查看器打开此文件查看完整数据。")
        else:
            print("爬取完成，但未生成JSON文件。")
        
    except Exception as e:
        print(f"爬取过程中出错: {e}")
    
    print("程序执行完毕!")

if __name__ == "__main__":
    main()