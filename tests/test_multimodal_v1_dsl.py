import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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

    def test_outputs_separate_report_and_technical_details(self):
        ends = [node for node in self.node_data("end") if node["title"] == "输出多模态报告"]
        self.assertEqual(len(ends), 1)
        output_names = {item["variable"] for item in ends[0]["outputs"]}
        self.assertEqual(
            output_names,
            {"report_markdown", "evaluation_result", "final_status", "technical_details"},
        )
        self.assertIn("/api/v1/evaluations/render", self.text)

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
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
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


if __name__ == "__main__":
    unittest.main()
