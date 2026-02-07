#!/usr/bin/env python3
"""
Qwen Web Client - 通义千问网页版自动化工具

Usage:
    # 首次登录（有头模式）
    DEBUG=1 python main.py --login

    # 单次提问
    python main.py "你好，介绍一下你自己"

    # 调试模式（有头浏览器，慢速）
    DEBUG=1 SLOW_MO=500 python main.py "帮我搜索今天的新闻"

    # 交互模式
    python main.py --interactive
    python main.py -i
"""
import argparse
import asyncio
import sys

from qwen_client import QwenBrowser, QwenChat, DEBUG
from qwen_client.utils import print_banner


async def login_only():
    """仅执行登录流程"""
    browser = QwenBrowser()
    try:
        # 强制有头模式
        await browser.launch(headless=False)
        await browser.load_cookies_and_goto()

        if not browser.is_logged_in:
            await browser.wait_for_login()

        print("\n✓ 登录完成，Cookies 已保存")
        print("  下次运行将自动使用已保存的登录状态")

    finally:
        input("\n按 Enter 关闭浏览器...")
        await browser.close()


async def single_query(prompt: str):
    """单次提问"""
    browser = QwenBrowser()
    try:
        await browser.launch()
        logged_in = await browser.load_cookies_and_goto()

        if not logged_in:
            if DEBUG:
                await browser.wait_for_login()
            else:
                print("✗ 未登录，请先运行: DEBUG=1 python main.py --login")
                return

        chat = QwenChat(browser.page)
        response = await chat.send_message(prompt)

        print("\n" + "=" * 50)
        print("AI 回复:")
        print("=" * 50)
        print(response)
        print("=" * 50)

    finally:
        await browser.close()


async def interactive_mode():
    """交互模式"""
    browser = QwenBrowser()
    try:
        await browser.launch()
        logged_in = await browser.load_cookies_and_goto()

        if not logged_in:
            if DEBUG:
                await browser.wait_for_login()
            else:
                print("✗ 未登录，请先运行: DEBUG=1 python main.py --login")
                return

        chat = QwenChat(browser.page)

        print("\n" + "=" * 50)
        print("进入交互模式")
        print("输入 'quit' 或 'exit' 退出")
        print("输入 'new' 开启新对话")
        print("=" * 50 + "\n")

        while True:
            try:
                prompt = input("You: ").strip()

                if not prompt:
                    continue

                if prompt.lower() in ('quit', 'exit', 'q'):
                    print("Bye!")
                    break

                if prompt.lower() == 'new':
                    await chat.new_chat()
                    continue

                response = await chat.send_message(prompt)
                print(f"\nQwen: {response}\n")

            except KeyboardInterrupt:
                print("\nBye!")
                break
            except Exception as e:
                print(f"\n✗ 错误: {e}\n")

    finally:
        await browser.close()


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Qwen Web Client - 通义千问网页版自动化工具"
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
        "-i", "--interactive",
        action="store_true",
        help="进入交互模式"
    )

    args = parser.parse_args()

    if args.login:
        asyncio.run(login_only())
    elif args.interactive:
        asyncio.run(interactive_mode())
    elif args.prompt:
        asyncio.run(single_query(args.prompt))
    else:
        parser.print_help()
        print("\n示例:")
        print("  DEBUG=1 python main.py --login        # 首次登录")
        print("  python main.py '你好'                 # 单次提问")
        print("  python main.py -i                     # 交互模式")


if __name__ == "__main__":
    main()
