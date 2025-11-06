#!/usr/bin/env python3
"""
AI新闻总结生成器
从环境变量读取大模型配置，生成每日新闻简报
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import requests


class AISummarizer:
    """AI新闻总结生成器类"""

    def __init__(self):
        """初始化，从环境变量读取配置"""
        self.base_url = os.getenv("AI_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("AI_API_KEY", "")
        self.model = os.getenv("AI_MODEL", "gpt-3.5-turbo")

        # 验证配置
        if not self.base_url:
            raise ValueError("环境变量 AI_BASE_URL 未设置")
        if not self.api_key:
            raise ValueError("环境变量 AI_API_KEY 未设置")

        print(f"✓ AI配置已加载: {self.model}")
        print(f"✓ API地址: {self.base_url}")

    def _call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        调用大语言模型API

        Args:
            messages: 消息列表
            temperature: 温度参数，控制随机性

        Returns:
            str: 模型返回的文本
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://solar-news-crawler.local",
            "X-Title": "Solar News AI Summarizer",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"❌ API调用失败: {e}")
            raise

    def generate_summary(
        self, news_data: List[Dict], news_type: str = "domestic"
    ) -> Dict:
        """
        根据新闻数据生成AI简报

        Args:
            news_data: 新闻数据列表
            news_type: 新闻类型 'domestic'(国内) 或 'international'(国际)

        Returns:
            Dict: 包含总结内容的字典
        """
        if not news_data:
            return {
                "success": False,
                "error": "没有新闻数据",
                "summary": "",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        # 准备上下文信息
        news_titles = []
        source_stats = {}

        for news in news_data[:100]:  # 限制最多100条，避免token过多
            # 根据新闻类型选择合适的标题字段
            if news_type == "international":
                title = news.get("title_translated") or news.get("title_original", "")
            else:
                title = news.get("title", "")

            if title:
                news_titles.append(title)

            # 统计数据源
            source = news.get("source", "Unknown")
            source_stats[source] = source_stats.get(source, 0) + 1

        # 构建提示词
        news_type_cn = "国内" if news_type == "domestic" else "国际"
        today = datetime.now().strftime("%Y年%m月%d日")

        context = f"""
今天是{today}，以下是今日收集的{news_type_cn}光伏行业新闻标题({len(news_titles)}条):

{chr(10).join(f"{i+1}. {title}" for i, title in enumerate(news_titles[:50]))}

数据来源统计:
{chr(10).join(f"- {source}: {count}条" for source, count in source_stats.items())}
"""

        prompt = f"""请根据以上{news_type_cn}光伏行业新闻标题，生成"今日光伏产业焦点"简报。

要求：
1. 首先用一句话总结今日整体趋势（如：今日光伏产业聚焦XXX领域...）
2. 提取3-5个主要热点话题
3. 每个话题用1句话精炼概括，突出核心要点
4. 使用markdown格式，用 "### " 标记每个话题标题
5. 总字数控制在250字以内
6. 语言精炼专业，避免冗余表述

格式示例：
今日光伏产业聚焦政策创新与市场扩容，多项重大举措集中发布。

### 话题标题
一句话核心要点描述。

