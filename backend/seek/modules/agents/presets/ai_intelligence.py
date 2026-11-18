"""固定 AI 技术情报研究配置。"""

from seek.modules.agents.presets import AgentPreset

PRESET = AgentPreset(
    slug="ai-intelligence",
    name="AI 技术情报研究",
    description="并行调研 AI 论文、模型和框架，独立核查后交付带来源与日期的 HTML 报告。",
    context={
        "system_prompt": (
            "你是 Seek AI 技术情报研究助手。严格遵循预加载的 ai-tech-intelligence Skill。"
            "根会话负责协调，子会话只完成 description 指定的调研或核查任务；"
            "不要把继承配置理解为需要重新编排整个研究。"
        ),
        "skills": ["ai-tech-intelligence"],
        "preload_skills": ["ai-tech-intelligence"],
        "tools": ["web_search", "web_fetch", "present_artifacts", "finalize_research_report"],
    },
)
