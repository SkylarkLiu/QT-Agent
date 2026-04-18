#!/usr/bin/env python3
"""QT-Agent API 端点测试脚本。

测试所有 API 端点是否正常工作，包括：
  1. Health Check
  2. 知识库 CRUD
  3. 文档上传与入库状态
  4. Chat（非流式 + SSE 流式）
  5. 会话历史与 Debug

用法:
    python scripts/test_api.py [--host http://localhost:8000]
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000/api/v1"
TEST_DATA_DIR = Path(__file__).parent / "test_data"


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str, detail: str = ""):
        self.passed += 1
        suffix = f" ({detail})" if detail else ""
        print(f"  ✅ {name}{suffix}")

    def fail(self, name: str, reason: str):
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
        print(f"  ❌ {name}: {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"测试结果: {self.passed}/{total} 通过, {self.failed} 失败")
        if self.errors:
            print("\n失败项:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*50}")
        return self.failed == 0


r = TestResult()


async def test_health(client: httpx.AsyncClient):
    """T1: Health Check"""
    print("\n── T1: Health Check ──")
    try:
        resp = await client.get(f"{API_BASE}/health")
        if resp.status_code == 200:
            data = resp.json()
            r.ok("GET /health", f"status={data.get('status')}")
        else:
            r.fail("GET /health", f"status={resp.status_code}")
    except Exception as e:
        r.fail("GET /health", str(e))


async def test_knowledge_base(client: httpx.AsyncClient) -> str | None:
    """T2: 知识库 CRUD"""
    print("\n── T2: 知识库管理 ──")
    kb_id = None

    # T2.1 创建知识库
    try:
        resp = await client.post(
            f"{API_BASE}/knowledge-bases",
            json={"name": "API测试知识库", "description": "自动化测试用"},
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            kb_id = data.get("id")
            r.ok("POST /knowledge-bases (创建)", f"id={kb_id}")
        else:
            r.fail("POST /knowledge-bases", f"status={resp.status_code} {resp.text[:200]}")
    except Exception as e:
        r.fail("POST /knowledge-bases", str(e))

    if not kb_id:
        print("  ⚠ 无法创建知识库，尝试获取已有的...")
        try:
            resp = await client.get(f"{API_BASE}/knowledge-bases")
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    kb_id = items[0]["id"]
                    r.ok("GET /knowledge-bases (回退)", f"使用已有 kb_id={kb_id}")
                else:
                    r.fail("GET /knowledge-bases (回退)", "无已有知识库")
        except Exception as e:
            r.fail("GET /knowledge-bases", str(e))

    # T2.2 列出知识库
    try:
        resp = await client.get(f"{API_BASE}/knowledge-bases")
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            r.ok("GET /knowledge-bases (列出)", f"total={total}")
        else:
            r.fail("GET /knowledge-bases", f"status={resp.status_code}")
    except Exception as e:
        r.fail("GET /knowledge-bases", str(e))

    return kb_id


async def test_document_upload(client: httpx.AsyncClient, kb_id: str) -> str | None:
    """T3: 文档上传"""
    print("\n── T3: 文档上传 ──")
    doc_id = None

    filepath = TEST_DATA_DIR / "gree_company_intro.md"
    if not filepath.exists():
        r.fail("POST /ingest/upload", f"测试文件不存在: {filepath}")
        return None

    try:
        with open(filepath, "rb") as f:
            resp = await client.post(
                f"{API_BASE}/ingest/upload",
                data={"knowledge_base_id": kb_id},
                files={"file": ("gree_company_intro.md", f, "text/markdown")},
            )
        if resp.status_code in (200, 201):
            data = resp.json()
            doc_id = data.get("document_id") or data.get("id")
            r.ok("POST /ingest/upload", f"doc_id={doc_id}")
        else:
            r.fail("POST /ingest/upload", f"status={resp.status_code} {resp.text[:200]}")
    except Exception as e:
        r.fail("POST /ingest/upload", str(e))

    return doc_id


async def test_document_status(client: httpx.AsyncClient, doc_id: str | None):
    """T4: 文档入库状态"""
    print("\n── T4: 文档入库状态 ──")

    if not doc_id:
        r.fail("GET /documents/{id}/status", "无可用 doc_id")
        return

    try:
        resp = await client.get(f"{API_BASE}/documents/{doc_id}/status")
        if resp.status_code == 200:
            data = resp.json()
            r.ok("GET /documents/{id}/status", f"status={data.get('status')}")
        else:
            r.fail("GET /documents/{id}/status", f"status={resp.status_code}")
    except Exception as e:
        r.fail("GET /documents/{id}/status", str(e))


async def test_list_documents(client: httpx.AsyncClient, kb_id: str):
    """T5: 列出知识库文档"""
    print("\n── T5: 列出知识库文档 ──")

    try:
        resp = await client.get(f"{API_BASE}/knowledge-bases/{kb_id}/documents")
        if resp.status_code == 200:
            data = resp.json()
            r.ok("GET /knowledge-bases/{id}/documents", f"total={data.get('total', 0)}")
        else:
            r.fail("GET /knowledge-bases/{id}/documents", f"status={resp.status_code}")
    except Exception as e:
        r.fail("GET /knowledge-bases/{id}/documents", str(e))


async def test_chat_non_stream(client: httpx.AsyncClient):
    """T6: Chat 非流式"""
    print("\n── T6: Chat 非流式 ──")

    try:
        resp = await client.post(
            f"{API_BASE}/chat",
            json={
                "username": "tester",
                "message": "格力电器的股票代码是什么？",
                "stream": False,
                "route_mode": "knowledge",
            },
            timeout=60.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("content", "")
            session_id = data.get("session_id", "")
            r.ok("POST /chat (非流式)", f"session={session_id[:8]}..., content_len={len(content)}")
            if not content:
                r.fail("POST /chat 内容检查", "返回内容为空")
            return session_id
        else:
            r.fail("POST /chat", f"status={resp.status_code} {resp.text[:300]}")
    except httpx.ReadTimeout:
        r.fail("POST /chat", "请求超时（60s）")
    except Exception as e:
        r.fail("POST /chat", str(e))

    return None


async def test_chat_stream(client: httpx.AsyncClient):
    """T7: Chat SSE 流式"""
    print("\n── T7: Chat SSE 流式 ──")

    try:
        async with client.stream(
            "POST",
            f"{API_BASE}/chat",
            json={
                "username": "tester",
                "message": "格力电器有哪些核心技术？",
                "stream": True,
                "route_mode": "knowledge",
            },
            timeout=60.0,
        ) as resp:
            if resp.status_code != 200:
                r.fail("POST /chat (流式)", f"status={resp.status_code}")
                return

            events = []
            full_content = ""
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data_str = line.removeprefix("data:").strip()
                    if data_str:
                        try:
                            data = json.loads(data_str)
                            events.append(data.get("event", ""))
                            if "content" in data:
                                full_content += data["content"]
                            elif "detail" in data:
                                r.fail("POST /chat (流式)", f"error event: {data['detail'][:200]}")
                                return
                        except json.JSONDecodeError:
                            pass

            event_types = set(events)
            r.ok("POST /chat (流式)", f"events={event_types}, content_len={len(full_content)}")

            if not full_content:
                r.fail("POST /chat (流式) 内容检查", "返回内容为空")

    except httpx.ReadTimeout:
        r.fail("POST /chat (流式)", "请求超时（60s）")
    except Exception as e:
        r.fail("POST /chat (流式)", str(e))


async def test_chat_history(client: httpx.AsyncClient, session_id: str | None):
    """T8: 会话历史"""
    print("\n── T8: 会话历史 ──")

    if not session_id:
        r.fail("GET /chat/history", "无可用 session_id")
        return

    try:
        resp = await client.get(f"{API_BASE}/chat/history", params={"session_id": session_id, "limit": 10})
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get("messages", [])
            r.ok("GET /chat/history", f"messages={len(messages)}")
        else:
            r.fail("GET /chat/history", f"status={resp.status_code}")
    except Exception as e:
        r.fail("GET /chat/history", str(e))


async def test_chat_debug(client: httpx.AsyncClient, session_id: str | None):
    """T9: Chat Debug"""
    print("\n── T9: Chat Debug ──")

    if not session_id:
        r.fail("GET /chat/debug", "无可用 session_id")
        return

    try:
        resp = await client.get(f"{API_BASE}/chat/debug", params={"session_id": session_id, "limit": 10})
        if resp.status_code == 200:
            data = resp.json()
            timeline = data.get("timeline", [])
            r.ok("GET /chat/debug", f"timeline_items={len(timeline)}")
        else:
            r.fail("GET /chat/debug", f"status={resp.status_code}")
    except Exception as e:
        r.fail("GET /chat/debug", str(e))


async def test_chat_websearch(client: httpx.AsyncClient):
    """T10: WebSearch 路由"""
    print("\n── T10: WebSearch 路由 ──")

    try:
        resp = await client.post(
            f"{API_BASE}/chat",
            json={
                "username": "tester",
                "message": "今天深圳天气怎么样？",
                "stream": False,
                "route_mode": "websearch",
            },
            timeout=60.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("content", "")
            route = data.get("route_type", "")
            r.ok("POST /chat (websearch)", f"route={route}, content_len={len(content)}")
        else:
            r.fail("POST /chat (websearch)", f"status={resp.status_code} {resp.text[:300]}")
    except httpx.ReadTimeout:
        r.fail("POST /chat (websearch)", "请求超时（60s）")
    except Exception as e:
        r.fail("POST /chat (websearch)", str(e))


async def main():
    global API_BASE
    host = API_BASE
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        host = sys.argv[1]
    API_BASE = host

    print("=" * 50)
    print(f"QT-Agent API 端点测试")
    print(f"目标: {API_BASE}")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30) as client:
        # T1: Health
        await test_health(client)

        # T2: Knowledge Base
        kb_id = await test_knowledge_base(client)

        #T3-T5: Document (需要 kb_id)
        if kb_id:
            doc_id = await test_document_upload(client, kb_id)
            await test_document_status(client, doc_id)
            await test_list_documents(client, kb_id)

        # T6: Chat non-stream
        session_id = await test_chat_non_stream(client)

        # T7: Chat stream
        await test_chat_stream(client)

        # T8-T9: History & Debug (需要 session_id)
        await test_chat_history(client, session_id)
        await test_chat_debug(client, session_id)

        # T10: WebSearch route
        await test_chat_websearch(client)

    return r.summary()


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
