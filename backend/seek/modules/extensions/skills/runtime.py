"""Skill 运行时解析。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from seek.infrastructure.filesystem import open_regular_file_fd
from seek.infrastructure.observability.logging import logger
from seek.modules.extensions.skills.access import lock_accessible_shared_skills_for_runtime, resolved_shared_skill
from seek.modules.extensions.skills.package import normalize_string_list
from seek.modules.extensions.skills.projection import refresh_user_skill_projection_async
from seek.modules.extensions.skills.resolved import RuntimeSkill, SkillRuntimeSnapshot
from seek.modules.identity.models import User
from seek.modules.workspace.runtime_paths import PERSONAL_SKILLS_PATH, SHARED_SKILLS_PATH


async def sync_agent_context_skills(context) -> None:
    """构图前校验运行身份，并刷新用户获授权的共享 Skill 投影。"""
    thread_id = context.get("thread_id") if isinstance(context, dict) else getattr(context, "thread_id", None)
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("thread_id is required in runtime context")
    uid = context.get("uid") if isinstance(context, dict) else getattr(context, "uid", None)
    if not isinstance(uid, str) or not uid.strip():
        raise ValueError("uid is required in runtime context")
    await refresh_user_skill_projection_async(uid.strip())


async def resolve_runtime_skills_for_context(
    context,
    *,
    db: AsyncSession,
    user: User,
    agent=None,
) -> SkillRuntimeSnapshot:
    """解析固定内置 Skill，派生运行范围和预加载快照。"""
    selected = normalize_string_list(getattr(context, "skills", None))
    shared_rows = await lock_accessible_shared_skills_for_runtime(
        db,
        user,
        selected,
    )
    skill_items_by_slug = {item.slug: resolved_shared_skill(item) for item in shared_rows if item.slug}
    runtime_skills = build_runtime_skills(list(skill_items_by_slug.values()))
    selected_skills = [slug for slug in selected if slug in skill_items_by_slug]
    context_skills = selected_skills
    effective_skills = expand_skill_closure(context_skills, runtime_skills)
    limited = any(dependency not in runtime_skills for slug in effective_skills for dependency in runtime_skills[slug]["skills"])
    configured_preloads = normalize_string_list(getattr(context, "preload_skills", None))
    context_preload_skills = [slug for slug in configured_preloads if slug in selected_skills]
    preloaded_skills = expand_skill_closure(context_preload_skills, runtime_skills)
    preloaded_contents = (
        await asyncio.to_thread(_read_preloaded_skill_contents, preloaded_skills, skill_items_by_slug) if preloaded_skills else {}
    )
    return {
        "capability_limited": limited,
        "context_skills": context_skills,
        "context_preload_skills": context_preload_skills,
        "effective_skills": effective_skills,
        "runtime_skills": runtime_skills,
        "skill_metadata": {
            slug: {
                "source_scope": skill_items_by_slug[slug].source_scope,
                "version": skill_items_by_slug[slug].version,
                "content_hash": skill_items_by_slug[slug].content_hash,
            }
            for slug in effective_skills
        },
        "preloaded_skills": preloaded_skills,
        "preloaded_skill_contents": preloaded_contents,
    }


def build_runtime_skills(skills: list) -> dict[str, RuntimeSkill]:
    """从已授权 Skill 构建运行时信息。"""
    result: dict[str, RuntimeSkill] = {}
    for item in skills:
        if not item.slug:
            continue
        root = PERSONAL_SKILLS_PATH if getattr(item, "source_scope", None) == "personal" else SHARED_SKILLS_PATH
        result[item.slug] = {
            "name": item.name,
            "description": item.description,
            "path": f"{root}/{item.slug}/SKILL.md",
            "tools": normalize_string_list(item.tool_dependencies or []),
            "skills": normalize_string_list(item.skill_dependencies or []),
        }
    return result


def expand_skill_closure(
    slugs: list[str] | None,
    runtime_skills: dict[str, RuntimeSkill],
) -> list[str]:
    """展开 Skill 依赖闭包并保持根与依赖的声明顺序。"""
    ordered_roots = normalize_string_list(slugs)
    if not ordered_roots:
        return []

    result: list[str] = []
    seen: set[str] = set()

    def dfs(slug: str, stack: set[str]) -> None:
        if slug in stack:
            logger.warning(f"Cycle detected in skill dependencies, skip: {' -> '.join([*stack, slug])}")
            return
        if slug in seen:
            return

        node = runtime_skills.get(slug)
        if not node:
            logger.warning(f"Skill dependency target not found in DB, skip: {slug}")
            return

        seen.add(slug)
        result.append(slug)
        next_stack = set(stack)
        next_stack.add(slug)
        for dep in node.get("skills", []):
            dfs(dep, next_stack)

    for root in ordered_roots:
        dfs(root, set())
    return result


def _read_preloaded_skill_contents(slugs: list[str], skill_items: dict[str, Any]) -> dict[str, str]:
    """从授权解析得到的真实来源读取根级 SKILL.md。"""

    contents: dict[str, str] = {}
    for slug in slugs:
        try:
            source_dir = Path(skill_items[slug].source_dir)
            if not source_dir.is_absolute() or ".." in source_dir.parts:
                raise OSError("Skill 来源目录必须是规范化绝对路径")
            with open_regular_file_fd(
                Path(source_dir.anchor),
                (*source_dir.parts[1:], "SKILL.md"),
            ) as (file_fd, _file_stat):
                with os.fdopen(os.dup(file_fd), encoding="utf-8") as skill_file:
                    contents[slug] = skill_file.read()
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"预加载 Skill '{slug}' 失败：根级 SKILL.md 不可读") from exc
    return contents
