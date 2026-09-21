"""AegisCode 工作区请求/响应模型。"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    storage_type: str = Field(default="cloud", pattern="^(cloud|local)$")
    # root_path 仅 local 模式由桌面端传入展示名, cloud 模式后端自动生成
    root_hint: str | None = None
    git_enabled: bool = True
    sandbox_enabled: bool = True
    allowed_paths: list[str] | None = None
    blocked_commands: list[str] | None = None
    # 本地模式设备信息(桌面端)
    device_id: str | None = None
    device_name: str | None = None
    device_platform: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    git_enabled: bool | None = None
    sandbox_enabled: bool | None = None
    allowed_paths: list[str] | None = None
    blocked_commands: list[str] | None = None
    status: str | None = Field(default=None, pattern="^(active|archived|deleted)$")


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    description: str | None = None
    storage_type: str = "cloud"
    root_path: str = ""
    root_hint: str | None = None
    git_enabled: bool
    git_branch: str
    sandbox_enabled: bool
    status: str
    created_at: datetime
    updated_at: datetime


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    path: str
    is_directory: bool
    size: int = 0
    content_hash: str | None = None
    language: str | None = None
    status: str = "normal"
    created_at: datetime
    updated_at: datetime


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    run_id: int | None = None
    step_index: int | None = None
    commit_hash: str | None = None
    commit_message: str
    files_changed: str | None = None
    reviewed: bool = False
    review_status: str | None = None
    created_at: datetime


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    run_id: int | None = None
    command: str
    cwd: str | None = None
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    duration_ms: int | None = None
    blocked: bool = False
    block_reason: str | None = None
    created_at: datetime
