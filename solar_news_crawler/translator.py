import json
import os
import time
import hashlib
import requests
from datetime import datetime
import glob

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

class MultiFileTranslator:
    def __init__(self):
        self.cache_file = 'translation_cache.json'
        self.translation_cache = self._load_cache()
        
    def _load_cache(self):
        """加载翻译缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_cache(self):
        """保存翻译缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.translation_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def _get_cache_key(self, text):
        """生成缓存键"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def translate_text(self, text):
        """使用免费的翻译服务"""
        if not text or not text.strip():
            return text
            
        # 检查缓存
        cache_key = self._get_cache_key(text)
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        # 尝试多个免费的翻译服务
        translation_methods = [
            self._libretranslate_translate,
            self._mymemory_translate,
            self._simply_translate
        ]
        
        for method in translation_methods:
            try:
                result = method(text)
                if result and result.strip() and result != text:
                    # 缓存结果
                    self.translation_cache[cache_key] = result
                    self._save_cache()
                    return result
            except Exception as e:
                print(f"翻译方法 {method.__name__} 失败: {e}")
                continue
        
        return text
    
    def _libretranslate_translate(self, text):
        """使用LibreTranslate（开源翻译服务）"""
        try:
            # 多个可用的LibreTranslate实例
            endpoints = [
                "https://translate.argosopentech.com/translate",
                "https://libretranslate.de/translate",
                "https://translate.fortran.is/translate"
            ]
            
            for endpoint in endpoints:
                try:
                    data = {
                        'q': text,
                        'source': 'en',
                        'target': 'zh',
                        'format': 'text'
                    }
                    
                    response = requests.post(endpoint, json=data, timeout=15)
                    if response.status_code == 200:
                        result = response.json()
                        return result['translatedText']
                except:
                    continue
                    
            return None
        except Exception as e:
            print(f"LibreTranslate失败: {e}")
            return None
    
    def _mymemory_translate(self, text):
        """使用MyMemory翻译API（免费）"""
        try:
            url = "https://api.mymemory.translated.net/get"
            params = {
                'q': text,
                'langpair': 'en|zh'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('responseStatus') == 200:
                    return data['responseData']['translatedText']
        except Exception as e:
            print(f"MyMemory翻译失败: {e}")
        return None
    
    def _simply_translate(self, text):
        """使用SimplyTranslate（另一个开源服务）"""
        try:
            url = "https://simplytranslate.org/api/translate"
            data = {
                'text': text,
                'from': 'en',
                'to': 'zh'
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                return response.text.strip()
        except Exception as e:
            print(f"SimplyTranslate失败: {e}")
        return None

    def process_pv_magazine_file(self, filename):
        """处理PV Magazine格式的文件"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"处理PV Magazine文件: {filename}")
            print(f"找到 {len(data)} 条新闻")
            
            processed_news = []
            for i, item in enumerate(data):
                print(f"处理进度: {i+1}/{len(data)}")
                
                # 翻译标题
                original_title = item.get('title', '')
                translated_title = self.translate_text(original_title)
                
                # 构建标准化格式
                news_item = {
                    'title_original': original_title,
                    'title_translated': translated_title,
                    'link': item.get('link', ''),
                    'publish_date': item.get('publish_date', ''),
                    'source': 'PV Magazine',
                    'content_type': item.get('content_type', 'news'),
                    'file_source': os.path.basename(filename)
                }
                
                processed_news.append(news_item)
                print(f"  ✓ PV Magazine: {original_title[:60]}...")
                
                # 避免请求过于频繁
                time.sleep(2)
            
            return processed_news
            
        except Exception as e:
            print(f"❌ 处理PV Magazine文件失败: {e}")
            return []

    def process_irena_file(self, filename):
        """处理IRENA格式的文件"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            print(f"处理IRENA文件: {filename}")

            # 支持两种格式：字典格式 {"news_list": [...]} 和数组格式 [...]
            if isinstance(data, dict) and 'news_list' in data:
                news_list = data['news_list']
            elif isinstance(data, list):
                news_list = data
            else:
                print("❌ IRENA文件格式不符合预期")
                return []

            print(f"找到 {len(news_list)} 条新闻")

            processed_news = []
            for i, item in enumerate(news_list):
                print(f"处理进度: {i+1}/{len(news_list)}")

                # 翻译标题
                original_title = item.get('title', '')
                translated_title = self.translate_text(original_title)

                # 构建标准化格式
                news_item = {
                    'title_original': original_title,
                    'title_translated': translated_title,
                    'link': item.get('link', ''),
                    'publish_date': item.get('date', ''),
                    'source': 'IRENA',
                    'summary': item.get('summary', ''),
                    'category': item.get('category', ''),
                    'language': item.get('language', ''),
                    'file_source': os.path.basename(filename)
                }

                processed_news.append(news_item)
                print(f"  ✓ IRENA: {original_title[:60]}...")

                # 避免请求过于频繁
                time.sleep(2)

            return processed_news

        except Exception as e:
            print(f"❌ 处理IRENA文件失败: {e}")
            return []

    def process_iea_file(self, filename):
        """处理IEA格式的文件"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"处理IEA文件: {filename}")
            print(f"找到 {len(data)} 条新闻")
            
            processed_news = []
            for i, item in enumerate(data):
                print(f"处理进度: {i+1}/{len(data)}")
                
                # 翻译标题
                original_title = item.get('title', '')
                translated_title = self.translate_text(original_title)
                
                # 构建标准化格式
                news_item = {
                    'title_original': original_title,
                    'title_translated': translated_title,
                    'link': item.get('link', ''),
                    'publish_date': item.get('publish_date', ''),
                    'source': 'IEA',
                    'content_type': item.get('content_type', 'news'),
                    'file_source': os.path.basename(filename)
                }
                
                processed_news.append(news_item)
                print(f"  ✓ IEA: {original_title[:60]}...")
                
                # 避免请求过于频繁
                time.sleep(2)
            
            return processed_news
            
        except Exception as e:
            print(f"❌ 处理IEA文件失败: {e}")
            return []

    def merge_and_save_translations(self):
        """合并所有翻译结果并保存（带时间戳）"""
        all_news = []
        
        # 定义要处理的文件
        files_to_process = [
            {
                'filename': find_latest_file('pvmagazine_*.json'),
                'processor': self.process_pv_magazine_file,
                'source': 'PV Magazine'
            },
            {
                'filename': find_latest_file('irena_*.json'),
                'processor': self.process_irena_file,
                'source': 'IRENA'
            },
            {
                'filename': find_latest_file('iea_*.json'),
                'processor': self.process_iea_file,
                'source': 'IEA'
            }
        ]
        
        total_translated = 0
        
        for file_info in files_to_process:
            filename = file_info['filename']
            processor = file_info['processor']
            source = file_info['source']
            
            if filename and os.path.exists(filename):
                print(f"\n{'='*50}")
                print(f"开始处理 {source} 文件: {os.path.basename(filename)}")
                print(f"{'='*50}")
                
                news_items = processor(filename)
                all_news.extend(news_items)
                total_translated += len(news_items)
                
                print(f"✅ {source} 处理完成: {len(news_items)} 条新闻")
            else:
                print(f"❌ 文件不存在: {filename}")
    
    # 构建最终输出结构
        output_data = {
            'merge_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_news': len(all_news),
            'total_translated': total_translated,
            'sources': {
                'PV Magazine': len([n for n in all_news if n['source'] == 'PV Magazine']),
                'IRENA': len([n for n in all_news if n['source'] == 'IRENA']),
                'IEA': len([n for n in all_news if n['source'] == 'IEA'])
            },
            'news_list': all_news
        }
    
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"translator_{timestamp}.json"
        output_filepath = output_filename
    
        # 保存合并后的文件
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
    
        print(f"\n{'='*50}")
        print(f"🎉 所有文件翻译合并完成！")
        print(f"📊 总计: {len(all_news)} 条新闻")
        print(f"📊 按来源统计:")
        for source, count in output_data['sources'].items():
            print(f"   {source}: {count} 条")
        print(f"💾 保存到: {output_filepath}")
        print(f"{'='*50}")
    
        return output_filepath

def main():
    translator = MultiFileTranslator()
    
    # 合并翻译所有文件
    output_file = translator.merge_and_save_translations()
    
    if output_file:
        print(f"\n🎉 所有文件翻译合并完成！")
        print(f"📁 输出文件: {output_file}")
        print("现在你可以在最新的 translator_*.json 文件中查看所有翻译后的内容。")
    else:
        print("\n❌ 翻译合并过程中出现错误。")

if __name__ == '__main__':
    main()