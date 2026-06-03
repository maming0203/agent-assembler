
import requests
import json
from typing import Dict, Any, List, Optional

class CozeApiClient:
    # China Domestic API
    API_BASE = "https://api.coze.cn/v1"
    
    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def create_bot(self, name: str, description: str, prompt: str, space_id: str) -> Optional[str]:
        """
        Create a bot on Coze (v1 API).
        Returns bot_id if success.
        """
        url = f"{self.API_BASE}/bot/create"
        payload = {
            "space_id": space_id,
            "name": name,
            "description": description,
            "prompt_info": {
                "prompt": prompt
            }
        }
        
        try:
            resp = requests.post(url, headers=self.headers, json=payload)
            data = resp.json()
            if data.get("code") == 0:
                bot_id = data.get("data", {}).get("bot_id")
                print(f"Bot created: {bot_id}")
                return bot_id
            else:
                error_msg = data.get("msg", "Unknown error")
                print(f"Coze API Error: {error_msg}")
                return None
        except Exception as e:
            print(f"Request Error: {e}")
            return None

    def install_connector(self, connector_id: str, workspace_id: str) -> bool:
        """
        Add a publishing channel (Connector) to the workspace.
        e.g. connector_id for Douyin, Feishu, etc.
        """
        url = f"{self.API_BASE}/connectors/{connector_id}/install"
        payload = {
            "workspace_id": workspace_id
        }
        
        try:
            resp = requests.post(url, headers=self.headers, json=payload)
            data = resp.json()
            if data.get("code") == 0:
                print(f"Connector {connector_id} installed to workspace {workspace_id}")
                return True
            else:
                print(f"Install Connector Error: {data.get('msg')}")
                return False
        except Exception as e:
            print(f"Request Error: {e}")
            return False

    def publish_bot(self, bot_id: str, connector_ids: List[str] = None) -> bool:
        """
        Publish the bot to specified channels.
        Default connector_ids: ['1024'] (API/SDK)
        """
        if connector_ids is None:
            connector_ids = ["1024"]
            
        url = f"{self.API_BASE}/bot/publish"
        payload = {
            "bot_id": bot_id,
            "connector_ids": connector_ids
        }
        
        try:
            resp = requests.post(url, headers=self.headers, json=payload)
            data = resp.json()
            if data.get("code") == 0:
                print(f"Bot {bot_id} published to {connector_ids}")
                return True
            else:
                print(f"Publish Bot Error: {data.get('msg')}")
                return False
        except Exception as e:
            print(f"Publish Error: {e}")
            return False

