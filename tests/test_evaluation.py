import unittest

from pydantic import ValidationError

from video_processor.evaluation import (
    DimensionScore,
    EvaluationRequest,
    EvidenceItem,
    IssueItem,
    calculate_overall_score,
    normalize_evaluation,
)


class EvaluationContractTests(unittest.TestCase):
    def test_calculate_overall_score_uses_equal_weight_for_evaluated_dimensions(self):
        dimensions = [
            DimensionScore(
                dimension="hook",
                label="开场钩子",
                score=6,
                status="evaluated",
                reason="钩子存在但吸引力一般",
            ),
            DimensionScore(
                dimension="cta",
                label="行动引导",
                score=8,
                status="evaluated",
                reason="行动指令明确",
            ),
        ]

        self.assertEqual(calculate_overall_score(dimensions), 70)

    def test_calculate_overall_score_excludes_not_applicable_dimensions(self):
        dimensions = [
            DimensionScore(
                dimension="hook",
                label="开场钩子",
                score=8,
                status="evaluated",
                reason="开场目标明确",
            ),
            DimensionScore(
                dimension="cta",
                label="行动引导",
                score=0,
                status="not_applicable",
                reason="当前素材不包含结尾",
            ),
        ]

        self.assertEqual(calculate_overall_score(dimensions), 80)

    def test_missing_optional_context_marks_partial_without_inventing_facts(self):
        request = EvaluationRequest(
            asset_type="script",
            profile="ad_script_v1",
            summary="脚本结构可以评价，但受众与转化目标缺失。",
            dimensions=[
                DimensionScore(
                    dimension="structure",
                    label="信息结构",
                    score=7,
                    status="partial",
                    reason="缺少目标受众，无法完整判断表达顺序",
                )
            ],
            missing_information=["target_audience", "conversion_goal"],
            confidence=0.75,
        )

        result = normalize_evaluation(request)

        self.assertEqual(result.status, "partial")
        self.assertEqual(
            result.missing_information,
            ["target_audience", "conversion_goal"],
        )
        self.assertEqual(result.summary, request.summary)
        self.assertNotIn("价格", result.summary)
        self.assertNotIn("认证", result.summary)

    def test_evidence_refs_must_resolve_to_known_evidence(self):
        with self.assertRaises(ValidationError):
            EvaluationRequest(
                asset_type="image",
                profile="ad_image_v1",
                summary="图片主体不突出。",
                dimensions=[],
                evidence=[
                    EvidenceItem(
                        id="evidence-1",
                        source_type="image",
                        location="image:1",
                        dimension="subject",
                        finding="商品主体面积较小",
                        confidence=0.8,
                    )
                ],
                issues=[
                    IssueItem(
                        priority="P1",
                        dimension="subject",
                        problem="主体不突出",
                        impact="用户难以快速识别商品",
                        evidence_refs=["evidence-missing"],
                        suggestion="放大商品主体",
                    )
                ],
                confidence=0.8,
            )

    def test_low_confidence_or_conflicting_evidence_requires_human_review(self):
        low_confidence = normalize_evaluation(
            EvaluationRequest(
                asset_type="video",
                profile="ad_video_v1",
                summary="关键帧不足。",
                dimensions=[],
                confidence=0.3,
            )
        )
        conflicting = normalize_evaluation(
            EvaluationRequest(
                asset_type="video",
                profile="ad_video_v1",
                summary="画面与脚本证据冲突。",
                dimensions=[],
                confidence=0.8,
                conflicting_core_evidence=True,
            )
        )

        self.assertEqual(low_confidence.status, "human_review_required")
        self.assertTrue(low_confidence.human_review_required)
        self.assertEqual(conflicting.status, "human_review_required")
        self.assertTrue(conflicting.human_review_required)


if __name__ == "__main__":
    unittest.main()
