"""
RPA 对接示例脚本（Playwright）
从 Boss 直聘聊天页抓取新消息后推送到本系统

使用前：
  pip install playwright httpx
  playwright install chromium

用法：
  python scripts/rpa_example.py
"""

import asyncio

import httpx

# 本系统 RPA Webhook 地址
RPA_WEBHOOK_URL = "http://127.0.0.1:8000/api/platform/rpa/webhook"

# 模拟从页面抓取到的一条新消息
SAMPLE_PAYLOAD = {
    "platform": "boss",
    "candidate_id": "12345678",
    "job_id": 1,  # 系统内部职位 ID
    "message": "您好，我对贵司的 Python 岗位很感兴趣",
    "candidate_name": "王五",
    "resume_text": "张三，5年Python后端经验，熟悉FastAPI、Docker、K8s...",
}


async def push_message(payload: dict) -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(RPA_WEBHOOK_URL, json=payload)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")


if __name__ == "__main__":
    print("模拟 RPA 推送消息到 AI 招聘系统...")
    asyncio.run(push_message(SAMPLE_PAYLOAD))
