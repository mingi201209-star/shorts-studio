"""Content contracts and render dependency plans for reusable 3D shorts.

Planning alone never starts a renderer, TTS service, publication or paid job.
"""

from .contracts import FactoryManifest, TemplateRegistry
from .planner import create_plan

__all__ = ["FactoryManifest", "TemplateRegistry", "create_plan"]
