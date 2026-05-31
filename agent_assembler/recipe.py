
import json
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

@dataclass
class Recipe:
    name: str
    trigger_keywords: List[str]
    skills: List[str]
    notes: str = ""
    routing: Optional[str] = None
    
    @classmethod
    def from_json(cls, path: str):
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(
            name=data.get('name', Path(path).stem),
            trigger_keywords=data.get('trigger_keywords', []),
            skills=data.get('skills', []),
            notes=data.get('notes', ""),
            routing=data.get('routing')
        )
