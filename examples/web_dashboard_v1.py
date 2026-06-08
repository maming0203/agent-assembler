"""Agent Assembler SaaS Dashboard v1.0

多租户工作台：登录 → 工作台 → Agent 管理 → Recipe 管理 → 发布 → Analytics

运行: streamlit run web_dashboard_v1.py
"""
import streamlit as st
import requests
import json
import os
from datetime import datetime

# ──────────────────────────────────────────
# 配置
# ──────────────────────────────────────────

API_BASE = os.environ.get("ASSEMBLER_API_BASE", "http://localhost:8644")

st.set_page_config(page_title="Agent Assembler SaaS", layout="wide", page_icon="🧩")

# ──────────────────────────────────────────
# 状态管理
# ──────────────────────────────────────────

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.tenant_id = None
    st.session_state.tenant_name = None
    st.session_state.api_key = None
    st.session_state.coze_token = ""
    st.session_state.coze_space_id = ""
    st.session_state.qianwen_key = ""

# ──────────────────────────────────────────
# API 客户端
# ──────────────────────────────────────────

def api_get(path, headers=None):
    h = headers or {}
    if st.session_state.api_key:
        h["x-api-key"] = st.session_state.api_key
    try:
        return requests.get(f"{API_BASE}{path}", headers=h, timeout=10).json()
    except Exception as e:
        return {"error": str(e)}

