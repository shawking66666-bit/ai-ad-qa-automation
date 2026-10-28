from __future__ import annotations

from .evaluation import EvaluationResult


def _review_label(result: EvaluationResult) -> str:
    return "需要人工复核" if result.human_review_required else "无需强制人工复核"


def render_markdown(result: EvaluationResult) -> str:
    evidence_by_id = {item.id: item for item in result.evidence}
    lines = [
        "# AIGC 内容质量评估报告",
        "",
        "## 总体结论",
        "",
        f"- 内容类型：{result.asset_type}",
        f"- 评估模板：{result.profile}",
        f"- 综合评分：{result.overall_score}/100",
        f"- 运行状态：{result.status}",
        f"- 人工复核：{_review_label(result)}",
        f"- 结论：{result.summary}",
        "",
        "## 关键问题",
        "",
    ]

    if result.issues:
        for issue in result.issues:
            lines.extend(
                [
                    f"### {issue.priority}｜{issue.problem}",
                    "",
                    f"- 评估维度：{issue.dimension}",
                    f"- 影响：{issue.impact}",
                    f"- 修改建议：{issue.suggestion}",
                ]
            )
            for reference in issue.evidence_refs:
                evidence = evidence_by_id[reference]
                lines.append(f"- 证据（{evidence.location}）：{evidence.finding}")
            lines.append("")
    else:
        lines.extend(["- 未发现需要优先处理的问题。", ""])

    lines.extend(["## 分项评分", ""])
    for dimension in result.dimensions:
        if dimension.status == "not_applicable":
            lines.append(f"- {dimension.label}：不适用（{dimension.reason}）")
        else:
            lines.append(
                f"- {dimension.label}：{dimension.score:g}/{dimension.max_score:g}"
                f"（{dimension.status}，{dimension.reason}）"
            )
    if not result.dimensions:
        lines.append("- 没有可用的分项评分。")

    lines.extend(["", "## 内容优势", ""])
    lines.extend(f"- {item}" for item in result.strengths)
    if not result.strengths:
        lines.append("- 暂无已确认优势。")

    lines.extend(["", "## 优化方案", ""])
    for item in result.suggestions:
        lines.append(
            f"- {item.priority}｜{item.action}；预期作用：{item.expected_effect}"
        )
    if not result.suggestions:
        lines.append("- 暂无独立优化动作。")

    lines.extend(["", "## 缺失信息与人工复核提示", ""])
    lines.extend(f"- 缺失信息：{item}" for item in result.missing_information)
    if result.human_review_reason:
        lines.append(f"- 人工复核原因：{result.human_review_reason}")
    if not result.missing_information and not result.human_review_reason:
        lines.append("- 当前没有额外缺失信息或强制人工复核要求。")

    return "\n".join(lines).strip() + "\n"
