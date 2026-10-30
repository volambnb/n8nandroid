from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AppInput(BaseModel):
    name: str
    type: str = "string"
    required: bool = False
    default: Any = None
    secret: bool = False

    @model_validator(mode="after")
    def _discard_secret_default(self) -> "AppInput":
        # Sensitive values must be supplied for each run, never persisted as an
        # app input default (including when an app bundle is imported).
        if self.secret:
            self.default = None
        return self


class Node(BaseModel):
    id: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    x: float = 0
    y: float = 0


class Edge(BaseModel):
    from_node: str = Field(..., alias="from")
    to: str
    label: str = "next"

    model_config = {"populate_by_name": True}


class AppGraph(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    inputs: list[AppInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_node_ids(self) -> "AppGraph":
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Node ids must be unique")
        return self


class CreateAppRequest(BaseModel):
    name: str
    description: str = ""
    graph: AppGraph


class UpdateAppRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: AppGraph | None = None


class ProfileSelector(BaseModel):
    tag_id: int = 0
    group_id: int = 0
    profile_ids: list[str] | None = None


class RunRequest(BaseModel):
    app_id: str | None = None
    task_id: str | None = None
    graph: AppGraph | None = None
    start_node_id: str | None = None
    single_node_only: bool = False
    inputs: dict[str, Any] = Field(default_factory=dict)
    profile_selector: ProfileSelector = Field(default_factory=ProfileSelector)
    concurrency: int = Field(default=3, ge=1, le=50)
    retry: int = Field(default=1, ge=0, le=10)
    timeout: float = Field(default=300.0, ge=1, le=3600)
    stop_on_error: bool = False
    close_profile_on_finish: bool = False

    @model_validator(mode="after")
    def _ensure_source(self) -> "RunRequest":
        if bool(self.app_id) == bool(self.task_id):
            raise ValueError("Provide exactly one of app_id or task_id")
        return self


class CreateSavedTaskRequest(BaseModel):
    name: str
    app_id: str
    default_inputs: dict[str, Any] = Field(default_factory=dict)
    profile_selector: ProfileSelector = Field(default_factory=ProfileSelector)
    concurrency: int = Field(default=3, ge=1, le=50)
    retry: int = Field(default=1, ge=0, le=10)
    timeout: float = Field(default=300.0, ge=1, le=3600)
    stop_on_error: bool = False
    close_profile_on_finish: bool = False


class UpdateSavedTaskRequest(BaseModel):
    name: str | None = None
    default_inputs: dict[str, Any] | None = None
    profile_selector: ProfileSelector | None = None
    concurrency: int | None = Field(default=None, ge=1, le=50)
    retry: int | None = Field(default=None, ge=0, le=10)
    timeout: float | None = Field(default=None, ge=1, le=3600)
    stop_on_error: bool | None = None
    close_profile_on_finish: bool | None = None


class CreateScheduleRequest(BaseModel):
    name: str
    task_id: str
    interval_seconds: int | None = Field(default=None, ge=10)
    cron_expr: str | None = None
    enabled: bool = True
    input_overrides: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ensure_timing(self) -> "CreateScheduleRequest":
        if not self.interval_seconds and not self.cron_expr:
            raise ValueError("Either interval_seconds or cron_expr is required")
        return self


class UpdateScheduleRequest(BaseModel):
    name: str | None = None
    interval_seconds: int | None = Field(default=None, ge=10)
    cron_expr: str | None = None
    enabled: bool | None = None
    input_overrides: dict[str, Any] | None = None


RunStatus = Literal["queued", "running", "done", "failed", "cancelled"]
