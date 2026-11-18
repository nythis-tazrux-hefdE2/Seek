"""Skills 中间件 - 处理 skills 提示词注入、依赖展开、动态激活"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Annotated, Any, NotRequired

from deepagents.middleware._utils import append_to_system_message
from deepagents.middleware.skills import SKILLS_SYSTEM_PROMPT
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.agents.middleware.types import ToolCallRequest
from langgraph.types import Command

from seek.infrastructure.observability.logging import logger
from seek.modules.extensions.skills.package import is_valid_skill_slug, normalize_string_list
from seek.modules.extensions.skills.resolved import RuntimeSkill
from seek.modules.workspace.runtime_paths import PERSONAL_SKILLS_PATH, SHARED_SKILLS_PATH


def _activated_skills_reducer(left: list[str] | None, right: list[str] | None) -> list[str]:
    """合并 activated_skills 列表"""
    return normalize_string_list([*(left or []), *(right or [])])


class SkillsState(AgentState):
    """Skills 状态定义"""

    activated_skills: NotRequired[Annotated[list[str], _activated_skills_reducer]]


class SkillsMiddleware(AgentMiddleware):
    """Skills 中间件 - 处理提示词注入、预加载、依赖展开和动态激活

    职责：
    - Skills 摘要提示与预加载完整说明注入
    - 依赖展开（预加载配置 + 动态激活）
    - 为已激活 Skill 装配动态 MCP 工具
    """

    state_schema = SkillsState

    def __init__(
        self,
        *,
        enable_skills_prompt: bool = True,
        skills_sources_for_prompt: list[str] | None = None,
    ):
        """初始化中间件

        Args:
            enable_skills_prompt: 是否启用 skills 提示段注入（默认 True）
            skills_sources_for_prompt: skills 来源路径（默认展示共享投影与个人 Workspace）
        """
        super().__init__()
        self.enable_skills_prompt = enable_skills_prompt
        self.skills_sources_for_prompt = skills_sources_for_prompt or [
            f"{SHARED_SKILLS_PATH}/",
            f"{PERSONAL_SKILLS_PATH}/",
        ]

    async def awrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
        """包装模型调用，处理 skills 提示词注入、动态激活和依赖展开"""
        runtime_context = request.runtime.context

        snapshot = runtime_context.skill_runtime_snapshot
        if self.enable_skills_prompt:
            if snapshot is not None:
                effective_skills = snapshot["effective_skills"]
                preloaded_skills = self._get_preloaded_skills(runtime_context)
                preloaded_set = set(preloaded_skills)
                prompt_sections: list[str] = []
                lazy_skills = [slug for slug in effective_skills if slug not in preloaded_set]
                if lazy_skills:
                    skills_meta = self._collect_prompt_metadata(lazy_skills, runtime_context)
                    if skills_meta:
                        prompt_sections.append(self._build_skills_section(skills_meta))
                if preloaded_skills:
                    prompt_sections.append(self._build_preloaded_skills_section(preloaded_skills, runtime_context))
                if prompt_sections:
                    system_message = append_to_system_message(getattr(request, "system_message", None), "\n\n".join(prompt_sections))
                    request = request.override(system_message=system_message)

        return await handler(request)

    def _collect_prompt_metadata(self, slugs: list[str], runtime_context) -> list[RuntimeSkill]:
        """收集指定 slugs 的提示词元数据"""
        runtime_skills = self._get_runtime_skills(runtime_context)
        return [runtime_skills[slug] for slug in slugs]

    def _process_tool_call_result(self, result: Any, request: ToolCallRequest) -> Any:
        """处理工具调用结果，检查并处理 skill 动态激活"""
        if request.tool_call.get("name") != "read_file":
            return result

        from langchain_core.messages import ToolMessage

        messages = (result.update or {}).get("messages", []) if isinstance(result, Command) else [result]
        if any(isinstance(message, ToolMessage) and message.status == "error" for message in messages):
            return result

        args = request.tool_call.get("args") or {}
        if isinstance(args, dict) and isinstance(args.get("limit"), int) and args["limit"] <= 0:
            return result
        file_path = args.get("file_path") if isinstance(args, dict) else None
        slug = self._extract_skill_slug_from_skill_md_path(file_path)

        if not slug:
            return result

        if slug not in self._get_effective_skills(request.runtime.context):
            logger.warning(f"SkillsMiddleware: deny skill activation for invisible slug: {slug}")
            return result

        logger.debug(f"SkillsMiddleware: activated skill by read_file: {slug}")
        return self._merge_activated_skill_update(result, slug)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ):
        """包装工具调用，处理 skill 动态激活"""
        result = await handler(request)
        return self._process_tool_call_result(result, request)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ):
        """同步版本的工具调用包装"""
        result = handler(request)
        return self._process_tool_call_result(result, request)

    def _extract_skill_slug_from_skill_md_path(self, file_path: Any) -> str | None:
        """从共享投影或个人 UserWorkspace 的 SKILL.md 路径中提取 slug。"""
        if not isinstance(file_path, str):
            return None
        raw = file_path.strip()
        if not raw:
            return None
        pure = PurePosixPath(raw if raw.startswith("/") else f"/{raw}")
        for root in (SHARED_SKILLS_PATH, PERSONAL_SKILLS_PATH):
            try:
                relative = pure.relative_to(PurePosixPath(root))
            except ValueError:
                continue
            if len(relative.parts) == 2 and relative.name == "SKILL.md" and is_valid_skill_slug(relative.parts[0]):
                return relative.parts[0]
        return None

    def _get_effective_skills(self, runtime_context) -> set[str]:
        """读取完整快照的有效 Skill，未准备阶段返回空集合。"""
        snapshot = runtime_context.skill_runtime_snapshot
        return set(snapshot["effective_skills"]) if snapshot is not None else set()

    def _get_runtime_skills(self, runtime_context) -> dict[str, RuntimeSkill]:
        """读取准备阶段构造的运行信息。"""
        snapshot = runtime_context.skill_runtime_snapshot
        return snapshot["runtime_skills"] if snapshot is not None else {}

    def _get_preloaded_skills(self, runtime_context) -> list[str]:
        """仅保留完整快照内仍有效的预加载 Skill。"""
        snapshot = runtime_context.skill_runtime_snapshot
        if snapshot is None:
            return []
        effective = set(snapshot["effective_skills"])
        return [slug for slug in snapshot["preloaded_skills"] if slug in effective]

    def _build_preloaded_skills_section(self, slugs: list[str], runtime_context) -> str:
        """从完整快照构建预加载提示；未准备阶段没有正文。"""
        snapshot = runtime_context.skill_runtime_snapshot
        contents = snapshot["preloaded_skill_contents"] if snapshot is not None else {}
        sections = ["# Preloaded Skills", "The following Skill instructions are already loaded and active."]
        for slug in slugs:
            content = contents[slug]
            sections.append(f'<preloaded_skill slug="{slug}">\n{content}\n</preloaded_skill>')
        return "\n\n".join(sections)

    def _merge_activated_skill_update(self, result: Any, slug: str):
        """合并动态激活的 skill 更新"""
        from langchain_core.messages import ToolMessage

        if isinstance(result, Command):
            update = dict(result.update or {})
            current = update.get("activated_skills") or []
            update["activated_skills"] = _activated_skills_reducer(current, [slug])
            return Command(graph=result.graph, update=update, resume=result.resume, goto=result.goto)

        if isinstance(result, ToolMessage):
            return Command(update={"messages": [result], "activated_skills": [slug]})

        return result

    def _format_skills_locations(self, sources: list[str]) -> str:
        """格式化 skills 位置信息"""
        locations = []
        for i, source_path in enumerate(sources):
            name = PurePosixPath(source_path.rstrip("/")).name.capitalize()
            suffix = " (higher priority)" if i == len(sources) - 1 else ""
            locations.append(f"**{name} Skills**: `{source_path}`{suffix}")
        return "\n".join(locations)

    def _format_skills_list(self, skills_meta: list[RuntimeSkill]) -> str:
        """格式化 skills 列表"""
        if not skills_meta:
            return f"(No skills available yet. You can create skills in {' or '.join(self.skills_sources_for_prompt)})"

        lines = []
        for skill in skills_meta:
            lines.append(f"- **{skill['name']}**: {skill['description']}")
            lines.append(f"  -> Read `{skill['path']}` for full instructions")
        return "\n".join(lines)

    def _build_skills_section(self, skills_meta: list[RuntimeSkill]) -> str:
        """构建 skills 提示段"""
        skills_locations = self._format_skills_locations(self.skills_sources_for_prompt)
        skills_list = self._format_skills_list(skills_meta)
        return SKILLS_SYSTEM_PROMPT.format(
            skills_locations=skills_locations,
            skills_load_warnings="",
            skills_list=skills_list,
        )
