"""正式研究报告与独立核查的工具输入契约。"""

from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceReference(BaseModel):
    """引用精确任务实际获得的网页，可声明连续原文。"""

    model_config = ConfigDict(extra="forbid")
    input_id: str
    url: str
    quote: str | None = Field(default=None, max_length=4000)
    content_kind: Literal["snippet", "body"] = "snippet"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """HTML 来源链接只接受实际网页协议。"""
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("来源必须是 HTTP 或 HTTPS 网页 URL")
        return value


class ResearchFinding(BaseModel):
    """结论的日期与引用和正文一起接受校验。"""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=12000)
    event_date: date | None = None
    event_date_quote: str | None = Field(default=None, max_length=4000)
    references: list[EvidenceReference] = Field(min_length=1, max_length=30)


class ResearchReport(BaseModel):
    """HTML 报告的正文；来源元数据不能由模型填写。"""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    scope: str = Field(min_length=1, max_length=4000)
    time_start: date | None = None
    time_end: date | None = None
    summary: str = Field(min_length=1, max_length=12000)
    findings: list[ResearchFinding] = Field(min_length=1, max_length=50)
    comparison: str | None = Field(default=None, max_length=16000)
    limitations: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_window(self):
        """时间窗口按事件时间解释，起止不能倒置。"""
        if self.time_start and self.time_end and self.time_start > self.time_end:
            raise ValueError("研究时间窗口起止颠倒")
        return self


class ResearchReview(BaseModel):
    """独立核查会话最终回答必须使用此 JSON 结构。"""

    model_config = ConfigDict(extra="forbid")
    reviewed_input_ids: list[str] = Field(min_length=2, max_length=100)
    conclusion: str = Field(min_length=1, max_length=12000)
    conflicts: list[str] = Field(max_length=50)
    unknowns: list[str] = Field(max_length=50)


class FinalizeResearchReportInput(BaseModel):
    """模型只能提交内容与任务身份，不能指定用户、Run 或宿主路径。"""

    model_config = ConfigDict(extra="forbid")
    report: ResearchReport
    research_input_ids: list[str] = Field(min_length=2, max_length=100)
    review_input_id: str