请直接输出简报内容，不要添加标题和额外说明。"""

        messages = [
            {"role": "system", "content": "你是一位资深的光伏行业分析师，擅长从大量新闻中提取核心信息并生成简报。"},
            {"role": "user", "content": context + "\n\n" + prompt},
        ]

        try:
            print(f"正在生成{news_type_cn}新闻AI简报...")
            summary_text = self._call_llm(messages, temperature=0.7)

            result = {
                "success": True,
                "summary": summary_text.strip(),
                "news_count": len(news_data),
                "processed_count": len(news_titles),
                "source_stats": source_stats,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "news_type": news_type,
            }

            print(f"✓ {news_type_cn}简报生成成功")
            return result

        except Exception as e:
            print(f"❌ 生成简报失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": "",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "news_type": news_type,
            }

    def save_summary_to_file(self, summary_data: Dict, output_path: str) -> bool:
        """
        将总结保存到JSON文件（列表形式，每天一条记录）

        Args:
            summary_data: 总结数据
            output_path: 输出文件路径

        Returns:
            bool: 是否保存成功
        """
        try:
            # 确保目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # 读取现有数据
            existing_data = []
            if os.path.exists(output_path):
                try:
                    with open(output_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                        if not isinstance(existing_data, list):
                            existing_data = []
                except:
                    existing_data = []

            # 获取今天的日期
            today = datetime.now().strftime("%Y-%m-%d")

            # 检查是否已有今天的记录，如果有就删除（覆盖）
            existing_data = [item for item in existing_data if item.get("date") != today]

            # 添加新记录
            new_record = {
                "date": today,
                "generated_at": summary_data.get("generated_at"),
                "summary": summary_data.get("summary"),
                "news_count": summary_data.get("news_count"),
                "processed_count": summary_data.get("processed_count"),
                "source_stats": summary_data.get("source_stats"),
                "news_type": summary_data.get("news_type"),
                "success": summary_data.get("success")
            }

            # 插入到列表开头（最新的在前）
            existing_data.insert(0, new_record)

            # 只保留最近30天的记录
            existing_data = existing_data[:30]

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            print(f"✓ 简报已保存至: {output_path} (日期: {today})")
            return True

        except Exception as e:
            print(f"❌ 保存简报失败: {e}")
            return False

    @classmethod
    def run_from_news_data(
        cls, news_data: List[Dict], news_type: str, output_path: str
    ) -> Dict:
        """
        类方法：运行完整流程（生成并保存）

        Args:
            news_data: 新闻数据列表
            news_type: 新闻类型 'domestic' 或 'international'
            output_path: 输出文件路径

        Returns:
            Dict: 总结结果
        """
        try:
            summarizer = cls()
            summary_data = summarizer.generate_summary(news_data, news_type)

            if summary_data.get("success"):
                summarizer.save_summary_to_file(summary_data, output_path)

            return summary_data

        except Exception as e:
            print(f"❌ 执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    @classmethod
    def run_from_file(
        cls, input_file: str, news_type: str, output_path: str
    ) -> Dict:
        """
        类方法：从JSON文件读取新闻数据并生成总结

        Args:
            input_file: 输入的新闻JSON文件路径
            news_type: 新闻类型
            output_path: 输出文件路径

        Returns:
            Dict: 总结结果
        """
        try:
            # 读取新闻数据
            with open(input_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 兼容不同的数据格式
            if isinstance(data, dict):
                news_data = data.get("news_list", data.get("data", []))
            elif isinstance(data, list):
                news_data = data
            else:
                raise ValueError("不支持的数据格式")

            print(f"✓ 从 {input_file} 读取了 {len(news_data)} 条新闻")

            return cls.run_from_news_data(news_data, news_type, output_path)

        except FileNotFoundError:
            print(f"❌ 文件不存在: {input_file}")
            return {"success": False, "error": "文件不存在"}
        except json.JSONDecodeError:
            print(f"❌ JSON解析失败: {input_file}")
            return {"success": False, "error": "JSON解析失败"}
        except Exception as e:
            print(f"❌ 读取文件失败: {e}")
            return {"success": False, "error": str(e)}


def main():
    """命令行入口"""
    if len(sys.argv) < 4:
        print("使用方法:")
        print(
            "  python ai_summarizer.py <输入文件> <新闻类型> <输出文件>"
        )
        print("\n参数说明:")
        print("  输入文件: 新闻JSON文件路径")
        print("  新闻类型: domestic(国内) 或 international(国际)")
        print("  输出文件: 输出的总结JSON文件路径")
        print("\n示例:")
        print(
            "  python ai_summarizer.py combined_news.json domestic summary_domestic.json"
        )
        print(
            "  python ai_summarizer.py translator.json international summary_international.json"
        )
        sys.exit(1)

    input_file = sys.argv[1]
    news_type = sys.argv[2]
    output_file = sys.argv[3]

    if news_type not in ["domestic", "international"]:
        print("❌ 新闻类型必须是 'domestic' 或 'international'")
        sys.exit(1)

    # 运行总结生成
    result = AISummarizer.run_from_file(input_file, news_type, output_file)

    if result.get("success"):
        print("\n" + "=" * 50)
        print("✓ 简报生成完成！")
        print(f"新闻数量: {result.get('news_count', 0)}")
        print(f"生成时间: {result.get('generated_at', '')}")
        print("=" * 50)
        sys.exit(0)
    else:
        print(f"\n❌ 简报生成失败: {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
