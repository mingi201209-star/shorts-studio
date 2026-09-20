import json
from pathlib import Path
from .models import Project

def load_project(path:str|Path)->Project:
    return Project.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
