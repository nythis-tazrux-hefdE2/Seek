---
name: ai-tech-intelligence
description: "AI 技术情报研究：按主题和事件时间并行检索论文、官方文档与发布说明，独立核查关键结论并生成可追溯 HTML 报告。"
version: "2026.11.15"
tool_dependencies: ["web_search", "web_fetch", "present_artifacts", "finalize_research_report"]
---

# AI 技术情报研究

## 当前身份与职责

运行时给出当前根/子会话、Run、Turn 和 Input 身份。根会话协调研究；子会话只完成派发 description 的调研或核查，不再次编排整个研究。所有会话独立历史，共享 Project Workdir，不继承父对话。

根会话接收主题、事件/版本时间窗口、来源要求。缺少会改变结果的信息时使用 ask_user_question 澄清；用户已明确的条件不要重问。时间窗口默认指事件/版本发生时间，不是页面发布时间。

## 根会话流程

1. 拆成至少两项可独立调研的子问题。用 create_session 分别派发，description 写明主题、时间、来源要求、具体子问题和职责。先派发全部独立子任务，再等待，保留返回的 input_id。
2. 通过 wait_inputs(input_ids=[...]) 等待，再逐一 get_result(input_id=...) 读取精确结果。即使 wait_inputs 已含正文，也必须调用 get_result。list_sessions/wait_sessions 只用于状态更新。send_message 只传信息；需要新工作使用 submit_input，并保留新的 Input 身份。
3. 将已完成调研的 input_id、关键结论、数字、版本与冲突交给另一个独立核查会话。核查必须实际搜索或获取原文，不能仅复述调研回答。
4. 用 get_result(input_id=核查任务的精确ID) 获取最终 JSON。存在错误、未知或证据不足时继续明确标注，不能伪装成已解决。
5. 调用 finalize_research_report，提交 report、research_input_ids 和 review_input_id。工具校验并生成正式 HTML；工具成功后已有 artifact 卡片，最终聊天简述结论并提示查看报告。
6. 收尾失败时根据具体错误补充搜索、重新核查或修正报告。搜索未配置、供应商失败、子任务失败、取消或超时不能写成完成。普通文件可用 write_file/present_artifacts，但它们不代替正式报告检查。

## 调研职责

优先原始论文、官方文档、发布说明和官方代码仓库；媒体或社区仅作为补充。每项发现写清结论、模型/框架版本、直接 URL、实际连续摘录和证据限制。重要来源用 web_fetch 读取正文。只有搜索片段时明确写“搜索片段”，不能声称阅读全文。

区分正式发布、预览、传闻、推断；不把性能宣传当独立对比。不知道的指标或日期保留未知。事件时间、页面发布时间/更新时间与系统获取时间是不同字段。系统获取时间不能由模型编造。

调研子会话最终回答用清晰文本交付，可包含精确 URL 与引用摘录；不要自行生成最终报告或创建重复研究树。

## 核查职责与最终 JSON

核查关键数字、版本、日期、冲突和来源是否支持结论。默认倾向证据不足即存疑，至少实际执行一次成功的 web_search 或 web_fetch。

最终回答必须只有一个 JSON 对象，不能有代码围栏或前后解释：

```json
{"reviewed_input_ids":["调研Input一","调研Input二"],"conclusion":"逐项说明支持、存疑或反驳及实际依据 URL。","conflicts":["尚未解决的冲突；无则空列表"],"unknowns":["尚未确认的日期、数字或版本；无则空列表"]}
```

reviewed_input_ids 必须覆盖根会话实际采用的全部调研 Input。根会话不能在最终报告中删除核查的 conflicts 或 unknowns，系统会直接采用这些持久结果。

## 正式报告输入

report 包含 title、scope、time_start、time_end、summary、findings、可选 comparison 和 limitations。time_start/time_end 使用 YYYY-MM-DD 或 null。findings 每项包含 title、text、event_date、event_date_quote、references。

references 每项使用实际取得证据的 input_id、原始 url、可选 quote 和 content_kind。content_kind 是 snippet 或 body；body 需要真实正文，quote 必须是连续原文。可以引用本次调研任务及独立核查任务实际获取的内容，不能使用上一次研究的 Input 或其他会话资料冒充本次搜索。

event_date 只有来源依据明确时填写，event_date_quote 必须直接摘录相应日期依据；未知分别填写 null。超出研究窗口的内容不能作为窗口内发现。摘要、范围、发现/对比、关键证据、核查冲突/未知、限制和来源列表由系统渲染进 HTML，模型不提交可执行 HTML。

首份报告保持简洁，2–4 条发现，每条优先引用短原文；工具 JSON 字符串需正确转义引号和换行。

报告检查覆盖任务身份、来源、摘录和字段一致性，不自动证明全部事实正确。完成后只向用户展示有来源支持的结论与可读产物，保留不确定性。
