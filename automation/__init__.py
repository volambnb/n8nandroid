"""Automation package for no-code app execution on IXBrowser profiles."""

from automation.models import (
    AppGraph,
    AppInput,
    CreateAppRequest,
    CreateSavedTaskRequest,
    CreateScheduleRequest,
    Edge,
    Node,
    RunRequest,
    UpdateAppRequest,
    UpdateSavedTaskRequest,
    UpdateScheduleRequest,
)
from automation.catalog import node_catalog
from automation.service import AutomationService

__all__ = [
    "AppGraph",
    "AppInput",
    "CreateAppRequest",
    "CreateSavedTaskRequest",
    "CreateScheduleRequest",
    "Edge",
    "Node",
    "RunRequest",
    "UpdateAppRequest",
    "UpdateSavedTaskRequest",
    "UpdateScheduleRequest",
    "node_catalog",
    "AutomationService",
]
