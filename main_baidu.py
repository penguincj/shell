#!/usr/bin/env python3
"""
Baidu AI Client - 百度文心助手网页版自动化工具

Usage:
    # 首次登录（有头模式）
    DEBUG=1 python main_baidu.py --login

    # 单次提问
    python main_baidu.py "你好，介绍一下你自己"

    # 带图片提问
    python main_baidu.py "识别这张图片" --image /path/to/image.png

    # 调试模式（有头浏览器，慢速）
    DEBUG=1 SLOW_MO=500 python main_baidu.py "测试"
"""
import argparse
import asyncio
import json
import time

from baidu_client import BaiduBrowser, BaiduChat, DEBUG
from baidu_client.config import ARTIFACT_PROMPT
from baidu_client.utils import print_banner, extract_json


async def login_only():
    """仅执行登录流程"""
    browser = BaiduBrowser()
    try:
        # 强制有头模式
        await browser.launch(headless=False)
        await browser.load_cookies_and_goto()

        if not browser.is_logged_in:
            await browser.wait_for_login()

        print("\n✓ 登录完成，状态已保存")
        print("  下次运行将自动使用已保存的登录状态")

    finally:
        input("\n按 Enter 关闭浏览器...")
        await browser.close()


async def single_query(prompt: str, image_path: str = None):
    """单次提问"""
    t_total = time.time()
    browser = BaiduBrowser()
    try:
        t0 = time.time()
        await browser.launch()
        t_launch = time.time()

        logged_in = await browser.load_cookies_and_goto()
        t_load = time.time()

        if not logged_in:
            if DEBUG:
                await browser.wait_for_login()
            else:
                print("✗ 未登录，请先运行: DEBUG=1 python main_baidu.py --login")
                return

        chat = BaiduChat(browser.page)

        # 根据是否有图片选择不同的发送方式
        t_query = time.time()
        if image_path:
            response = await chat.send_message_with_image(prompt, image_path)
        else:
            response = await chat.send_message(prompt)
        t_done = time.time()

        # 图片识别场景：从回复中提取 JSON
        if image_path:
            data = extract_json(response)
            if data:
                print("\n" + "=" * 50)
                print("文物识别结果 (JSON):")
                print("=" * 50)
                print(json.dumps(data, ensure_ascii=False, indent=2))
                print("=" * 50)
            else:
                print("\n" + "=" * 50)
                print("[WARN] 未能从回复中提取 JSON，原始回复:")
                print("=" * 50)
                print(response)
                print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print("AI 回复:")
            print("=" * 50)
            print(response)
            print("=" * 50)

        if DEBUG:
            print(f"\n  [TIMING] === 全流程耗时 ===")
            print(f"  [TIMING]   浏览器启动:  {t_launch - t0:.1f}s")
            print(f"  [TIMING]   加载页面+登录: {t_load - t_launch:.1f}s")
            print(f"  [TIMING]   查询(含上传): {t_done - t_query:.1f}s")
            print(f"  [TIMING]   全流程总计:   {t_done - t_total:.1f}s")

    finally:
        await browser.close()


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Baidu AI Client - 百度文心助手网页版自动化工具"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="要发送的消息"
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="执行登录流程（有头模式）"
    )
    parser.add_argument(
        "--image", "-img",
        type=str,
        help="要上传的图片路径"
    )

    args = parser.parse_args()

    if args.login:
        asyncio.run(login_only())
    elif args.prompt or args.image:
        # 有图片时默认使用文物识别提示词，也可自定义
        prompt = args.prompt or ARTIFACT_PROMPT
        asyncio.run(single_query(prompt, args.image))
    else:
        parser.print_help()
        print("\n示例:")
        print("  DEBUG=1 python main_baidu.py --login           # 首次登录")
        print("  python main_baidu.py '你好'                    # 单次提问")
        print("  python main_baidu.py --image a.png             # 文物识别（默认提示词）")
        print("  python main_baidu.py '自定义问题' --image a.png  # 带图片自定义提问")


if __name__ == "__main__":
    main()
