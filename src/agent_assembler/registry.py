"""Recipe Registry — 配方市场基础结构（注册、搜索、版本管理）"""
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path


# ──────────────────────────────────────────
# RecipeVersion
# ──────────────────────────────────────────

@dataclass
class RecipeVersion:
    """配方版本记录"""
    version: str          # 语义化版本：0.1.0
    author: str = ""
    created_at: str = ""
    changelog: str = ""
    file_path: str = ""
    
    def to_dict(self) -> dict[str, str]:
        return {
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at,
            "changelog": self.changelog,
            "file_path": self.file_path,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, str]) -> RecipeVersion:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ──────────────────────────────────────────
# RecipeRegistry
# ──────────────────────────────────────────

class RecipeRegistry:
    """配方市场注册表——管理配方的注册、搜索、版本、导入导出。
    
    用法：
        registry = RecipeRegistry(registry_dir="./recipes")
        registry.scan()
        results = registry.search("财务分析")
        registry.export_recipe("财务分析", "./export/")
    """
    
    def __init__(self, registry_dir: str = "", recipes: list | None = None):
        self.registry_dir = os.path.abspath(registry_dir) if registry_dir else ""
        self._recipes: dict[str, Any] = {}       # name → recipe data
        self._versions: dict[str, list[RecipeVersion]] = {}  # name → [versions]
        self._tags_index: dict[str, list[str]] = {}  # tag → [recipe names]
        self._keyword_index: dict[str, list[str]] = {}  # keyword → [recipe names]
        
        # 如果传入现有 recipes 列表，直接注册
        if recipes:
            for r in recipes:
                self.register(r)
    
    def register(self, recipe_data: dict[str, Any]) -> str:
        """注册一个配方到注册表"""
        name = recipe_data.get("name", "")
        if not name:
            raise ValueError("Recipe must have a name")
        self._recipes[name] = recipe_data
        
        # 构建关键词索引
        keywords = recipe_data.get("trigger_keywords", [])
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in self._keyword_index:
                self._keyword_index[kw_lower] = []
            if name not in self._keyword_index[kw_lower]:
                self._keyword_index[kw_lower].append(name)
        
        # 构建标签索引
        tags = recipe_data.get("tags", [])
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower not in self._tags_index:
                self._tags_index[tag_lower] = []
            if name not in self._tags_index[tag_lower]:
                self._tags_index[tag_lower].append(name)
        
        return name
    
    def scan(self) -> int:
        """从 registry_dir 扫描所有 JSON 配方文件"""
        if not self.registry_dir or not os.path.exists(self.registry_dir):
            return 0
        
        count = 0
        for root, _, files in os.walk(self.registry_dir):
            for fname in files:
                if fname.endswith(".json"):
                    path = os.path.join(root, fname)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        self.register(data)
                        count += 1
                    except Exception as e:
                        print(f"[RecipeRegistry] Failed to load {path}: {e}")
        return count
    
    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """搜索配方——加权关键词匹配。
        
        评分规则：
        - 完全匹配配方名：+100 分
        - 匹配 trigger_keywords（精确）：+10 分
        - 匹配 trigger_keywords（子串）：+5 分
        - 匹配 tags：+8 分
        - 匹配 notes（子串）：+3 分
        """
        query_lower = query.lower()
        scores: dict[str, float] = {}
        
        for name, recipe in self._recipes.items():
            score = 0.0
            
            # 配方名完全匹配
            if query_lower == name.lower():
                score += 100
            
            # 配方名子串匹配
            if query_lower in name.lower():
                score += 50
            
            # 关键词精确匹配
            keywords = recipe.get("trigger_keywords", [])
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower == query_lower:
                    score += 10
                elif query_lower in kw_lower or kw_lower in query_lower:
                    score += 5
            
            # 标签匹配
            tags = recipe.get("tags", [])
            for tag in tags:
                if query_lower in tag.lower():
                    score += 8
            
            # notes 子串匹配
            notes = recipe.get("notes", "")
            if query_lower in notes.lower():
                score += 3
            
            if score > 0:
                scores[name] = score
        
        # 按分数排序，返回 top_k
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"recipe": self._recipes[name], "score": score}
            for name, score in sorted_results[:top_k]
        ]
    
    def list_recipes(self, tag: str = "") -> list[dict[str, Any]]:
        """列出所有配方，可按标签过滤"""
        if tag:
            tag_lower = tag.lower()
            names = self._tags_index.get(tag_lower, [])
            return [
                {"name": name, "recipe": self._recipes[name]}
                for name in names if name in self._recipes
            ]
        return [
            {"name": name, "recipe": recipe}
            for name, recipe in self._recipes.items()
        ]
    
    def get(self, name: str) -> Optional[dict[str, Any]]:
        return self._recipes.get(name)
    
    def remove(self, name: str) -> bool:
        """从注册表移除配方"""
        if name in self._recipes:
            recipe = self._recipes.pop(name)
            # 清理索引
            for kw in recipe.get("trigger_keywords", []):
                if kw in self._keyword_index:
                    self._keyword_index[kw] = [
                        n for n in self._keyword_index[kw] if n != name
                    ]
            for tag in recipe.get("tags", []):
                if tag in self._tags_index:
                    self._tags_index[tag] = [
                        n for n in self._tags_index[tag] if n != name
                    ]
            return True
        return False
    
    def count(self) -> int:
        return len(self._recipes)
    
    def tags(self) -> list[str]:
        return list(self._tags_index.keys())
    
    def export_recipe(self, name: str, export_dir: str) -> str:
        """导出配方到指定目录"""
        recipe = self._recipes.get(name)
        if not recipe:
            raise KeyError(f"Recipe '{name}' not found")
        
        os.makedirs(export_dir, exist_ok=True)
        path = os.path.join(export_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recipe, f, indent=2, ensure_ascii=False)
        return path
    
    def import_recipe(self, path: str) -> str:
        """从 JSON 文件导入配方"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.register(data)
    
    def export_all(self, export_dir: str) -> list[str]:
        """导出所有配方"""
        os.makedirs(export_dir, exist_ok=True)
        paths = []
        for name, recipe in self._recipes.items():
            path = self.export_recipe(name, export_dir)
            paths.append(path)
        return paths
    
    def import_directory(self, directory: str) -> int:
        """从目录批量导入配方"""
        if not os.path.exists(directory):
            return 0
        count = 0
        for fname in os.listdir(directory):
            if fname.endswith(".json"):
                path = os.path.join(directory, fname)
                try:
                    self.import_recipe(path)
                    count += 1
                except Exception as e:
                    print(f"[RecipeRegistry] Failed to import {path}: {e}")
        return count
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_dir": self.registry_dir,
            "count": len(self._recipes),
            "recipes": self._recipes,
            "tags": list(self._tags_index.keys()),
        }
    
    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, path: str) -> RecipeRegistry:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        registry = cls(registry_dir=data.get("registry_dir", ""))
        for recipe in data.get("recipes", {}).values():
            registry.register(recipe)
        return registry
    
    def __repr__(self) -> str:
        return f"RecipeRegistry(count={len(self._recipes)}, dir={self.registry_dir!r})"
