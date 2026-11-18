"""检查本次研究证据、独立核查并生成正式 HTML。"""

import asyncio
import hashlib
import json
from html import escape

from seek.modules.agents.repositories.research_reports import ResearchReportRepository
from seek.modules.agents.repositories.runs import AgentRunRepository
from seek.modules.agents.repositories.sessions import SessionRepository
from seek.modules.agents.repositories.turn import AgentTurnRepository
from seek.modules.agents.research_reports import ResearchReport, ResearchReview
from seek.modules.agents.tool_results import normalize_tool_result
from seek.modules.workspace.runtime_files import RuntimeFiles
from seek.modules.workspace.runtime_paths import runtime_workdir_path
from seek.shared.datetime import format_utc_datetime
from seek.shared.errors import StateConflictError

REPORT_DIRECTORY = "/outputs/research-reports/"


async def finalize_report(
    *, db, context, tool_call_id: str, report: ResearchReport, research_input_ids: list[str], review_input_id: str
) -> dict:
    """持有当前 Run 执行归属，先检查证据再发布文件。"""
    from seek.modules.agents.services.cooperation import SessionCooperationService

    service = SessionCooperationService(db, run_id=context.run_id, uid=context.uid, worker_id=context.worker_id)
    run, caller = await service.caller()
    if caller.parent_thread_id:
        raise ValueError("正式报告由根协调会话收尾，子会话只交付任务结果")
    research_ids = list(dict.fromkeys(research_input_ids))
    if len(research_ids) < 2 or review_input_id in research_ids:
        raise ValueError("至少需要两个调研任务和独立核查任务")
    repo = ResearchReportRepository(db)
    rows = await repo.load_tasks(caller, run.turn_id, [*research_ids, review_input_id])
    by_input = {row[1].id: row for row in rows}
    if set(by_input) != {*research_ids, review_input_id}:
        raise ValueError("研究任务不存在")
    for member, item, turn, result_run, message in rows:
        if (
            turn is None
            or turn.status != "completed"
            or result_run is None
            or message is None
            or result_run.id != turn.result_run_id
            or result_run.turn_id != turn.id
            or message.run_id != result_run.id
            or message.turn_id != turn.id
            or message.session_record_id != member.id
            or item.turn_id != turn.id
        ):
            raise ValueError("研究任务没有可采用的精确已完成结果")
    research_threads = {by_input[item][0].thread_id for item in research_ids}
    review_member, _, _, _, review_message = by_input[review_input_id]
    if len(research_threads) < 2 or review_member.thread_id in research_threads | {caller.thread_id}:
        raise ValueError("调研与核查必须使用独立会话")
    try:
        review = ResearchReview.model_validate_json(review_message.content)
    except ValueError as exc:
        raise ValueError("核查最终回答必须是 ResearchReview JSON，不能使用代码围栏") from exc
    if set(review.reviewed_input_ids) != set(research_ids):
        raise ValueError("核查结果未覆盖本次采用的全部调研任务")
    turn_inputs = {row[2].id: row[1].id for row in rows}
    evidence = collect_web_evidence(await repo.successful_tool_messages(caller, set(turn_inputs)), turn_inputs)
    if not any(item["input_id"] == review_input_id for item in evidence):
        raise ValueError("核查会话需要实际成功搜索或读取网页")
    sources = validate_report_evidence(report, evidence)
    content = render_report(report, review, sources).encode()
    digest = hashlib.sha256(content).hexdigest()
    call_hash = hashlib.sha256(tool_call_id.encode()).hexdigest()[:16]
    path = f"{runtime_workdir_path(context.workdir_relative_path)}{REPORT_DIRECTORY}{run.turn_id}/{call_hash}.html"

    # 与取消、steer 和终态提交沿用 Thread → Turn → Run 锁序；文件写入前复核 lease。
    await SessionRepository(db).lock_session_by_thread_id(caller.thread_id)
    await AgentTurnRepository(db).get_for_scope(
        turn_id=run.turn_id, thread_id=caller.thread_id, uid=run.uid, app_id=run.app_id, for_update=True
    )
    await AgentRunRepository(db).lock_output_persistence(run.id, worker_id=context.worker_id, thread_id=caller.thread_id)
    await service.caller()
    files = RuntimeFiles(context.uid)
    try:
        await asyncio.to_thread(files.write, path, content, overwrite=False)
    except FileExistsError:
        # 同一工具调用可重放；既有文件必须与重新计算的正文一致。
        existing = await asyncio.to_thread(files.read, path)
        if hashlib.sha256(existing).hexdigest() != digest:
            raise ValueError("正式报告路径已有不同内容，不能覆盖") from None
    return {
        "path": path,
        "sha256": digest,
        "turn_id": run.turn_id,
        "run_id": run.id,
        "research_input_ids": research_ids,
        "review_input_id": review_input_id,
        "sources": sources,
        "check": "source_consistency",
    }


