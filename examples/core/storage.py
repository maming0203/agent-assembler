
import os
import json
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "agents.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS agent_configs (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            name TEXT,
            content TEXT,
            platform TEXT,
            created_at INTEGER,
            FOREIGN KEY(tenant_id) REFERENCES tenants(id)
        )
    ''')
    conn.commit()
    conn.close()

class TenantManager:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", tenant_id)
        os.makedirs(self.data_dir, exist_ok=True)
        init_db()

    @staticmethod
    def create_tenant(tenant_id, name):
        init_db()
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("INSERT INTO tenants (id, name, created_at) VALUES (?, ?, ?)", 
                         (tenant_id, name, int(time.time())))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    @staticmethod
    def verify_tenant(tenant_id):
        init_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name FROM tenants WHERE id=?", (tenant_id,))
        res = c.fetchone()
        conn.close()
        return res[0] if res else None

    def save_config(self, agent_id, name, content, platform):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("INSERT INTO agent_configs (id, tenant_id, name, content, platform, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (agent_id, self.tenant_id, name, json.dumps(content), platform, int(time.time())))
            file_path = os.path.join(self.data_dir, f"{agent_id}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            conn.commit()
            return True
        except Exception as e:
            print(f"Save error: {e}")
            return False
        finally:
            conn.close()

    def get_configs(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM agent_configs WHERE tenant_id=? ORDER BY created_at DESC", (self.tenant_id,))
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_stats(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Total Agents
        c.execute("SELECT count(*) FROM agent_configs WHERE tenant_id=?", (self.tenant_id,))
        total = c.fetchone()[0]
        
        # Platform distribution
        c.execute("SELECT platform, count(*) as cnt FROM agent_configs WHERE tenant_id=? GROUP BY platform", (self.tenant_id,))
        platforms = {row[0]: row[1] for row in c.fetchall()}
        
        # Activity (Last 7 days) - Mocked based on creation date since we don't have usage logs yet
        # We will visualize creation trends
        c.execute("SELECT created_at FROM agent_configs WHERE tenant_id=? ORDER BY created_at", (self.tenant_id,))
        dates = [row[0] for row in c.fetchall()]
        
        conn.close()
        return {
            "total_agents": total,
            "platforms": platforms,
            "creation_dates": dates
        }

    def delete_config(self, agent_id):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("DELETE FROM agent_configs WHERE id=? AND tenant_id=?", (agent_id, self.tenant_id))
            conn.commit()
            file_path = os.path.join(self.data_dir, f"{agent_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            print(f"Delete error: {e}")
            return False
        finally:
            conn.close()
