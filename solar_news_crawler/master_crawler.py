# master_crawler.py
import os
import json
import time
import schedule
import shutil
import glob
import subprocess
import sys
from datetime import datetime

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

def cleanup_chrome_temp():
    """清理Chrome临时文件，避免多实例冲突"""
    try:
        import tempfile
        temp_dir = tempfile.gettempdir()

        # 清理Chrome相关的临时目录
        patterns = [
            os.path.join(temp_dir, 'chrome_*'),
            os.path.join(temp_dir, '.com.google.Chrome.*'),
            os.path.join(temp_dir, 'scoped_dir*')
        ]

        for pattern in patterns:
            for path in glob.glob(pattern):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                except:
                    pass

        print("🧹 已清理Chrome临时文件")
    except Exception as e:
        print(f"清理临时文件时出错（可忽略）: {e}")


def run_single_crawler_subprocess(crawler_name, timeout=600):
    """
    在独立子进程中运行单个爬虫

    Args:
        crawler_name: 爬虫名称 (iea, pvmagazine, irena, combined)
        timeout: 超时时间（秒），默认10分钟

    Returns:
        dict: {'success': bool, 'file': str, 'count': int, 'error': str}
    """
    try:
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 启动 {crawler_name.upper()} 爬虫（独立进程）")
        print(f"⏱️  超时设置: {timeout}秒")
        print(f"{'='*60}\n")

        # 构建爬虫脚本路径
        script_map = {
            'iea': 'iea_crawler.py',
            'pvmagazine': 'pv_magazine_crawler.py',
            'irena': 'irena_crawler.py',
            'combined': 'combined_crawler.py'
        }

        if crawler_name not in script_map:
            return {
                'success': False,
                'error': f'未知的爬虫名称: {crawler_name}',
                'file': None,
                'count': 0
            }

        script_path = os.path.join(os.path.dirname(__file__), script_map[crawler_name])

        # 运行爬虫脚本（带超时）
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=timeout,
            cwd=os.path.dirname(__file__)
        )

        # 输出日志
        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(f"⚠️  stderr输出:\n{result.stderr}")

        # 检查执行结果
        if result.returncode == 0:
            # 查找最新的输出文件
            output_dir = "output/individual"
            pattern = os.path.join(output_dir, f"{crawler_name}_*.json")
            files = glob.glob(pattern)

            if files:
                # 获取最新文件
                latest_file = max(files, key=os.path.getmtime)

                # 读取数据统计
                try:
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        count = len(data) if isinstance(data, list) else 0
                except:
                    count = 0

                print(f"✅ {crawler_name.upper()} 爬虫完成！获取 {count} 条数据")
                print(f"📁 文件: {latest_file}\n")

                return {
                    'success': True,
                    'file': latest_file,
                    'count': count,
                    'error': None
                }
            else:
                print(f"⚠️  {crawler_name.upper()} 爬虫完成，但未找到输出文件\n")
                return {
                    'success': False,
                    'error': '未找到输出文件',
                    'file': None,
                    'count': 0
                }
        else:
            error_msg = f"爬虫脚本返回错误码: {result.returncode}"
            print(f"❌ {crawler_name.upper()} 爬虫失败: {error_msg}\n")
            return {
                'success': False,
                'error': error_msg,
                'file': None,
                'count': 0
            }

    except subprocess.TimeoutExpired:
        error_msg = f"超时（>{timeout}秒）"
        print(f"⏱️  {crawler_name.upper()} 爬虫超时: {error_msg}\n")
        return {
            'success': False,
            'error': error_msg,
            'file': None,
            'count': 0
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ {crawler_name.upper()} 爬虫执行出错: {error_msg}\n")
        return {
            'success': False,
            'error': error_msg,
            'file': None,
            'count': 0
        }


def run_all_crawlers(timeout_per_crawler=600):
    """
    运行所有爬虫（串行模式）

    Args:
        timeout_per_crawler: 每个爬虫的超时时间（秒）

    Returns:
        dict: 执行结果统计
    """
    try:
        print(f"\n{'='*80}")
        print(f"🚀 开始执行爬虫任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print(f"⏱️  单个爬虫超时: {timeout_per_crawler}秒")
        print(f"{'='*80}\n")

        crawlers = ['iea', 'pvmagazine', 'irena', 'combined']
        results = {}

        # 串行执行所有爬虫
        for crawler_name in crawlers:
            results[crawler_name] = run_single_crawler_subprocess(
                crawler_name,
                timeout_per_crawler
            )

            # 清理临时文件，避免冲突
            print("🧹 清理临时文件...\n")
            cleanup_chrome_temp()
            time.sleep(5)  # 短暂等待

        # 统计结果
        print(f"\n{'='*80}")
        print("📊 爬虫任务执行结果汇总")
        print(f"{'='*80}\n")

        total_success = 0
        total_count = 0
        failed_crawlers = []

        for crawler_name, result in results.items():
            status = "✅ 成功" if result['success'] else "❌ 失败"
            count = result['count']
            error = result.get('error', '')

            print(f"  {crawler_name.upper():12s} {status:8s} - {count:3d}条数据", end="")
            if error:
                print(f"  ({error})")
            else:
                print()

            if result['success']:
                total_success += 1
                total_count += count
            else:
                failed_crawlers.append(crawler_name)

        print(f"\n{'='*80}")
        print(f"✅ 成功: {total_success}/{len(crawlers)} 个爬虫")
        print(f"📊 总计: {total_count} 条数据")
        if failed_crawlers:
            print(f"❌ 失败: {', '.join(failed_crawlers)}")
        print(f"{'='*80}\n")

        # 5. 运行翻译
        print(f"\n{'='*60}")
        print("🌐 开始翻译任务")
        print(f"{'='*60}\n")

        translator_output = None
        try:
            from translator import MultiFileTranslator
            translator = MultiFileTranslator()
            translator_output = translator.merge_and_save_translations()
            if translator_output:
                print(f"\n✅ 翻译完成！")
                print(f"📁 文件: {translator_output}\n")
            else:
                print("\n⚠️  翻译未生成输出文件\n")
        except Exception as e:
            print(f"\n❌ 翻译失败: {e}\n")

        # 6. 生成AI总结
        print(f"\n{'='*60}")
        print("🤖 开始生成AI总结")
        print(f"{'='*60}\n")

        try:
            from ai_summarizer import AISummarizer

            # 生成国内新闻总结
            print("📝 生成国内新闻AI总结...")
            combined_file = results.get('combined', {}).get('file')
            if combined_file and os.path.exists(combined_file):
                domestic_summary = AISummarizer.run_from_file(
                    combined_file,
                    'domestic',
                    'ai_summary_domestic.json'
                )
                if domestic_summary.get('success'):
                    print(f"✅ 国内新闻AI总结生成成功\n")
                else:
                    print(f"⚠️  国内新闻AI总结生成失败: {domestic_summary.get('error')}\n")
            else:
                print("⚠️  未找到国内新闻数据文件，跳过国内新闻总结\n")

            # 生成国际新闻总结
            print("📝 生成国际新闻AI总结...")
            if translator_output and os.path.exists(translator_output):
                international_summary = AISummarizer.run_from_file(
                    translator_output,
                    'international',
                    'ai_summary_international.json'
                )
                if international_summary.get('success'):
                    print(f"✅ 国际新闻AI总结生成成功\n")
                else:
                    print(f"⚠️  国际新闻AI总结生成失败: {international_summary.get('error')}\n")
            else:
                print("⚠️  未找到翻译文件，跳过国际新闻总结\n")

            print(f"{'='*60}")
            print("🎉 AI总结任务完成")
            print(f"{'='*60}\n")

        except ImportError:
            print("⚠️  AI总结模块未安装或环境变量未配置，跳过AI总结\n")
        except Exception as e:
            print(f"❌ AI总结生成失败: {e}\n")

        return {
            "results": results,
            "total_success": total_success,
            "total_count": total_count,
            "failed_crawlers": failed_crawlers
        }

    except Exception as e:
        print(f"\n❌ 爬虫任务执行出错: {e}\n")
        return {
            "results": {},
            "total_success": 0,
            "total_count": 0,
            "failed_crawlers": crawlers
        }


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
            run_all_crawlers(timeout_per_crawler=600)
        elif sys.argv[1] == "daily":
            # 设置为每日运行模式
            schedule.clear()
            schedule.every().day.at("09:00").do(run_all_crawlers)
            print("已设置为每日上午9点运行模式")
            run_scheduler()
        else:
            print("Usage:")
            print("  python master_crawler.py now      # 立即运行一次")
            print("  python master_crawler.py daily    # 设置为每日运行")
            print("  python master_crawler.py          # 默认每小时运行（测试）")
    else:
        # 默认：设置定时任务（每小时运行，测试用）
        setup_scheduler()
        run_scheduler()