def collect_web_evidence(messages, turn_inputs: dict[str, str]) -> list[dict]:
    """从成功网页审计提取实际内容和系统日期，片段不升级为正文。"""
    sources = []
    for message in messages:
        metadata = message.extra_metadata or {}
        name = metadata.get("tool_name")
        if name not in {"web_search", "web_fetch"} or message.execution_status != "completed":
            continue
        try:
            payload = json.loads(normalize_tool_result(metadata.get("output")).audit_content)
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict) or payload.get("error"):
            continue
        items = payload.get("results", []) if name == "web_search" else [payload]
        for index, item in enumerate(items):
            body = item.get("raw_content") or item.get("content") or ""
            content = body or item.get("relevant_content") or item.get("snippet") or ""
            if not content or not item.get("url"):
                continue
            fetched = payload.get("retrieved_at") or format_utc_datetime(message.finished_at or message.created_at)
            sources.append(
                {
                    "input_id": turn_inputs[message.turn_id],
                    "url": item["url"],
                    "title": item.get("title") or item["url"],
                    "content": content,
                    "content_kind": "body" if body else "snippet",
                    "page_date": item.get("publish_time"),
                    "retrieved_at": fetched,
                    "tool_message_id": message.id,
                    "run_id": message.run_id,
                    "result_index": index,
                    "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                }
            )
    return sources


def validate_report_evidence(report: ResearchReport, evidence: list[dict]) -> list[dict]:
    """引用、直接摘录、阅读范围和事件日期逐项检查。"""
    used = []
    for finding in report.findings:
        matched = []
        for ref in finding.references:
            candidates = [s for s in evidence if s["input_id"] == ref.input_id and s["url"] == ref.url]
            if not candidates:
                raise ValueError("报告引用不是本次任务实际取得的 URL")
            if ref.content_kind == "body":
                candidates = [s for s in candidates if s["content_kind"] == "body"]
                if not candidates:
                    raise ValueError("只有搜索片段，不能声明已读取正文")
            if ref.quote is not None:
                candidates = [s for s in candidates if ref.quote.strip() and ref.quote in s["content"]]
                if not candidates:
                    raise ValueError("报告直接摘录不存在于实际来源")
            source = candidates[0]
            matched.append(source)
            if source not in used:
                used.append(source)
        if finding.event_date is not None:
            if not finding.event_date_quote or not any(finding.event_date_quote in s["content"] for s in matched):
                raise ValueError("已知事件日期需要实际来源中的依据摘录")
            day = finding.event_date
            date_forms = [day.isoformat(), f"{day.year}/{day.month:02}/{day.day:02}", f"{day.year}年{day.month}月{day.day}日"]
            for month_format in ("%B", "%b"):
                month = day.strftime(month_format)
                date_forms.extend((f"{month} {day.day}, {day.year}", f"{day.day} {month} {day.year}"))
            if not any(value.casefold() in finding.event_date_quote.casefold() for value in date_forms):
                raise ValueError("事件日期与依据摘录不一致；无法确认时应标记未知")
            if (report.time_start and finding.event_date < report.time_start) or (report.time_end and finding.event_date > report.time_end):
                raise ValueError("事件日期不在报告声明的研究窗口内")
        elif finding.event_date_quote:
            raise ValueError("未知事件日期不能同时声明日期依据")
    return [{key: value for key, value in source.items() if key != "content"} for source in used]


def render_report(report: ResearchReport, review: ResearchReview, sources: list[dict]) -> str:
    """只渲染经过校验的文本与链接，核查冲突不可被综合正文省略。"""

    def paragraphs(text):
        """正文作为文本处理，不执行模型提交的 HTML。"""
        return "".join(f"<p>{escape(line)}</p>" for line in text.splitlines() if line.strip())

    def items(values):
        """列表显式表示空结果。"""
        return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>" if values else "<p>未报告。</p>"

    parts = [
        f"<h1>{escape(report.title)}</h1>",
        "<h2>摘要</h2>",
        paragraphs(report.summary),
        "<h2>研究范围</h2>",
        paragraphs(report.scope),
        f"<p>事件时间窗口：{report.time_start or '未知'} 至 {report.time_end or '未知'}；"
        "系统获取时间采用 UTC。检查完成时间见会话工具审计。</p>",
        "<h2>发现与关键证据</h2>",
    ]
    for finding in report.findings:
        parts.extend(
            [
                f"<section><h3>{escape(finding.title)}</h3>",
                paragraphs(finding.text),
                f"<p>事件/版本时间：{finding.event_date or '未知（时间窗口未核实）'}</p>",
            ]
        )
        if finding.event_date_quote:
            parts.append(f"<blockquote>日期依据：{escape(finding.event_date_quote)}</blockquote>")
        for ref in finding.references:
            label = "正文" if ref.content_kind == "body" else "搜索片段"
            parts.append(f'<p><a href="{escape(ref.url, quote=True)}" rel="noopener noreferrer">来源（{label}）</a></p>')
            if ref.quote:
                parts.append(f"<blockquote>{escape(ref.quote)}</blockquote>")
        parts.append("</section>")
    if report.comparison:
        parts.extend(["<h2>对比</h2>", paragraphs(report.comparison)])
    parts.extend(
        [
            "<h2>独立核查</h2>",
            paragraphs(review.conclusion),
            "<h3>冲突与存疑</h3>",
            items(review.conflicts),
            "<h3>未知项</h3>",
            items(review.unknowns),
            "<h2>限制</h2>",
            items(report.limitations),
            "<h2>来源列表</h2><ol>",
        ]
    )
    for source in sources:
        parts.append(
            f'<li><a href="{escape(source["url"], quote=True)}">{escape(source["title"])}</a>'
            f"<p>页面发布/更新时间：{escape(source['page_date'] or '未知')}；获取时间：{escape(source['retrieved_at'])}；"
            f"证据类型：{'正文' if source['content_kind'] == 'body' else '搜索片段'}</p></li>"
        )
    parts.append("</ol><footer>来源一致性检查覆盖任务归属、来源与摘录一致性，不证明全部事实正确。检查完成时间见会话工具审计。</footer>")
    return (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        + f"<title>{escape(report.title)}</title>"
        "<style>:root{background:#fff}body{font:16px/1.75 system-ui,sans-serif;max-width:960px;margin:auto;padding:32px;color:#20242a}"
        "h1,h2,h3{line-height:1.3}h2{margin-top:2em}a{color:#2463a6;overflow-wrap:anywhere}"
        "blockquote{border-left:3px solid #bcccdc;margin:1em 0;padding:0 1em;white-space:pre-wrap}"
        "footer{margin-top:3em;border-top:1px solid #ddd;padding-top:1em;font-size:.85em}"
        "p,li{overflow-wrap:anywhere}"
        "@media(prefers-color-scheme:dark){:root{background:#161a20}body{color:#e1e6ec}a{color:#8cbcff}}</style><body>"
        + "".join(parts)
        + "</body></html>"
    )


async def require_report_integrity(
    *,
    db,
    thread_id: str | None,
    uid: str,
    app_id: str | None,
    path: str,
    local_path: str | None = None,
    content: bytes | None = None,
) -> None:
    """正式报告预览、下载和保存只读取通过检查的同一份字节。"""
    if REPORT_DIRECTORY not in path:
        return
    for message in await ResearchReportRepository(db).published_reports(thread_id, uid, app_id):
        output = (message.extra_metadata or {}).get("output") or {}
        artifact = output.get("artifact") or {}
        metadata = artifact.get("research_report")
        if not metadata:
            try:
                metadata = json.loads(normalize_tool_result(output).audit_content)
            except (ValueError, TypeError):
                continue
        if metadata.get("path") != path:
            continue
        if content is not None:
            digest = hashlib.sha256(content).hexdigest()
        else:
            with open(local_path, "rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != metadata.get("sha256"):
            raise StateConflictError("正式报告内容已改变，原来源检查失效", code="research_report_changed")
        return
    raise StateConflictError("正式报告尚无本会话已完成 Turn 的成功检查记录", code="research_report_unpublished")


async def require_workspace_report_integrity(
    *,
    uid: str,
    path: str,
    content: bytes | None = None,
    local_path: str | None = None,
    db=None,
) -> None:
    """Workspace 与 Viewer 读取同一正式路径时也核验原始字节。"""
    if REPORT_DIRECTORY not in path:
        return
    from seek.infrastructure.postgres.manager import pg_manager

    if db is not None:
        await require_report_integrity(db=db, thread_id=None, uid=uid, app_id=None, path=path, content=content, local_path=local_path)
    else:
        async with pg_manager.get_async_session_context() as session:
            await require_report_integrity(
                db=session, thread_id=None, uid=uid, app_id=None, path=path, content=content, local_path=local_path
            )
