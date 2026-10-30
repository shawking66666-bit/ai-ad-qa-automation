import hashlib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workflow" / "tools"))
import build_multimodal_v1
from video_processor.evaluation import EvaluationRequest, EvaluationResult
CANDIDATE = ROOT / "workflow" / "candidate" / "AIGC-Multimodal-QA-v1.yml"
PROTECTED_HASHES = {
    ROOT / "workflow" / "current" / "AI-Ad-QA-current.yml": (
        "9018d8353db8d9b0be08754bb5cec14f1b67614488401b93f4ab56fd64b9f162"
    ),
    ROOT / "workflow" / "candidate" / "AI-Ad-QA-agent-v1.yml": (
        "f4ea7c6216996c8e8c70ac32a0a71ee98b3299b0309e8e66fa1de70042e9a1e1"
    ),
}


class MultimodalV1DslTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CANDIDATE.is_file(), f"candidate DSL missing: {CANDIDATE}")
        self.text = CANDIDATE.read_text(encoding="utf-8")
        self.dsl = json.loads(self.text)
        self.graph = self.dsl["workflow"]["graph"]
        self.nodes = self.graph["nodes"]

    def node_data(self, node_type):
        return [node["data"] for node in self.nodes if node["data"].get("type") == node_type]

    def run_code_node(self, title, **kwargs):
        code = next(node["code"] for node in self.node_data("code") if node["title"] == title)
        namespace = {}
        exec(code, namespace)
        return namespace["main"](**kwargs)

    def test_has_one_asset_type_entry_and_three_branches(self):
        starts = self.node_data("start")
        self.assertEqual(len(starts), 1)
        variables = {item["variable"]: item for item in starts[0]["variables"]}
        self.assertEqual(
            set(variables),
            {
                "asset_type",
                "video",
                "image",
                "script",
                "product_context",
                "target_audience",
                "conversion_goal",
                "additional_requirements",
            },
        )
        self.assertEqual(variables["asset_type"]["options"], ["video", "image", "script"])

        route_text = json.dumps(self.node_data("if-else"), ensure_ascii=False)
        for asset_type in ("video", "image", "script"):
            self.assertIn(asset_type, route_text)

    def test_video_retains_bounded_agent_and_video_lifecycle(self):
        loops = self.node_data("loop")
        self.assertEqual(len(loops), 1)
        self.assertEqual(loops[0]["loop_count"], 5)
        urls = [node["url"] for node in self.node_data("http-request")]
        self.assertIn("http://host.docker.internal:8000/api/v1/agent-videos", urls)
        self.assertTrue(any(url.endswith("/frames") for url in urls))
        cleanup = [
            node
            for node in self.node_data("http-request")
            if node["title"] == "清理 Agent 视频任务"
        ]
        self.assertEqual(len(cleanup), 1)
        self.assertEqual(cleanup[0]["method"], "delete")

    def test_video_guard_reads_decision_text_when_provider_returns_schema_hint(self):
        guard = next(node for node in self.node_data("code") if node["title"] == "校验决策与守卫")
        namespace = {}
        exec(guard["code"], namespace)
        state = {"final_status": "running", "completed_actions": [], "current_step": 0,
                 "retry_count": 0, "supplementary_rounds": 0, "needs_human_review": False, "errors": []}
        result = namespace["main"](
            state_json=json.dumps(state), decision={"type": "json_object"},
            decision_text='<think>reasoning</think>{"action":"analyze_frames","arguments":{"timestamps":[0.0,3.0]},"should_stop":"false"}',
        )
        self.assertEqual(result["action"], "analyze_frames")
        self.assertEqual(json.loads(result["timestamps_json"]), [0.0, 3.0])

    def test_video_guard_safely_stops_on_unparseable_decision(self):
        guard = next(node for node in self.node_data("code") if node["title"] == "校验决策与守卫")
        namespace = {}
        exec(guard["code"], namespace)
        state = {"final_status": "running", "completed_actions": [], "current_step": 0,
                 "retry_count": 0, "supplementary_rounds": 0, "needs_human_review": False, "errors": []}
        result = namespace["main"](state_json=json.dumps(state), decision={"type": "json_object"},
                                   decision_text="<think>reasoning</think>not valid json")
        self.assertEqual(result["action"], "stop")
        self.assertTrue(json.loads(result["state_json"])["needs_human_review"])

    def test_outputs_separate_report_and_technical_details(self):
        ends = [node for node in self.node_data("end") if node["title"] == "输出多模态报告"]
        self.assertEqual(len(ends), 1)
        output_names = {item["variable"] for item in ends[0]["outputs"]}
        self.assertEqual(
            output_names,
            {"report_markdown", "evaluation_result", "final_status", "technical_details"},
        )
        self.assertIn("/api/v1/evaluations/render", self.text)

    def test_report_branches_converge_before_one_end(self):
        ends = self.node_data("end")
        all_names = [output["variable"] for node in ends for output in node["outputs"]]
        self.assertEqual(len(all_names), len(set(all_names)), "Dify rejects duplicate End outputs")
        report_ends = [node for node in ends if "report_markdown" in {item["variable"] for item in node["outputs"]}]
        self.assertEqual(len(report_ends), 1)
        aggregators = self.node_data("variable-aggregator")
        self.assertEqual(len(aggregators), 1)
        self.assertEqual(aggregators[0]["output_type"], "object")
        self.assertEqual(len(aggregators[0]["variables"]), 5)
        aggregator = next(node for node in self.nodes if node["data"]["type"] == "variable-aggregator")
        packer_ids = {selector[0] for selector in aggregators[0]["variables"]}
        self.assertEqual({selector[1] for selector in aggregators[0]["variables"]}, {"report_bundle"})
        self.assertEqual(len(packer_ids), 5)
        for packer_id in packer_ids:
            packer = next(node for node in self.nodes if node["id"] == packer_id)
            self.assertEqual(packer["data"]["type"], "code")
            self.assertEqual({item["variable"] for item in packer["data"]["variables"]},
                             {"report_markdown", "evaluation_result", "final_status", "technical_details"})
            self.assertTrue(any(edge["source"] == packer_id and edge["target"] == aggregator["id"] for edge in self.graph["edges"]))
        unpack = next(node for node in self.nodes if node["data"].get("title") == "拆分统一报告")
        self.assertEqual(unpack["data"]["variables"][0]["value_selector"], [aggregator["id"], "output"])
        self.assertEqual({item["value_selector"][0] for item in report_ends[0]["outputs"]}, {unpack["id"]})

        sample = {
            "report_markdown": "# Report",
            "evaluation_result": {"status": "human_review_required"},
            "final_status": "human_review_required",
            "technical_details": {"failure_stage": "model"},
        }
        packer = next(node for node in self.nodes if node["id"] in packer_ids)
        namespace = {}
        exec(packer["data"]["code"], namespace)
        packed = namespace["main"](**sample)
        namespace = {}
        exec(unpack["data"]["code"], namespace)
        self.assertEqual(namespace["main"](**packed), sample)

    def test_public_report_never_interpolates_state_json(self):
        public_templates = [
            node
            for node in self.node_data("template-transform")
            if "报告" in node["title"]
        ]
        for node in public_templates:
            self.assertNotIn("state_json", node.get("template", ""))
            self.assertNotIn("```json", node.get("template", ""))

    def test_protected_dsl_files_are_unchanged(self):
        for path, expected in PROTECTED_HASHES.items():
            canonical_bytes = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            digest = hashlib.sha256(canonical_bytes).hexdigest()
            self.assertEqual(digest, expected, path)

    def test_image_branch_uses_real_vision_input_and_expected_profile(self):
        image_nodes = [node for node in self.node_data("llm") if node["title"] == "评估广告图片"]
        self.assertEqual(len(image_nodes), 1)
        vision = image_nodes[0]["vision"]
        self.assertTrue(vision["enabled"])
        self.assertEqual(vision["configs"]["variable_selector"], ["1900000000001", "image"])
        image_text = json.dumps(image_nodes[0], ensure_ascii=False)
        self.assertIn("ad_image_v1", self.text)
        for dimension in ("subject", "composition", "readability", "selling_point", "audience", "cta", "risk"):
            self.assertIn(dimension, image_text)

    def test_image_renderer_failure_requires_human_review(self):
        parsers = [node for node in self.node_data("code") if node["title"] == "解析图片报告"]
        self.assertEqual(len(parsers), 1)
        code = parsers[0]["code"]
        self.assertIn('"human_review_required"', code)
        self.assertIn("报告渲染失败", code)

    def test_script_branch_has_profile_dimensions_and_located_evidence(self):
        script_nodes = [node for node in self.node_data("llm") if node["title"] == "评估广告脚本"]
        self.assertEqual(len(script_nodes), 1)
        script_text = json.dumps(script_nodes[0], ensure_ascii=False)
        self.assertIn("ad_script_v1", self.text)
        for dimension in ("hook", "pain_point", "selling_point", "audience", "structure", "cta", "claim_risk"):
            self.assertIn(dimension, script_text)
        self.assertIn("location", script_text)
        self.assertIn("段落", script_text)
        self.assertIn("场景", script_text)

    def test_blank_script_is_rejected_before_model(self):
        validators = [node for node in self.node_data("if-else") if node["title"] == "脚本非空？"]
        self.assertEqual(len(validators), 1)
        llm_node = next(node for node in self.nodes if node["data"].get("title") == "评估广告脚本")
        incoming = [edge for edge in self.graph["edges"] if edge["target"] == llm_node["id"]]
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]["source"], next(node["id"] for node in self.nodes if node["data"].get("title") == "脚本非空？"))
        self.assertEqual(incoming[0]["sourceHandle"], "true")

    def test_branch_normalizers_emit_renderer_contract_fields(self):
        for title in ("规范化图片评估", "规范化脚本评估"):
            node = next(node for node in self.node_data("code") if node["title"] == title)
            code = node["code"]
            for field in ("source_type", "dimension", "finding", "priority", "problem", "impact", "suggestion", "expected_effect"):
                self.assertIn(field, code, f"{title} missing {field}")

    def test_builder_is_deterministic(self):
        first = json.dumps(build_multimodal_v1.build_dsl(), ensure_ascii=False, sort_keys=True)
        second = json.dumps(build_multimodal_v1.build_dsl(), ensure_ascii=False, sort_keys=True)
        self.assertEqual(first, second)

    def test_all_start_references_exist_and_video_extensions_match_backend(self):
        start = self.node_data("start")[0]
        variables = {item["variable"]: item for item in start["variables"]}
        references = set(re.findall(r"\{\{#1900000000001\.([A-Za-z0-9_]+)#\}\}", self.text))
        self.assertLessEqual(references, set(variables))
        self.assertNotIn("ad_script", references)
        self.assertNotIn("material_type", references)
        self.assertEqual(variables["video"]["allowed_file_extensions"], [".MP4", ".MOV"])

    def test_model_and_normalizer_failures_route_to_complete_review_result(self):
        for title in ("评估广告图片", "规范化图片评估", "评估广告脚本", "规范化脚本评估"):
            node = next(node for node in self.nodes if node["data"].get("title") == title)
            self.assertEqual(node["data"].get("error_strategy"), "fail-branch")
            fail_edges = [edge for edge in self.graph["edges"] if edge["source"] == node["id"] and edge["sourceHandle"] == "fail-branch"]
            self.assertEqual(len(fail_edges), 1, title)
        for title in ("图片分析失败转人工复核", "脚本分析失败转人工复核", "解析图片报告", "解析脚本报告", "解析报告响应"):
            code = next(node["code"] for node in self.node_data("code") if node["title"] == title)
            for field in ("asset_type", "profile", "status", "overall_score", "human_review_required", "run_summary"):
                self.assertIn(field, code, f"{title} missing {field}")

    def test_video_result_is_evidence_backed_and_not_hardcoded_as_evaluated(self):
        code = next(node["code"] for node in self.node_data("code") if node["title"] == "转换视频评估结果")
        self.assertIn("source_type", code)
        self.assertIn("evidence_refs", code)
        self.assertNotIn('"score":5', code)
        self.assertIn('"status":"partial"', code)

    def test_issue_and_suggestion_refs_use_known_evidence_ids(self):
        for title in ("规范化图片评估", "规范化脚本评估"):
            code = next(node["code"] for node in self.node_data("code") if node["title"] == title)
            self.assertIn('evidence_ids=[item["id"] for item in evidence]', code)
            self.assertIn('"evidence_refs":evidence_ids', code)

    def test_script_precheck_strips_whitespace_before_validation(self):
        precheck = next(node for node in self.node_data("code") if node["title"] == "脚本输入预检")
        self.assertIn(".strip()", precheck["code"])
        validator = next(node for node in self.node_data("if-else") if node["title"] == "脚本非空？")
        self.assertIn("2900000000299", json.dumps(validator))

    def test_normalizer_payloads_validate_against_fastapi_contract(self):
        image = self.run_code_node(
            "规范化图片评估",
            analysis={"summary":"主体清晰","dimensions":[{"dimension":"subject","score":8,"reason":"主体居中"}],"evidence":[{"dimension":"subject","finding":"水杯位于画面中央"}],"issues":["行动引导偏弱"],"strengths":["主体清晰"],"suggestions":["增加明确按钮"],"confidence":0.8},
            product_context="水杯", target_audience="通勤人群", conversion_goal="了解更多",
        )
        script = self.run_code_node(
            "规范化脚本评估",
            analysis={"summary":"结构完整","dimensions":[{"dimension":"hook","score":7,"reason":"场景明确"}],"evidence":[{"location":"场景1","dimension":"hook","finding":"开场提出通勤补水问题"}],"issues":["卖点较泛"],"strengths":["场景清晰"],"suggestions":["补充具体卖点"],"confidence":0.8},
            product_context="水杯", target_audience="通勤人群", conversion_goal="了解更多",
        )
        video = self.run_code_node(
            "转换视频评估结果",
            state_json=json.dumps({"visual_evidence":[{"summary":"主体可见","evidence":["水杯在关键帧中居中"],"missing_dimensions":["cta"],"confidence":0.8}],"script_evidence":[],"missing_dimensions":[],"optimization_plan":{"changes":["增加结尾按钮"]},"current_step":2,"completed_actions":["analyze_frames"],"retry_count":0,"supplementary_rounds":0,"final_status":"partial"}),
            product_context="水杯", target_audience="通勤人群", conversion_goal="了解更多",
        )
        for output in (image, script, video):
            request = EvaluationRequest.model_validate(json.loads(output["evaluation_json"]))
            self.assertTrue(all(item.evidence_refs for item in [*request.issues, *request.suggestions]))
        video_request = EvaluationRequest.model_validate(json.loads(video["evaluation_json"]))
        self.assertEqual(video_request.issues, [])

    def test_unsubstantiated_model_issues_require_human_review(self):
        complete_dimensions = {
            "image": ["subject", "composition", "readability", "selling_point", "audience", "cta", "risk"],
            "script": ["hook", "pain_point", "selling_point", "audience", "structure", "cta", "claim_risk"],
        }
        for asset_type, title in (("image", "规范化图片评估"), ("script", "规范化脚本评估")):
            analysis = {
                "summary": "模型报告存在问题",
                "dimensions": [{"dimension": key, "score": 8, "reason": "已评估"} for key in complete_dimensions[asset_type]],
                "evidence": [],
                "issues": ["行动引导不明确"],
                "strengths": [],
                "suggestions": ["增加按钮"],
                "confidence": 0.9,
            }
            output = self.run_code_node(title, analysis=analysis, product_context="水杯", target_audience="通勤人群", conversion_goal="了解更多")
            request = EvaluationRequest.model_validate(json.loads(output["evaluation_json"]))
            self.assertTrue(request.human_review_required)
            self.assertIn("issue_evidence", request.missing_information)
            self.assertEqual(request.issues, [])
            self.assertEqual(request.suggestions, [])

    def test_renderer_fallbacks_are_complete_evaluation_results(self):
        for title in ("解析报告响应", "解析图片报告", "解析脚本报告"):
            output = self.run_code_node(title, body="not-json", status_code=500, fallback_details={})
            result = EvaluationResult.model_validate(output["evaluation_result"])
            self.assertEqual(result.status, "human_review_required")


if __name__ == "__main__":
    unittest.main()
