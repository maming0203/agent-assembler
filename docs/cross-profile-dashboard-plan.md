# Cross-Profile Status Dashboard — Architectural Plan

> **Version:** 1.0  
> **Date:** 2026-06-07  
> **Author:** Hermes Agent (马明主 profile)  
> **Status:** Draft — awaiting review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Architecture Overview](#3-architecture-overview)
4. [Data Model](#4-data-model)
5. [Implementation Approach](#5-implementation-approach)
6. [UI/UX Design](#6-uiux-design)
7. [Integration Points](#7-integration-points)
8. [Phased Rollout Plan](#8-phased-rollout-plan)
9. [Security & Isolation Guarantees](#9-security--isolation-guarantees)
10. [Future Extensions](#10-future-extensions)

---

## 1. Executive Summary

This plan describes a **read-only, passive monitoring dashboard** that provides real-time visibility into all Hermes agent profiles without modifying their internal behavior. The dashboard:

- **Polls** filesystem-level signals every 30–60 seconds
- **Renders** a single-page HTML dashboard with live-updating panels
- **Tracks** the full pipeline: Miner → Sync → AutoCraft → Deploy
- **Alerts** on failures, stuck tasks, and dependency breaks

The entire system is **file-based only** — no network calls between profiles, no process injection, no modification of profile internals. Profiles remain completely unaware they are being monitored.

---

## 2. Problem Statement

### Current Pain Points

| # | Problem | Impact |
|---|---------|--------|
| 1 | No real-time visibility into what other profiles are doing | Manual polling required; latency in detecting stalls |
| 2 | No status tracking (running/idle/error/completed) | Can't tell if Miner is actively mining or stuck |
| 3 | No output traceability | Don't know what Miner produced or if it succeeded |
| 4 | No cross-profile dependency tracking | Can't see Miner output → AutoCraft trigger chain |
| 5 | Profile gateways are independent | One profile can't query another's state |

### Current Coordination Mechanisms

| Mechanism | Type | Frequency | Limitation |
|-----------|------|-----------|------------|
| `HEARTBEAT.md` | File handshake | On demand | No structured status |
| `task-tracker.json` | Inbox messaging | Ad-hoc | No timeline history |
| `recipe-sync.sh` | Cron sync | Every 1 min | No visibility into sync result |
| Kanban dispatch | CLI commands | Manual | No automated tracking |

---

## 3. Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CROSS-PROFILE DASHBOARD                       │
│                                                                 │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐  │
│  │   Collector   │───▶│   Aggregator  │───▶│    Dashboard     │  │
│  │  (Poller)     │    │  (Processor)  │    │    (HTML/JS)     │  │
│  └──────┬───────┘    └───────┬───────┘    └────────┬─────────┘  │
│         │                    │                     │            │
│         ▼                    ▼                     ▼            │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐  │
│  │  State Cache  │◀───│   Event Bus   │    │  Live Refresh    │  │
│  │  (JSON file)  │    │  (in-memory)  │    │  (30s polling)   │  │
│  └──────────────┘    └───────────────┘    └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Profile: 马明主 │  │ Profile: 矿工   │  │ Profile: 同事顾问 │
│  (default)      │  │ (painpoint-     │  │ (bbb-consultant)│
│                 │  │  miner)         │  │                 │
│  • gateway.log  │  │  • state.db     │  │  • gateway.log  │
│  • cron/        │  │  • logs/        │  │  • cron/        │
│  • sessions/    │  │  • recipes/     │  │  • sessions/    │
│  • memories/    │  │  • mined/       │  │  • kanban/      │
│  • skills/      │  │                 │  │  • skills/      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Component Details

#### 3.1 Collector (Poller)

A lightweight Python script (`~/.hermes/scripts/dashboard-collector.py`) that runs on a cron schedule (every 30s). It performs **read-only filesystem scans** across all profiles:

- **No writes** to profile directories
- **No network calls** between profiles
- **No process injection** into profile gateways
- Reads only public signals: logs, state files, timestamps, process status

#### 3.2 Aggregator (Processor)

Merges raw signals into structured events. Detects:

- Profile state transitions (idle → active → error)
- New outputs (recipes mined, files created)
- Sync bridge results (success/failure)
- Pipeline stage progression

#### 3.3 State Cache

A single JSON file at `~/.hermes/dashboard/state.json` that stores the latest known state of all profiles. This is the **source of truth** for the dashboard UI.

#### 3.4 Dashboard UI

A self-contained HTML file (`~/.hermes/dashboard/status.html`) with embedded CSS/JS. Opens in any browser. Auto-refreshes every 30s by re-reading the state cache.

---

## 4. Data Model

### 4.1 Profile State

```typescript
interface ProfileState {
  name: string;                    // "default", "painpoint-miner", "bbb-consultant"
  status: "active" | "idle" | "error" | "stopped";
  last_activity: string;           // ISO 8601 timestamp
  last_activity_type: string;      // "message_received" | "cron_executed" | "recipe_mined" | ...
  current_task: string | null;     // Description of ongoing work
  gateway: GatewayState;
  cron: CronState[];
  recent_outputs: OutputRecord[];
  error_count_24h: number;
  uptime_hours: number;
}

interface GatewayState {
  running: boolean;
  pid: number | null;
  last_log_entry: string;          // ISO 8601
  last_log_message: string;        // Last line from gateway.log
  errors_recent: string[];         // Last 5 error lines from errors.log
}

interface CronState {
  job_id: string;
  name: string;
  state: "scheduled" | "running" | "paused";
  last_run_at: string;
  last_status: "ok" | "error" | "skipped";
  next_run_at: string;
  total_executions: number;
}

interface OutputRecord {
  type: "recipe" | "report" | "skill" | "sync" | "kanban";
  name: string;
  path: string;
  created_at: string;
  source_profile: string;
  destination_profile: string | null;  // null if not cross-profile
}
```

### 4.2 Event Record

```typescript
interface EventRecord {
  id: string;                      // UUID
  timestamp: string;               // ISO 8601
  profile: string;
  type: "status_change" | "output_created" | "sync_completed" | 
        "error" | "cron_triggered" | "pipeline_stage";
  severity: "info" | "warning" | "error";
  message: string;
  details: Record<string, any>;    // Context-specific payload
  related_event_id: string | null; // Links to upstream/downstream events
}
```

### 4.3 Pipeline State

```typescript
interface PipelineStage {
  name: string;                    // "Mine" | "Sync" | "AutoCraft" | "Deploy"
  status: "waiting" | "running" | "completed" | "failed";
  profile: string;                 // Which profile owns this stage
  input_artifact: string | null;   // What triggered this stage
  output_artifact: string | null;  // What it produced
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

interface PipelineRun {
  id: string;                      // Unique run ID
  stages: PipelineStage[];
  created_at: string;
  overall_status: "running" | "completed" | "failed" | "stalled";
}
```

### 4.4 Dashboard State (Cache)

```json
{
  "generated_at": "2026-06-07T16:30:00Z",
  "profiles": {
    "default": { /* ProfileState */ },
    "painpoint-miner": { /* ProfileState */ },
    "bbb-consultant": { /* ProfileState */ }
  },
  "events": [/* EventRecord[] — last 100 */],
  "pipelines": [/* PipelineRun[] — last 20 */],
  "alerts": [/* ActiveAlert[] */]
}
```

---

## 5. Implementation Approach

### 5.1 Monitoring Strategy: Passive Filesystem Polling

The core principle is **read-only observation**. The collector scans known file paths and infers state from:

| Data Source | What It Tells Us | How We Read It |
|-------------|------------------|----------------|
| `~/.hermes/profiles/<name>/gateway.pid` | Is gateway running? | File exists + `kill -0 <pid>` |
| `~/.hermes/profiles/<name>/logs/gateway.log` | What is gateway doing? | `tail -5` last entries |
| `~/.hermes/profiles/<name>/logs/errors.log` | Are there errors? | Count entries in last hour |
| `~/.hermes/profiles/<name>/logs/agent.log` | Agent activity? | Timestamp of last entry |
| `~/.hermes/cron/jobs.json` | Cron job status | Parse JSON for per-profile jobs |
| `~/.hermes/sessions/` | Active sessions? | File timestamps + JSONL contents |
| `~/Desktop/配方/mined/` | Miner output? | Directory listing + `index.json` |
| `~/Desktop/配方/AutoCreated/` | AutoCraft output? | Directory listing + timestamps |
| `ps aux \| grep hermes` | Process status | Parse `ps` output for profile-specific processes |

### 5.2 State Inference Logic

**Profile Status Determination:**

```
IF gateway.pid exists AND process alive AND agent.log modified < 5 min ago
  → status = "active"
ELIF gateway.pid exists AND process alive AND agent.log modified > 30 min ago
  → status = "idle"
ELIF errors.log has entries in last 5 min
  → status = "error"
ELSE
  → status = "stopped"
```

**Dependency Chain Detection:**

```
1. Monitor ~/Desktop/配方/mined/index.json for new entries
2. When new recipe appears → create EventRecord(type="output_created")
3. Check recipe-sync.sh output/logs to confirm sync
4. Monitor ~/Desktop/配方/AutoCreated/ for files matching recipe name
5. When matching file appears → link events via related_event_id
6. Display as pipeline chain in UI
```

### 5.3 Collector Script Structure

```python
# ~/.hermes/scripts/dashboard-collector.py

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

PROFILES = {
    "default": {
        "name": "马明主",
        "base_dir": Path.home() / ".hermes",  # default is root-level
    },
    "painpoint-miner": {
        "name": "矿工",
        "base_dir": Path.home() / ".hermes" / "profiles" / "painpoint-miner",
    },
    "bbb-consultant": {
        "name": "同事顾问",
        "base_dir": Path.home() / ".hermes" / "profiles" / "bbb-consultant",
    },
}

OUTPUT_DIRS = {
    "mined": Path.home() / "Desktop" / "配方" / "mined",
    "autocreated": Path.home() / "Desktop" / "配方" / "AutoCreated",
}

DASHBOARD_DIR = Path.home() / ".hermes" / "dashboard"
STATE_FILE = DASHBOARD_DIR / "state.json"
EVENTS_FILE = DASHBOARD_DIR / "events.jsonl"

class DashboardCollector:
    def __init__(self):
        self.state = self.load_state()
        self.profiles = {}
        self.new_events = []
    
    def collect(self):
        """Main collection cycle — runs every 30s"""
        for name, config in PROFILES.items():
            self.collect_profile(name, config)
        self.collect_pipeline_state()
        self.detect_state_changes()
        self.save_state()
    
    def collect_profile(self, name, config):
        """Collect all signals for one profile"""
        state = {
            "name": name,
            "display_name": config["name"],
            "status": self.infer_status(config["base_dir"]),
            "last_activity": self.get_last_activity(config["base_dir"]),
            "last_activity_type": self.get_last_activity_type(config["base_dir"]),
            "current_task": self.get_current_task(config["base_dir"]),
            "gateway": self.check_gateway(config["base_dir"]),
            "cron": self.check_cron(name),
            "recent_outputs": self.get_recent_outputs(name),
            "error_count_24h": self.count_errors_24h(config["base_dir"]),
        }
        self.profiles[name] = state
    
    def detect_state_changes(self):
        """Compare current vs previous state, emit events for changes"""
        for name, current in self.profiles.items():
            previous = self.state.get("profiles", {}).get(name, {})
            
            if previous.get("status") != current["status"]:
                self.emit_event(
                    type="status_change",
                    profile=name,
                    message=f"Status changed: {previous.get('status', '?')} → {current['status']}",
                    severity="info" if current["status"] != "error" else "warning",
                )
            
            if current["error_count_24h"] > previous.get("error_count_24h", 0):
                self.emit_event(
                    type="error",
                    profile=name,
                    message=f"New errors detected: {current['error_count_24h']} in last 24h",
                    severity="error",
                )
    
    def collect_pipeline_state(self):
        """Track Miner → Sync → AutoCraft pipeline"""
        # Check for new mined recipes
        mined_index = self.read_json(OUTPUT_DIRS["mined"] / "index.json")
        autocreated_files = self.list_recent(OUTPUT_DIRS["autocreated"])
        # Correlate and build pipeline stages
        ...
    
    def emit_event(self, type, profile, message, severity="info", details=None):
        event = {
            "id": generate_uuid(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profile": profile,
            "type": type,
            "severity": severity,
            "message": message,
            "details": details or {},
        }
        self.new_events.append(event)
    
    def save_state(self):
        """Write merged state to cache file"""
        merged = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profiles": self.profiles,
            "events": self.state.get("events", [])[-99:] + self.new_events,
            "pipelines": self.state.get("pipelines", []),
            "alerts": self.build_alerts(),
        }
        DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
        write_json(STATE_FILE, merged)
        # Append new events to JSONL
        append_jsonl(EVENTS_FILE, self.new_events)
```

### 5.4 Cron Integration

Add a new cron job to the global cron system:

```json
{
  "id": "dashboard-collector",
  "name": "Dashboard State Collector",
  "script": "dashboard-collector.py",
  "schedule": { "kind": "interval", "minutes": 0.5, "display": "every 30s" },
  "no_agent": true,
  "enabled": true
}
```

**Note:** If Hermes cron doesn't support sub-minute intervals, fall back to 1-minute with the understanding that dashboard refresh will be 30s (collector) + 30s (UI poll) = ~60s effective latency.

### 5.5 File Structure

```
~/.hermes/dashboard/
├── state.json              # Current state cache (updated every 30s)
├── events.jsonl            # Append-only event log
├── pipelines.json          # Pipeline run history
├── collector.py            # Main collector script
└── status.html             # Dashboard UI (self-contained)
```

---

## 6. UI/UX Design

### 6.1 Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  🤖 Hermes Cross-Profile Dashboard                    [🔄 Auto: 30s] │
│  Last updated: 2026-06-07 16:30:05 CST              [📊 Export]     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐        │
│  │  🟢 马明主       │ │  🔵 矿工        │ │  🟡 同事顾问     │        │
│  │  ACTIVE         │ │  ACTIVE         │ │  IDLE           │        │
│  │  Last: 2m ago   │ │  Last: 1m ago   │ │  Last: 15m ago  │        │
│  │  Task: 大脑巡检  │ │  Task: 挖掘痛点  │ │  Task: —        │        │
│  │  Errors: 0      │ │  Errors: 1      │ │  Errors: 0      │        │
│  │  ⏱ Gateway: ✓   │ │  ⏱ Gateway: ✓   │ │  ⏱ Gateway: ✗   │        │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘        │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  📡 Activity Timeline                                                │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  16:30:05  🟢 [default]       Cron executed: 大脑巡检        │    │
│  │  16:29:12  🔵 [miner]        New recipe mined: fine-risk-.. │    │
│  │  16:28:45  🔵 [miner]        Mining session started         │    │
│  │  16:27:30  🔄 [sync]         recipe-sync.sh completed: OK   │    │
│  │  16:25:10  ⚠️  [miner]        Error in agent.log (stack trace│    │
│  │  ...                                                              │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  📦 Output Tracker                                                   │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Profile        │ Output           │ Time    │ Status │ Path  │    │
│  │  ───────────────┼──────────────────┼─────────┼────────┼───────│    │
│  │  🔵 矿工        │ fine-risk-..     │ 16:29   │ ✓ OK   │ mined/│    │
│  │  🔵 矿工        │ chaos-account..  │ 16:15   │ ✓ OK   │ mined/│    │
│  │  🟢 马明主      │ 红烧肉 recipe    │ 15:42   │ ✓ OK   │ AutoC │    │
│  │  🟢 马明主      │ sync report      │ 15:30   │ ✓ OK   │ SyncB │    │
│  │  🟡 同事顾问    │ 销售演练.md      │ 14:20   │ ✓ OK   │ AutoC │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  🔄 Pipeline View: Miner → Sync → AutoCraft → Deploy                 │
│                                                                      │
│  Run #47  started 16:28 ─────────────────────────────── [RUNNING]   │
│  ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐                       │
│  │ Mine │───▶│ Sync │───▶│ Craft│───▶│Deploy│                       │
│  │  ✅   │    │  ✅   │    │  🔄   │    │  ⏳   │                       │
│  │16:28 │    │16:29 │    │16:30 │    │      │                       │
│  └──────┘    └──────┘    └──────┘    └──────┘                       │
│  Artifact: fine-risk-detector                                       │
│                                                                      │
│  Run #46  completed 16:15 ──────────────────────────── [✅ DONE]    │
│  ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐                       │
│  │ Mine │───▶│ Sync │───▶│ Craft│───▶│Deploy│                       │
│  │  ✅   │    │  ✅   │    │  ✅   │    │  ✅   │                       │
│  └──────┘    └──────┘    └──────┘    └──────┘                       │
│  Artifact: chaos-account-clerk                                      │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  ⚠️  Alerts                                                          │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  🟡 [16:25] miner: Agent error in session 20260607_145032   │    │
│  │     → Gateway recovered automatically                        │    │
│  │                                                              │    │
│  │  🔴 [14:20] sync: recipe-sync.sh failed (exit code 1)      │    │
│  │     → Retry scheduled in 60s                                 │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 Color Scheme

| Status | Color | Emoji | Meaning |
|--------|-------|-------|---------|
| Active | Green `#22c55e` | 🟢 | Gateway running, recent activity |
| Idle | Yellow `#eab308` | 🟡 | Gateway running, no recent activity (>5 min) |
| Error | Red `#ef4444` | 🔴 | Errors in log, gateway may be down |
| Stopped | Gray `#6b7280` | ⚫ | Gateway not running |
| Running (pipeline) | Blue `#3b82f6` | 🔵 | Currently processing |

### 6.3 Interactive Features

- **Auto-refresh toggle** — enable/disable 30s polling
- **Profile filter** — show/hide specific profiles
- **Event filter** — filter by severity (info/warning/error)
- **Timeline search** — search event messages
- **Export** — download state as JSON or events as CSV
- **Dark mode** — toggle between light/dark themes

### 6.4 Technical Implementation

The dashboard is a **single self-contained HTML file** with:
- Embedded CSS (no external dependencies)
- Vanilla JS with `fetch()` to read state.json
- `setInterval()` for 30s polling
- SVG icons (inline, no CDN)
- Responsive design (works on mobile)

---

## 7. Integration Points

### 7.1 Existing Systems

| System | Integration Method | Direction |
|--------|-------------------|-----------|
| **Hermes Cron** | New job for collector; reads existing `jobs.json` | Read + Extend |
| **recipe-sync.sh** | Monitor exit code + log output | Read Only |
| **Kanban** | Read kanban state files for task tracking | Read Only |
| **Gateway Logs** | Parse `gateway.log` and `errors.log` | Read Only |
| **Session JSONL** | Read session files for activity timestamps | Read Only |
| **mined/index.json** | Read for Miner output tracking | Read Only |
| **AutoCreated/** | Directory scan for AutoCraft output | Read Only |

### 7.2 Integration with Existing Dashboard

The existing `status-dashboard.html` at `~/.openclaw/workspace/scripts/status-dashboard.html` is a **single-profile** dashboard. The new cross-profile dashboard:

1. **Replaces** it for multi-profile visibility
2. **Incorporates** useful panels from the existing dashboard
3. **Coexists** — the old dashboard can still be used for detailed single-profile debugging

### 7.3 Notification Integration (Future)

In Phase 3, the dashboard can trigger notifications:
- **Feishu card** when pipeline fails
- **WeChat message** when profile goes to error state
- **Desktop notification** via macOS `osascript`

---

## 8. Phased Rollout Plan

### Phase 1: Foundation (Week 1)

**Goal:** Collector script + state cache + basic HTML dashboard

| Task | Details | Estimated Time |
|------|---------|---------------|
| 1.1 Create `~/.hermes/dashboard/` directory | mkdir + permissions | 5 min |
| 1.2 Write `collector.py` | Profile status inference from gateway.pid, logs, sessions | 2 hours |
| 1.3 Write `state.json` schema | Define and document the JSON structure | 30 min |
| 1.4 Write basic `status.html` | Profile overview cards + auto-refresh | 2 hours |
| 1.5 Add cron job | Register collector in Hermes cron (every 30s-1m) | 15 min |
| 1.6 Test end-to-end | Verify collector runs, state updates, dashboard renders | 1 hour |

**Deliverables:**
- `~/.hermes/dashboard/collector.py`
- `~/.hermes/dashboard/state.json`
- `~/.hermes/dashboard/status.html`
- Cron job registered

**Acceptance Criteria:**
- [ ] Dashboard shows all 3 profiles with correct status
- [ ] Status updates within 60s of profile state change
- [ ] No writes to profile directories
- [ ] Dashboard loads in browser without server

### Phase 2: Enrichment (Week 2)

**Goal:** Activity timeline + output tracker + pipeline view

| Task | Details | Estimated Time |
|------|---------|---------------|
| 2.1 Implement event detection | Status changes, new outputs, errors | 2 hours |
| 2.2 Build activity timeline UI | Chronological event feed with filtering | 2 hours |
| 2.3 Build output tracker UI | Table of recent outputs by profile | 1.5 hours |
| 2.4 Implement pipeline detection | Correlate Miner → Sync → AutoCraft | 3 hours |
| 2.5 Build pipeline view UI | Visual flow diagram | 2 hours |
| 2.6 Add alert panel | Active errors and warnings | 1 hour |
| 2.7 Add dark mode | CSS theme toggle | 30 min |

**Deliverables:**
- Updated `collector.py` with event detection
- Updated `status.html` with all 5 panels
- `~/.hermes/dashboard/events.jsonl` for event history

**Acceptance Criteria:**
- [ ] Timeline shows events from last 24 hours
- [ ] Output tracker lists recent recipes/files
- [ ] Pipeline view shows current + historical runs
- [ ] Alerts display active issues with severity

### Phase 3: Polish & Notifications (Week 3)

**Goal:** Interactive features + notifications + performance optimization

| Task | Details | Estimated Time |
|------|---------|---------------|
| 3.1 Add interactive filters | Profile filter, severity filter, search | 1.5 hours |
| 3.2 Add export functionality | JSON state export, CSV events export | 1 hour |
| 3.3 Add Feishu notifications | Push alert cards to Feishu on errors | 2 hours |
| 3.4 Optimize collector | Only scan changed files, reduce I/O | 1 hour |
| 3.5 Add health check endpoint | Simple script to verify dashboard is working | 30 min |
| 3.6 Write documentation | README.md for dashboard usage | 1 hour |
| 3.7 Load testing | Verify collector handles 100+ events gracefully | 30 min |

**Deliverables:**
- Interactive dashboard with all features
- Notification integration
- `~/.hermes/dashboard/README.md`

**Acceptance Criteria:**
- [ ] Filters work without page reload
- [ ] Export generates valid files
- [ ] Notifications sent within 60s of error detection
- [ ] Collector CPU usage < 1% per run
- [ ] Dashboard loads in < 2 seconds

---

## 9. Security & Isolation Guarantees

### 9.1 Read-Only Access

The collector **never writes** to profile directories. All outputs go to `~/.hermes/dashboard/`:

```
~/.hermes/profiles/<name>/     ← READ ONLY (never modified)
~/.hermes/dashboard/           ← WRITE TARGET (collector output)
```

### 9.2 No Process Injection

The collector does not:
- Inject code into profile gateways
- Modify profile configurations
- Call profile APIs or endpoints
- Use `hermes` CLI commands targeting other profiles

### 9.3 File System Boundaries

| Access Type | Allowed Paths | Forbidden Paths |
|-------------|---------------|-----------------|
| Read | All profile dirs, logs, sessions, cron, mined/, AutoCreated/ | None (read is safe) |
| Write | `~/.hermes/dashboard/` only | All profile directories |

### 9.4 Data Privacy

- No personal message content is collected
- Only metadata is tracked: timestamps, status codes, file names
- Event messages are generated by the collector, not copied from logs
- No data is transmitted off-machine

---

## 10. Future Extensions

### 10.1 Predictive Analytics
- Predict when Miner will complete a batch
- Estimate pipeline completion times
- Alert on anomalous activity patterns

### 10.2 Cross-Profile Task Delegation
- Visual task assignment between profiles
- Dependency-based scheduling
- Automatic retry on failure

### 10.3 Historical Reporting
- Weekly/monthly summary reports
- Output productivity metrics
- Error rate trends

### 10.4 Multi-Machine Support
- If profiles run on different machines, add SSH-based log polling
- State cache synchronization via file sync

---

## Appendix A: File Inventory

### New Files Created

| Path | Purpose |
|------|---------|
| `~/.hermes/dashboard/collector.py` | Main polling script |
| `~/.hermes/dashboard/state.json` | State cache (generated) |
| `~/.hermes/dashboard/events.jsonl` | Event log (generated) |
| `~/.hermes/dashboard/status.html` | Dashboard UI |
| `~/.hermes/dashboard/README.md` | Documentation |
| `~/.hermes/dashboard/tests/test_collector.py` | Unit tests |

### Existing Files Read (No Modification)

| Path | Purpose |
|------|---------|
| `~/.hermes/profiles/<name>/gateway.pid` | Gateway process tracking |
| `~/.hermes/profiles/<name>/logs/gateway.log` | Gateway activity |
| `~/.hermes/profiles/<name>/logs/errors.log` | Error detection |
| `~/.hermes/profiles/<name>/logs/agent.log` | Agent activity |
| `~/.hermes/cron/jobs.json` | Cron job status |
| `~/.hermes/sessions/*.jsonl` | Session activity |
| `~/Desktop/配方/mined/index.json` | Miner output index |
| `~/Desktop/配方/mined/*/` | Individual recipe directories |
| `~/Desktop/配方/AutoCreated/` | AutoCraft output directory |
| `~/.hermes/scripts/recipe-sync.sh` | Sync script (monitor exit) |

---

## Appendix B: Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Collector reads stale data | Low | Low | Add staleness detection; alert if state.json > 2 min old |
| False positive error detection | Medium | Low | Require 2+ error lines within 5 min window |
| Dashboard file grows too large | Medium | Medium | Implement event rotation (keep last 1000 events) |
| Profile directory permissions block read | Low | High | Document required permissions; fallback to degraded mode |
| Cron job conflicts with existing jobs | Low | Medium | Use unique job ID; monitor for collisions |

---

*End of Plan Document*
