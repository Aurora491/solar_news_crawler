# master_crawler.py
import os
import json
import time
import schedule
from datetime import datetime
from iea_crawler import IEASolarContentCrawler
from pv_magazine_crawler import PVMagazineSeleniumCrawler
from irena_crawler import IrenaCrawler
from combined_crawler import CombinedSolarCrawler

def save_individual_crawler_data(crawler_name, data, output_dir="output/individual"):
    """保存单个爬虫的数据到独立文件"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{crawler_name}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"{crawler_name}数据已保存: {filepath}")
    return filepath

# 在master_crawler.py的run_all_crawlers函数中修改：

def run_all_crawlers():
    """运行所有爬虫并分别保存结果"""
    all_data = []
    individual_files = {}
    
    try:
        print(f"\n=== 开始执行爬虫任务 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        
        # 1. 运行IEA爬虫
        print("\n=== 开始运行IEA爬虫 ===")
        iea_crawler = IEASolarContentCrawler()
        iea_crawler.search_solar_content()
        iea_file = save_individual_crawler_data("iea", iea_crawler.content_data)
        individual_files["iea"] = iea_file
        all_data.extend(iea_crawler.content_data)
        print(f"IEA爬虫完成，获取 {len(iea_crawler.content_data)} 条数据")
        
        # 2. 运行PV Magazine爬虫
        print("\n=== 开始运行PV Magazine爬虫 ===")
        try:
            pvmagazine_crawler = PVMagazineSeleniumCrawler()
            pvmagazine_crawler.search_solar_content()
            pvmagazine_file = save_individual_crawler_data("pvmagazine", pvmagazine_crawler.content_data)
            individual_files["pvmagazine"] = pvmagazine_file
            all_data.extend(pvmagazine_crawler.content_data)
            pvmagazine_crawler.close()
            print(f"PV Magazine爬虫完成，获取 {len(pvmagazine_crawler.content_data)} 条数据")
        except Exception as e:
            print(f"PV Magazine爬虫失败: {e}")
            print("跳过PV Magazine爬虫，继续执行其他爬虫...")
        
        # 3. 运行IRENA爬虫（修复方法名）
        print("\n=== 开始运行IRENA爬虫 ===")
        try:
            irena_crawler = IrenaCrawler()
            # 修复：使用正确的方法名
            if hasattr(irena_crawler, 'crawl_with_load_more'):
                news_data = irena_crawler.crawl_with_load_more(loads_per_keyword=3)
                # 将数据格式统一为content_data
                irena_crawler.content_data = news_data
            elif hasattr(irena_crawler, 'search_solar_content'):
                irena_crawler.search_solar_content()
            else:
                print("IRENA爬虫没有可用的爬取方法")
                news_data = []
            
            irena_file = save_individual_crawler_data("irena", irena_crawler.content_data)
            individual_files["irena"] = irena_file
            all_data.extend(irena_crawler.content_data)
            print(f"IRENA爬虫完成，获取 {len(irena_crawler.content_data)} 条数据")
        except Exception as e:
            print(f"IRENA爬虫失败: {e}")
            print("跳过IRENA爬虫，继续执行其他爬虫...")
        
        # 4. 运行Combined爬虫（修复方法名）
        print("\n=== 开始运行Combined爬虫 ===")
        try:
            combined_crawler = CombinedSolarCrawler()
            # 修复：使用正确的方法名
            if hasattr(combined_crawler, 'get_news_data'):
                news_data = combined_crawler.get_news_data(pages=3)
                # 将数据格式统一为content_data
                combined_crawler.content_data = news_data
            elif hasattr(combined_crawler, 'search_solar_content'):
                combined_crawler.search_solar_content()
            else:
                print("Combined爬虫没有可用的爬取方法")
                news_data = []
            
            combined_file = save_individual_crawler_data("combined", combined_crawler.content_data)
            individual_files["combined"] = combined_file
            all_data.extend(combined_crawler.content_data)
            print(f"Combined爬虫完成，获取 {len(combined_crawler.content_data)} 条数据")
        except Exception as e:
            print(f"Combined爬虫失败: {e}")
            print("跳过Combined爬虫...")
        
        print(f"\n=== 所有爬虫任务完成 ===")
        print(f"总计获取 {len(all_data)} 条内容")
        print("各爬虫文件:")
        for name, filepath in individual_files.items():
            print(f"  - {name}: {filepath}")
        
        return {
            "individual_files": individual_files,
            "total_count": len(all_data)
        }
        
    except Exception as e:
        print(f"爬虫执行出错: {e}")
        return {}

def setup_scheduler():
    """设置定时任务 - 每小时执行一次用于测试"""
    # 每小时执行一次（测试用）
    schedule.every().hour.do(run_all_crawlers)
    
    print("定时任务已设置，每小时自动运行（测试模式）")
    print("程序持续运行中...")

def run_scheduler():
    """运行调度器"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次

if __name__ == "__main__":
    import sys
    
    # 支持命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "now":
            # 立即运行一次
            run_all_crawlers()
        elif sys.argv[1] == "daily":
            # 设置为每日运行模式
            schedule.clear()
            schedule.every().day.at("09:00").do(run_all_crawlers)
            print("已设置为每日上午9点运行模式")
            run_scheduler()
        else:
            print("Usage:")
            print("  python master_crawler.py now     # 立即运行一次")
            print("  python master_crawler.py daily   # 设置为每日运行")
            print("  python master_crawler.py         # 默认每小时运行（测试）")
    else:
        # 默认：设置定时任务（每小时运行，测试用）
        setup_scheduler()
        run_scheduler()