
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from ..recipe import Recipe

class BaseAdapter(ABC):
    """Base class for all platform adapters."""
    
    PLATFORM_NAME = "Base"
    
    @abstractmethod
    def export(self, recipe: Recipe) -> Dict[str, Any]:
        """Export recipe to target platform format."""
        pass

    @abstractmethod
    def validate(self, recipe: Recipe) -> List[str]:
        """Validate recipe against platform constraints."""
        pass

    def deploy(self, recipe: Recipe) -> bool:
        """Deploy agent to platform."""
        raise NotImplementedError("Deploy not implemented.")
