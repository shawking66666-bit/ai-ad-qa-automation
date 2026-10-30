import unittest

from video_processor.evaluation import (
    DimensionScore,
    EvaluationRequest,
    EvidenceItem,
    IssueItem,
    SuggestionItem,
    normalize_evaluation,
)
from video_processor.reporting import render_markdown


def make_result(*, human_review: bool = False):
    request = EvaluationRequest(
        asset_type="video",
        profile="ad_video_v1",
        summary="商品出现清晰，但开场卖点不够直接。",
        dimensions=[
            DimensionScore(
                dimension="hook",
                label="开场钩子",
                score=6,
                status="evaluated",
                reason="前三秒未说明核心收益",
            )
        ],
        evidence=[
            EvidenceItem(
                id="evidence-1",
                source_type="video_frame",
                location="00:03",
                dimension="hook",
                finding="画面展示商品，但没有结果型文案",
                confidence=0.9,
            )
        ],
        issues=[
            IssueItem(
                priority="P0",
                dimension="hook",
                problem="核心卖点出现过晚",
                impact="前三秒无法建立观看理由",
                evidence_refs=["evidence-1"],
                suggestion="在00:02前加入核心收益",
            )
        ],
        strengths=["商品主体清晰"],
        suggestions=[
            SuggestionItem(
                priority="P0",
                action="重写开场文案",
                expected_effect="更早建立观看理由",
                evidence_refs=["evidence-1"],
            )
        ],
        missing_information=["conversion_goal"] if human_review else [],
        confidence=0.4 if human_review else 0.9,
        human_review_reason="关键业务目标缺失" if human_review else None,
        technical_details={"state_json": "secret-debug-state"},
    )
    return normalize_evaluation(request)


class MarkdownReportTests(unittest.TestCase):
    def test_render_contains_summary_score_issues_and_evidence(self):
        report = render_markdown(make_result())

        for heading in (
            "总体结论",
            "关键问题",
            "分项评分",
            "内容优势",
            "优化方案",
            "缺失信息与人工复核提示",
        ):
            self.assertIn(heading, report)
        self.assertIn("综合评分：60/100", report)
        self.assertIn("核心卖点出现过晚", report)
        self.assertIn("00:03", report)

    def test_render_shows_missing_information_and_human_review_reason(self):
        report = render_markdown(make_result(human_review=True))

        self.assertIn("需要人工复核", report)
        self.assertIn("关键业务目标缺失", report)
        self.assertIn("conversion_goal", report)

    def test_render_does_not_embed_raw_state_json(self):
        report = render_markdown(make_result())

        self.assertNotIn("state_json", report)
        self.assertNotIn("secret-debug-state", report)
        self.assertNotIn("```json", report)

    def test_render_marks_partial_dimensions_as_unscored(self):
        request = EvaluationRequest(
            asset_type="video", profile="ad_video_v1", summary="已提取画面证据",
            dimensions=[DimensionScore(dimension="hook", label="开场钩子", score=0,
                                       status="partial", reason="尚未生成评分")],
            confidence=0.9, human_review_required=True,
        )
        report = render_markdown(normalize_evaluation(request))
        self.assertIn("综合评分：未评分", report)
        self.assertIn("开场钩子：未评分", report)
        self.assertNotIn("综合评分：0/100", report)


if __name__ == "__main__":
    unittest.main()
