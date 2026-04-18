#!/usr/bin/env python3
"""注入测试文档到 RAG 知识库。

用法:
    python scripts/ingest_test_data.py [--host http://localhost:8000]
"""
import asyncio
import sys
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000/api/v1"
TEST_DATA_DIR = Path(__file__).parent / "test_data"

DOCUMENTS = [
    ("gree_company_intro.md", "格力电器公司简介"),
    ("gree_technology.md", "格力核心技术体系"),
    ("qt_agent_development_guide.md", "QT-Agent 开发指南"),
]


async def main(host: str):
    base = host
    print(f"=== 注入测试数据到 {base} ===\n")

    # 1. 创建知识库
    print("[1/3] 创建知识库...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base}/knowledge-bases",
            json={"name": "测试知识库", "description": "用于测试的格力相关知识"},
        )
        if resp.status_code not in (200, 201):
            print(f"  创建知识库失败: {resp.status_code} {resp.text}")
            # 尝试获取已有的
            resp = await client.get(f"{base}/knowledge-bases")
            if resp.status_code == 200 and resp.json():
                kb_id = resp.json()[0]["id"]
                print(f"  使用已有知识库: {kb_id}")
            else:
                print("  无法创建或获取知识库，退出")
                sys.exit(1)
        else:
            kb_data = resp.json()
            kb_id = kb_data["id"]
            print(f"  知识库已创建: id={kb_id}")

    # 2. 上传文档
    print(f"\n[2/3] 上传文档到知识库 {kb_id}...")
    async with httpx.AsyncClient(timeout=60) as client:
        for filename, description in DOCUMENTS:
            filepath = TEST_DATA_DIR / filename
            if not filepath.exists():
                print(f"  ⚠ 文件不存在，跳过: {filepath}")
                continue

            with open(filepath, "rb") as f:
                resp = await client.post(
                    f"{base}/ingest/upload",
                    data={"knowledge_base_id": kb_id},
                    files={"file": (filename, f, "text/markdown")},
                )

            if resp.status_code in (200, 201):
                doc = resp.json()
                print(f"  ✅ {filename} → doc_id={doc.get('id', 'N/A')} status={doc.get('status', 'N/A')}")
            else:
                print(f"  ❌ {filename}: {resp.status_code} {resp.text[:200]}")

    # 3. 等待入库完成并检查状态
    print(f"\n[3/3] 等待入库完成（最多60秒）...")
    async with httpx.AsyncClient(timeout=30) as client:
        await asyncio.sleep(5)  # 先等5秒

        for _ in range(12):  # 最多等60秒
            resp = await client.get(f"{base}/knowledge-bases/{kb_id}/documents")
            if resp.status_code != 200:
                print(f"  查询文档状态失败: {resp.status_code}")
                break

            docs = resp.json()
            if not isinstance(docs, list):
                docs = docs.get("items", []) if isinstance(docs, dict) else []
            statuses = {d.get("parser_status", d.get("status", "unknown")) for d in docs}
            print(f"  文档状态: { {s: sum(1 for d in docs if d.get('parser_status', d.get('status'))==s) for s in statuses} }")

            if statuses <= {"completed", "failed"}:
                break
            await asyncio.sleep(5)

    print("\n=== 注入完成 ===")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else API_BASE
    asyncio.run(main(host))
