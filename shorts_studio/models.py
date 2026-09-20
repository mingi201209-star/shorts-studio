from __future__ import annotations
from pydantic import BaseModel, Field, model_validator

class Motion(BaseModel):
    type: str = "push_in"

class Scene(BaseModel):
    id: str
    narration: str = Field(min_length=1)
    visual_description: str = Field(min_length=1)
    asset: str | None = None
    attribution: str | None = None
    expected_duration: float | None = Field(default=None, gt=0)
    motion: Motion = Motion()
    transition: str = "cut"
    factual_notes: list[str] = []
    visual_qa_requirements: list[str] = []

class Project(BaseModel):
    title: str
    width: int = 1080
    height: int = 1920
    fps: int = 30
    scenes: list[Scene] = Field(min_length=1)

    @model_validator(mode="after")
    def vertical(self):
        if (self.width,self.height)!=(1080,1920): raise ValueError("V1 output must be 1080x1920")
        if self.fps < 30: raise ValueError("fps must be >=30")
        return self
