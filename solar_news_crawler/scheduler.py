#!/usr/bin/env python3
"""
独立的定时调度器 - 每天自动运行爬虫和翻译任务
使用方法: python scheduler.py
"""

import os
import sys
import time
import schedule
import subprocess
from datetime import datetime

# 获取当前脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_crawler_task():
    """运行爬虫任务（爬取+翻译）"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{'='*60}")
        print(f"[{timestamp}] 🚀 开始执行定时爬虫任务...")
        print(f"{'='*60}\n")

        # 运行 master_crawler.py now
        master_crawler_path = os.path.join(BASE_DIR, 'master_crawler.py')

        result = subprocess.run(
            [sys.executable, master_crawler_path, 'now'],
            cwd=BASE_DIR
        )

        # 输出日志
        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print("❌ 错误信息:")
            print(result.stderr)

        if result.returncode == 0:
            print(f"\n✅ 定时爬虫任务执行成功！")
        else:
            print(f"\n❌ 定时爬虫任务执行失败，返回码: {result.returncode}")

        print(f"\n{'='*60}\n")

    except Exception as e:
        print(f"❌ 执行爬虫任务时出错: {e}")

def main():
    """主函数"""
    print("="*60)
    print("📅 定时调度器已启动")
    print("="*60)
    print(f"⏰ 每日执行时间: 02:00 AM")
    print(f"📁 工作目录: {BASE_DIR}")
    print(f"🔄 首次运行: 将在下一个02:00执行")
    print("="*60)
    print("\n提示: 按 Ctrl+C 可以停止调度器\n")

    # 设置每天凌晨2点执行
    schedule.every().day.at("02:00").do(run_crawler_task)

    # 可选：启动时立即执行一次（测试用）
    if len(sys.argv) > 1 and sys.argv[1] == '--run-now':
        print("🚀 检测到 --run-now 参数，立即执行一次任务...\n")
        run_crawler_task()

    # 持续运行
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        print("\n\n⚠️  收到停止信号，调度器正在关闭...")
        print("👋 调度器已安全退出\n")

if __name__ == "__main__":
    main()