def api_post(path, data=None, headers=None):
    h = (headers or {}).copy()
    if st.session_state.api_key:
        h["x-api-key"] = st.session_state.api_key
    try:
        resp = requests.post(f"{API_BASE}{path}", json=data, headers=h, timeout=30)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def api_delete(path, headers=None):
    h = headers or {}
    if st.session_state.api_key:
        h["x-api-key"] = st.session_state.api_key
    try:
        resp = requests.delete(f"{API_BASE}{path}", headers=h, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# ──────────────────────────────────────────
# 登录页面
# ──────────────────────────────────────────

def login_page():
    st.title("🔒 Agent Assembler SaaS 登录")
    st.caption(f"API: `{API_BASE}`")
    
    tab1, tab2 = st.tabs(["登录", "创建账户"])
    
    with tab1:
        st.header("已有账户")
        device_id = st.text_input("Tenant ID", key="login_tid")
        if st.button("进入工作台", type="primary", use_container_width=True):
            if not device_id:
                st.error("请输入 Tenant ID")
                return
            resp = api_get(f"/api/v1/login?device_id={device_id}")
            if "api_key" in resp:
                st.session_state.logged_in = True
                st.session_state.tenant_id = device_id
                st.session_state.tenant_name = device_id
                st.session_state.api_key = resp["api_key"]
                st.rerun()
            else:
                st.error(f"登录失败: {resp}")

    with tab2:
        st.header("创建新账户")
        new_tid = st.text_input("Tenant ID", key="reg_tid")
        new_name = st.text_input("名称", key="reg_name")
        if st.button("注册", use_container_width=True):
            if not new_tid or not new_name:
                st.error("Tenant ID 和名称不能为空")
                return
            # 注册即登录
            resp = api_get(f"/api/v1/login?device_id={new_tid}")
            if "api_key" in resp:
                st.session_state.logged_in = True
                st.session_state.tenant_id = new_tid
                st.session_state.tenant_name = new_name
                st.session_state.api_key = resp["api_key"]
                st.success("✅ 注册成功，已进入工作台")
                st.rerun()
            else:
                st.error(f"注册失败: {resp}")


# ──────────────────────────────────────────
# 工作台
# ──────────────────────────────────────────

def dashboard_page():
    # Sidebar
    with st.sidebar:
        st.write(f"👤 **{st.session_state.tenant_name}**")
        st.caption(f"Tenant: `{st.session_state.tenant_id}`")
        st.divider()
        
        st.subheader("⚙️ 发布设置")
        st.session_state.coze_token = st.text_input(
            "Coze Token", type="password",
            value=st.session_state.coze_token, key="sidebar_coze"
        )
        st.session_state.coze_space_id = st.text_input(
            "Coze Space ID",
            value=st.session_state.coze_space_id, key="sidebar_space"
        )
        st.session_state.qianwen_key = st.text_input(
            "千问 Key", type="password",
            value=st.session_state.qianwen_key, key="sidebar_qianwen"
        )
        st.divider()
        
        if st.button("🚪 退出", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.api_key = None
            st.rerun()

    # 导航
    menu = st.radio(
        "选择功能模块",
        ["📊 工作台概览", "🤖 Agent 管理", "🥘 Recipe 配方", "🚀 一键发布", "📈 Analytics"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if menu == "📊 工作台概览":
        overview_page()
    elif menu == "🤖 Agent 管理":
        agents_page()
    elif menu == "🥘 Recipe 配方":
        recipes_page()
    elif menu == "🚀 一键发布":
        deploy_page()
    elif menu == "📈 Analytics":
        analytics_page()


# ──────────────────────────────────────────
# 概览
# ──────────────────────────────────────────

def overview_page():
    st.header("📊 工作台概览")
    
    # 获取数据
    summary = api_get("/api/v1/metrics/summary")
    recipes = api_get("/api/v1/recipes")
    agents = api_get("/api/v1/agents")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_agents = summary.get("total_users", 0) if isinstance(summary, dict) else 0
    total_runs = summary.get("total_runs", 0) if isinstance(summary, dict) else 0
    total_recipes = recipes.get("total", 0) if isinstance(recipes, dict) else 0
    total_api_agents = len(agents.get("agents", [])) if isinstance(agents, dict) else 0
    
    col1.metric("Agent 数", total_agents)
    col2.metric("运行次数", total_runs)
    col3.metric("配方数", total_recipes)
    col4.metric("可用 Agent", total_api_agents)
    
    st.divider()
    
    # 快捷操作
    st.subheader("⚡ 快捷操作")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🤖 创建 Agent", use_container_width=True):
            st.session_state._menu_index = 1
            st.rerun()
    with col2:
        if st.button("🥘 创建配方", use_container_width=True):
            st.session_state._menu_index = 2
            st.rerun()
    with col3:
        if st.button("🚀 发布到 Coze", use_container_width=True):
            st.session_state._menu_index = 3
            st.rerun()
    
    # 计划分布
    if isinstance(summary, dict) and "plan_distribution" in summary:
        st.divider()
        st.subheader("📋 计划分布")
        plans = summary["plan_distribution"]
        if plans:
            st.bar_chart({"计划": plans})
        else:
            st.info("暂无数据")


# ──────────────────────────────────────────
# Agent 管理
# ──────────────────────────────────────────

def agents_page():
    st.header("🤖 Agent 管理")
    
    agents = api_get("/api/v1/agents")
    agent_list = agents.get("agents", []) if isinstance(agents, dict) else []
    
    if not agent_list:
        st.info("暂无 Agent")
        return
    
    # 创建新 Agent
    with st.expander("➕ 创建新 Agent"):
        with st.form("new_agent_form"):
            col1, col2 = st.columns(2)
            with col1:
                agent_name = st.text_input("Agent 名称")
                agent_desc = st.text_area("描述")
            with col2:
                platform = st.selectbox("目标平台", ["Coze", "Qianwen", "Local"])
            if st.form_submit_button("创建"):
                if agent_name:
                    resp = api_post("/api/v1/export", {
                        "name": agent_name,
                        "description": agent_desc,
                        "platform": platform,
                    })
                    if resp.get("status") == "success":
                        st.success(f"✅ Agent '{agent_name}' 已创建")
                        st.json(resp.get("config", {}))
                    else:
                        st.error(f"创建失败: {resp}")
                else:
                    st.error("Agent 名称不能为空")
    
    st.divider()
    
    # Agent 列表
    for agent in agent_list:
        with st.expander(f"**{agent.get('name')}** — {agent.get('description', '')[:80]}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"ID: `{agent.get('id')}`")
                if agent.get("tags"):
                    st.caption(f"Tags: {', '.join(agent['tags'])}")
            with col2:
                if st.button(f"🗑️", key=f"del_{agent['id']}"):
                    st.warning(f"删除功能待实现: {agent['name']}")


# ──────────────────────────────────────────
# Recipe 配方管理
# ──────────────────────────────────────────

def recipes_page():
    st.header("🥘 Recipe 配方管理")
    
    # 创建新配方
    with st.expander("➕ 创建新配方"):
        with st.form("new_recipe_form"):
            col1, col2 = st.columns(2)
            with col1:
                recipe_name = st.text_input("配方名称", key="recipe_name_input")
                keywords = st.text_input("触发关键词（逗号分隔）", key="recipe_kw")
            with col2:
                routing = st.text_input("路由 ID（可选）", key="recipe_routing")
                script_path = st.text_input("脚本路径（可选）", key="recipe_script")
            notes = st.text_area("备注/说明", key="recipe_notes")
            
            if st.form_submit_button("创建配方"):
                if not recipe_name or not keywords:
                    st.error("名称和关键词不能为空")
                else:
                    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
                    resp = api_post("/api/v1/recipes", {
                        "name": recipe_name,
                        "trigger_keywords": kw_list,
                        "skills": [],
                        "notes": notes,
                        "routing": routing or None,
                        "script_path": script_path or None,
                    })
                    if resp.get("status") == "created":
                        st.success(f"✅ 配方 '{recipe_name}' 已创建")
                        st.rerun()
                    else:
                        st.error(f"创建失败: {resp}")
    
    st.divider()
    
    # 搜索
    search_q = st.text_input("🔍 搜索配方", placeholder="输入关键词搜索...")
    if search_q:
        results = api_get(f"/api/v1/recipes/search?q={search_q}")
        matches = results.get("recipes", []) if isinstance(results, dict) else []
        st.caption(f"找到 {len(matches)} 个匹配")
        for r in matches:
            with st.expander(f"**{r.get('name')}** — {r.get('notes', '')[:60]}"):
                st.caption(f"关键词: {', '.join(r.get('keywords', []))}")
                st.json(r)
    else:
        # 列出所有
        recipes = api_get("/api/v1/recipes")
        recipe_list = recipes.get("recipes", []) if isinstance(recipes, dict) else []
        st.caption(f"共 {len(recipe_list)} 个配方")
        
        if recipe_list:
            for r in recipe_list:
                with st.expander(f"**{r.get('name')}** {'🔒' if r.get('is_premium') else ''}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.caption(f"关键词: {', '.join(r.get('keywords', []))}")
                        st.caption(f"技能: {', '.join(r.get('skills', [])) if r.get('skills') else '无'}")
                        if r.get("notes"):
                            st.caption(f"备注: {r['notes'][:100]}")
                    with col2:
                        if st.button(f"🗑️ 删除", key=f"del_recipe_{r.get('name')}"):
                            resp = api_delete(f"/api/v1/recipes/{r.get('name')}")
                            if resp.get("status") == "deleted":
                                st.success(f"已删除: {r.get('name')}")
                                st.rerun()
                            else:
                                st.error(f"删除失败: {resp}")
        else:
            st.info("暂无配方，点击上方创建")


# ──────────────────────────────────────────
# 一键发布
# ──────────────────────────────────────────

def deploy_page():
    st.header("🚀 一键发布")
    
    tab1, tab2 = st.tabs(["发布到 Coze", "发布到千问"])
    
    with tab1:
        st.subheader("发布到 Coze")
        
        if not st.session_state.coze_token:
            st.warning("⚠️ 请在侧边栏设置 Coze Token 和 Space ID")
        
        with st.form("deploy_coze_form"):
            name = st.text_input("Agent 名称", key="coze_name")
            desc = st.text_area("描述", key="coze_desc")
            
            if st.form_submit_button("🚀 发布到 Coze", type="primary"):
                if not name:
                    st.error("名称不能为空")
                elif not st.session_state.coze_token or not st.session_state.coze_space_id:
                    st.error("请先在侧边栏设置 Coze Token 和 Space ID")
                else:
                    resp = api_post("/api/v1/deploy/coze", {
                        "name": name,
                        "description": desc,
                        "platform": "Coze",
                    })
                    if resp.get("status") == "ready":
                        st.success("✅ 发布配置已准备")
                        st.json(resp.get("bot_info", {}))
                    else:
                        st.error(f"发布失败: {resp}")
    
    with tab2:
        st.subheader("发布到千问")
        
        if not st.session_state.qianwen_key:
            st.warning("⚠️ 请在侧边栏设置千问 Key")
        
        with st.form("deploy_qianwen_form"):
            name = st.text_input("Agent 名称", key="qianwen_name")
            desc = st.text_area("描述", key="qianwen_desc")
            
            if st.form_submit_button("🚀 发布到千问", type="primary"):
                if not name:
                    st.error("名称不能为空")
                else:
                    resp = api_post("/api/v1/deploy/qianwen", {
                        "name": name,
                        "description": desc,
                        "platform": "Qianwen",
                    })
                    if resp.get("status") == "ready":
                        st.success("✅ 发布配置已准备")
                        st.json(resp.get("config", {}))
                    else:
                        st.error(f"发布失败: {resp}")


# ──────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────

def analytics_page():
    st.header("📈 Analytics 数据看板")
    
    metrics = api_get("/api/v1/metrics")
    summary = api_get("/api/v1/metrics/summary")
    timeseries = api_get("/api/v1/metrics/timeseries?days=7")
    
    if not isinstance(metrics, dict) or "error" in metrics:
        st.error(f"获取数据失败: {metrics}")
        return
    
    # 顶部指标
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总运行次数", metrics.get("total_runs", 0))
    with col2:
        st.metric("用户数", metrics.get("users", 0))
    with col3:
        total_ts = timeseries.get("total", 0) if isinstance(timeseries, dict) else 0
        st.metric("近 7 天运行", total_ts)
    
    st.divider()
    
    # 汇总
    if isinstance(summary, dict) and "error" not in summary:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总用户", summary.get("total_users", 0))
        with col2:
            st.metric("总运行", summary.get("total_runs", 0))
        with col3:
            st.metric("活跃配方", summary.get("active_recipes", 0))
        
        # 计划分布
        plans = summary.get("plan_distribution", {})
        if plans:
            st.divider()
            st.subheader("📋 计划分布")
            st.bar_chart({"计划": plans})
    
    # Top 用户
    top_users = metrics.get("top_users", [])
    if top_users:
        st.divider()
        st.subheader("🏆 Top 用户")
        import pandas as pd
        df = pd.DataFrame(top_users)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 时序数据
    if isinstance(timeseries, dict) and timeseries.get("data"):
        st.divider()
        st.subheader("📊 运行趋势（近 7 天）")
        ts_data = timeseries["data"]
        ts_df = pd.DataFrame(ts_data)
        st.bar_chart(ts_df.set_index("user")["runs"])


# ──────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────

if not st.session_state.logged_in:
    login_page()
else:
    dashboard_page()
