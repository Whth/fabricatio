from typing import Dict, List, Optional, Any
from pathlib import Path

class TemplateManager:
    def __init__(self, template_dirs: List[Path]) -> None: ...
    def discover_templates(self) -> None: ...
    def get_template_path(self, name: str) -> Optional[Path]: ...
    def render_template(self, name: str, data: Dict[str, Any]) -> str: ...