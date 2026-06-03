
import streamlit as st
import sys
import os
import uuid
import json
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

from agent_assembler.recipe import Recipe
from agent_assembler.adapters import CozeAdapter, QianwenAdapter
from agent_assembler.deploy import CozeApiClient, QianwenApiClient
from core.storage import TenantManager

st.set_page_config(page_title="Agent Assembler SaaS", layout="wide")

# --- State ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.tenant_id = None
    st.session_state.tenant_name = None
    st.session_state.coze_token = ""
    st.session_state.qianwen_key = ""
    st.session_state.coze_space_id = ""

# --- Auth Page ---
if not st.session_state.logged_in:
    st.title("🔒 Agent Assembler SaaS 登录")
    tab1, tab2 = st.tabs(["登录", "注册新租户"])
    
    with tab1:
        tid = st.text_input("Tenant ID")
        if st.button("进入工作台"):
            name = TenantManager.verify_tenant(tid)
            if name:
                st.session_state.logged_in = True
                st.session_state.tenant_id = tid
                st.session_state.tenant_name = name
                st.rerun()
            else:
                st.error("❌ 租户不存在")
                
    with tab2:
        new_tid = st.text_input("Tenant ID")
        new_name = st.text_input("Name")
        if st.button("注册"):
            if TenantManager.create_tenant(new_tid, new_name):
                st.success("✅ 注册成功")
            else:
                st.error("❌ ID 已存在")

# --- Dashboard ---
else:
    mgr = TenantManager(st.session_state.tenant_id)
    
    with st.sidebar:
        st.write(f"👤 {st.session_state.tenant_name}")
        st.divider()
        st.subheader("⚙️ API 设置")
        st.session_state.coze_token = st.text_input("Coze Token", type="password", value=st.session_state.coze_token)
        st.session_state.coze_space_id = st.text_input("Coze Space ID", value=st.session_state.coze_space_id)
        st.session_state.qianwen_key = st.text_input("Qianwen Key", type="password", value=st.session_state.qianwen_key)
        st.divider()
        if st.button("退出"):
            st.session_state.logged_in = False
            st.rerun()

    st.title("🧩 工作台")
    
    menu = st.radio("选择功能模块", ["🤖 生成通用 Agent", "🎭 场景定制 (Roleplay)", "📊 数据分析"], horizontal=True)

    # --- Module 1: Generic Agent ---
    if menu == "🤖 生成通用 Agent":
        st.header("1. 生成通用业务 Agent")
        with st.form("gen_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Agent 名称")
                desc = st.text_area("描述/背景")
            with col2:
                platform = st.selectbox("目标平台", ["Coze", "Qianwen", "本地网关 (Local ECS)"])
            
            if st.form_submit_button("🚀 生成并保存"):
                recipe = Recipe(name=name, trigger_keywords=[name], skills=[], notes=desc)
                
                if platform == "Coze":
                    adapter = CozeAdapter()
                    config = adapter.export(recipe)
                elif platform == "Qianwen":
                    adapter = QianwenAdapter()
                    config = adapter.export(recipe)
                else:
                    config = {"name": recipe.name, "trigger_keywords": [name], "skills": [], "notes": recipe.notes}
                    
                agent_id = str(uuid.uuid4())[:8]
                if mgr.save_config(agent_id, name, config, platform):
                    st.success(f"✅ Agent '{name}' 已保存！")
                    st.session_state['last_deploy_info'] = {'recipe': recipe, 'config': config, 'platform': platform}
                    st.rerun()

    # --- Module 2: Roleplay / Character Engine (WITH STATE) ---
    elif menu == "🎭 场景定制 (Roleplay)":
        st.header("1. 沉浸式角色场景生成器")
        st.caption("支持定义动态状态（如信任度/好感度），让 Agent 随对话改变态度。")
        
        with st.form("role_form"):
            name = st.text_input("场景名称", value="高难度销售演练")
            keywords_str = st.text_input("触发关键词 (逗号分隔)", value="销售演练, 困难客户")
            
            st.markdown("**👥 角色设定**")
            col1, col2 = st.columns(2)
            with col1:
                user_role_desc = st.text_area("用户扮演 (User Persona)", value="我是初级销售经理")
            with col2:
                opp_role_desc = st.text_area("对手设定 (Opponent Role)", value="你是一个挑剔的客户，对价格敏感")
            
            st.markdown("**📈 动态状态管理**")
            state_vars_str = st.text_input("状态变量 (键:初始值, 键:初始值)", value="Trust:50, Anger:20")
            state_rules_str = st.text_area("变化规则 (自然语言描述)", value="如果用户报价低于预期，Anger 增加；如果用户表现出专业，Trust 增加。")

            if st.form_submit_button("⚡ 生成角色引擎配置"):
                keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
                
                # Parse State Variables
                state_vars = {}
                for pair in state_vars_str.split(","):
                    if ":" in pair:
                        k, v = pair.split(":")
                        state_vars[k.strip()] = int(v.strip())
                        
                notes = f"USER:{user_role_desc}|OPP:{opp_role_desc}"
                
                recipe_config = {
                    "name": name,
                    "trigger_keywords": keywords,
                    "skills": ["immersive-rpg-simulation"],
                    "notes": notes,
                    "engine_config": {
                        "type": "character-v1",
                        "initial_state": state_vars,
                        "state_rules": state_rules_str,
                        "user_persona": user_role_desc,
                        "opponent_persona": opp_role_desc
                    }
                }
                
                agent_id = str(uuid.uuid4())[:8]
                if mgr.save_config(agent_id, name, recipe_config, "Local RPG"):
                    st.success(f"✅ 角色场景 '{name}' (带状态) 已生成！")
                    st.session_state['last_roleplay_info'] = recipe_config
                    st.rerun()

        if 'last_roleplay_info' in st.session_state:
            st.subheader("生成结果")
            info = st.session_state['last_roleplay_info']
            st.json(info)
            st.download_button(
                label="📥 下载 JSON",
                data=json.dumps(info, ensure_ascii=False, indent=2),
                file_name=f"{info['name']}_rpg.json",
                mime="application/json"
            )

    # --- Module 3: Analytics ---
    elif menu == "📊 数据分析":
        st.subheader("📊 运营数据看板")
        stats = mgr.get_stats()
        k1, k2, k3 = st.columns(3)
        k1.metric("总 Agent 数", stats['total_agents'])
        k2.metric("Coze 部署", stats['platforms'].get('Coze', 0))
        k3.metric("本地运行", stats['platforms'].get('Local ECS', 0) + stats['platforms'].get('Local RPG', 0))
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**平台分布**")
            if stats['platforms']:
                st.bar_chart(pd.DataFrame([stats['platforms']]))
        
    # --- Agent List ---
    st.header("我的 Agent 列表")
    configs = mgr.get_configs()
    if not configs:
        st.info("暂无 Agent")
    else:
        for c in configs:
            with st.expander(f"{c['name']} ({c['platform']})"):
                st.json(json.loads(c['content']))
