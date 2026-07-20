"""Central Tool Registry — plugins register themselves; no hardcoded tool lists in the executor."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Callable, Type

from app.ai.agents.registry.base_tool import BaseTool

logger = logging.getLogger(__name__)

ToolFactory = Callable[[], BaseTool]


class ToolRegistry:
    """
    Plugin registry for agent tools.

    Tools register via ``@register_tool`` or ``registry.register(ToolClass)``.
    ``discover_tools()`` auto-imports ``app.ai.agents.tools`` so new modules
    appear without changing the executor/planner.
    """

    def __init__(self) -> None:
        self._factories: dict[str, ToolFactory] = {}
        self._instances: dict[str, BaseTool] = {}

    def register(self, tool_cls: Type[BaseTool] | ToolFactory) -> Type[BaseTool] | ToolFactory:
        """Register a tool class (or zero-arg factory). Usable as a decorator."""

        def _factory() -> BaseTool:
            if isinstance(tool_cls, type) and issubclass(tool_cls, BaseTool):
                return tool_cls()
            return tool_cls()  # type: ignore[operator]

        if isinstance(tool_cls, type) and issubclass(tool_cls, BaseTool):
            name = getattr(tool_cls, "name", None) or tool_cls.__name__
        else:
            name = _factory().name

        if name in self._factories:
            logger.debug("Replacing tool registration: %s", name)
        self._factories[name] = _factory
        self._instances.pop(name, None)
        logger.info("Registered agent tool: %s", name)
        return tool_cls

    def get(self, name: str) -> BaseTool:
        if name not in self._factories:
            raise KeyError(f"Tool not registered: {name}")
        if name not in self._instances:
            self._instances[name] = self._factories[name]()
        return self._instances[name]

    def has(self, name: str) -> bool:
        return name in self._factories

    def list_names(self) -> list[str]:
        return sorted(self._factories.keys())

    def list_tools(self, *, agent_type: str | None = None) -> list[BaseTool]:
        tools = [self.get(n) for n in self.list_names()]
        if agent_type:
            tools = [t for t in tools if t.matches_agent(agent_type)]
        return tools

    def schemas(self, *, agent_type: str | None = None) -> list[dict]:
        return [t.schema_dict() for t in self.list_tools(agent_type=agent_type)]

    def clear(self) -> None:
        self._factories.clear()
        self._instances.clear()


tool_registry = ToolRegistry()


def register_tool(cls: Type[BaseTool]) -> Type[BaseTool]:
    """Decorator: ``@register_tool class MyTool(BaseTool): ...``"""
    tool_registry.register(cls)
    return cls


def discover_tools(package_name: str = "app.ai.agents.tools") -> list[str]:
    """Import (or reload) all modules under the tools package so @register_tool runs."""
    import sys

    try:
        package = importlib.import_module(package_name)
    except ModuleNotFoundError:
        logger.warning("Tools package not found: %s", package_name)
        return []

    imported: list[str] = []
    if not hasattr(package, "__path__"):
        return imported

    for mod in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        try:
            if mod.name in sys.modules:
                importlib.reload(sys.modules[mod.name])
            else:
                importlib.import_module(mod.name)
            imported.append(mod.name)
        except Exception:
            logger.exception("Failed to import tool module %s", mod.name)
    return imported


def ensure_tools_loaded(*, force: bool = False) -> ToolRegistry:
    """Idempotent bootstrap used by services/API."""
    if force or not tool_registry.list_names():
        discover_tools()
    return tool_registry
