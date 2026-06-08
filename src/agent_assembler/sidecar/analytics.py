"""Analytics — 数据分析（查询追踪、指标收集、统计管道）。

自动追踪 Agent 每次运行的 query、reply、token 消耗、延迟等指标，
支持内存统计和 SQLite 持久化，以及导出为 CSV/JSON。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from .base import SidecarBase


@dataclass
class MetricEntry:
    """单条指标记录。"""
    timestamp: float
    agent: str
    query: str
    reply: str = ""
    status: str = "success"
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    sidecars: str = ""
    latency_ms: float = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "agent": self.agent,
            "query": self.query,
            "reply": self.reply[:200],  # 截断
            "status": self.status,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "sidecars": self.sidecars,
            "latency_ms": self.latency_ms,
        }


# ──────────────────────────────────────────
# SQLite 持久化
# ──────────────────────────────────────────

_SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    agent TEXT NOT NULL,
    query TEXT NOT NULL,
    reply TEXT,
    status TEXT DEFAULT 'success',
    model TEXT DEFAULT '',
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    sidecars TEXT DEFAULT '',
    latency_ms REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_metrics_agent ON metrics(agent);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
"""


class _SQLiteStore:
    """SQLite 存储后端。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SQL_SCHEMA)

    def insert(self, entry: MetricEntry):
        self._conn.execute(
            "INSERT INTO metrics (timestamp, agent, query, reply, status, model, "
            "prompt_tokens, completion_tokens, total_tokens, sidecars, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.timestamp, entry.agent, entry.query, entry.reply,
                entry.status, entry.model,
                entry.prompt_tokens, entry.completion_tokens, entry.total_tokens,
                entry.sidecars, entry.latency_ms,
            ),
        )
        self._conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cursor = self._conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]

    def close(self):
        self._conn.close()


# ──────────────────────────────────────────
# Analytics Sidecar
# ──────────────────────────────────────────

class Analytics(SidecarBase):
    """数据分析——查询追踪、指标收集、统计管道。

    用法:
        analytics = Analytics()  # 仅内存
        analytics = Analytics(db_path="/tmp/analytics.db")  # 持久化

        agent.add_sidecar("analytics", analytics)

        # 查询统计
        print(analytics.summary())
        analytics.export_json("/tmp/metrics.json")
    """
    name = "analytics"
    version = "0.2.0"

    def __init__(self, db_path: str | None = None):
        self._metrics: list[MetricEntry] = []
        self._store: _SQLiteStore | None = None
        self._start_time: float | None = None

        if db_path:
            self._store = _SQLiteStore(db_path)

    def pre_process(self, query: str) -> str:
        self._start_time = time.time()
        return query

    def post_process(self, result: dict) -> dict:
        elapsed = 0
        if self._start_time:
            elapsed = (time.time() - self._start_time) * 1000
            self._start_time = None

        usage = result.get("usage", {})
        entry = MetricEntry(
            timestamp=time.time(),
            agent=result.get("agent", ""),
            query=result.get("query", ""),
            reply=result.get("reply", ""),
            status=result.get("status", "success"),
            model=result.get("model", ""),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            sidecars=",".join(result.get("sidecars_active", [])),
            latency_ms=round(elapsed, 2),
        )
        self._metrics.append(entry)

        # 持久化
        if self._store:
            self._store.insert(entry)

        result["analytics_tracked"] = True
        return result

    # ── 查询接口 ──

    @property
    def count(self) -> int:
        if self._store:
            return self._store.count()
        return len(self._metrics)

    def latest(self, n: int = 10) -> list[dict[str, Any]]:
        """获取最近 n 条记录。"""
        if self._store:
            rows = self._store.query(
                "SELECT * FROM metrics ORDER BY timestamp DESC LIMIT ?",
                (n,),
            )
            return rows
        return [m.to_dict() for m in self._metrics[-n:]]

    def summary(self) -> dict[str, Any]:
        """汇总统计。"""
        if self._store:
            return self._db_summary()
        return self._mem_summary()

    def _mem_summary(self) -> dict[str, Any]:
        if not self._metrics:
            return {"count": 0}

        total_tokens = sum(m.total_tokens for m in self._metrics)
        avg_latency = sum(m.latency_ms for m in self._metrics) / len(self._metrics)
        status_counts = {}
        for m in self._metrics:
            status_counts[m.status] = status_counts.get(m.status, 0) + 1

        agent_counts = {}
        for m in self._metrics:
            agent_counts[m.agent] = agent_counts.get(m.agent, 0) + 1

        return {
            "count": len(self._metrics),
            "total_tokens": total_tokens,
            "avg_tokens": round(total_tokens / len(self._metrics)),
            "avg_latency_ms": round(avg_latency, 2),
            "status_breakdown": status_counts,
            "agent_breakdown": agent_counts,
        }

    def _db_summary(self) -> dict[str, Any]:
        rows = self._store.query(
            "SELECT COUNT(*) as cnt, "
            "COALESCE(SUM(total_tokens), 0) as total_tokens, "
            "COALESCE(AVG(total_tokens), 0) as avg_tokens, "
            "COALESCE(AVG(latency_ms), 0) as avg_latency "
            "FROM metrics"
        )
        if not rows:
            return {"count": 0}

        r = rows[0]
        status = self._store.query(
            "SELECT status, COUNT(*) as cnt FROM metrics GROUP BY status"
        )
        agents = self._store.query(
            "SELECT agent, COUNT(*) as cnt FROM metrics GROUP BY agent"
        )

        return {
            "count": r["cnt"],
            "total_tokens": int(r["total_tokens"]),
            "avg_tokens": round(r["avg_tokens"]),
            "avg_latency_ms": round(r["avg_latency"], 2),
            "status_breakdown": {s["status"]: s["cnt"] for s in status},
            "agent_breakdown": {a["agent"]: a["cnt"] for a in agents},
        }

    def top_queries(self, n: int = 10) -> list[dict[str, Any]]:
        """Top N 查询频率。"""
        if self._store:
            return self._store.query(
                "SELECT query, COUNT(*) as cnt FROM metrics GROUP BY query ORDER BY cnt DESC LIMIT ?",
                (n,),
            )
        counts: dict[str, int] = {}
        for m in self._metrics:
            counts[m.query] = counts.get(m.query, 0) + 1
        sorted_q = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"query": q, "cnt": c} for q, c in sorted_q]

    # ── 导出 ──

    def export_json(self, path: str):
        """导出为 JSON。"""
        data = self.latest(n=10000)  # 全量
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def export_csv(self, path: str):
        """导出为 CSV。"""
        data = self.latest(n=10000)
        if not data:
            with open(path, "w") as f:
                f.write("")
            return

        headers = list(data[0].keys())
        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(headers) + "\n")
            for row in data:
                vals = [str(row.get(h, "")).replace(",", ";") for h in headers]
                f.write(",".join(vals) + "\n")

    def close(self):
        if self._store:
            self._store.close()

    def meta(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "count": str(self.count),
            "persistent": str(self._store is not None),
        }
