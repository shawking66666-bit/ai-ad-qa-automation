import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "workflow" / "candidate" / "AI-Ad-QA-agent-v1.yml"


class DifyAgentV1DslTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CANDIDATE.is_file(), f"candidate DSL missing: {CANDIDATE}")
        self.text = CANDIDATE.read_text(encoding="utf-8")
        self.dsl = json.loads(self.text)
        self.graph = self.dsl["workflow"]["graph"]
        self.nodes = self.graph["nodes"]

    def node_data(self, node_type):
        return [node["data"] for node in self.nodes if node["data"].get("type") == node_type]

    def test_uses_only_official_deepseek_model(self):
        llm_nodes = self.node_data("llm")
        self.assertGreaterEqual(len(llm_nodes), 3)
        for node in llm_nodes:
            self.assertEqual(node["model"]["provider"], "langgenius/deepseek/deepseek")
            self.assertEqual(node["model"]["name"], "deepseek-flash")
        lowered = self.text.lower()
        self.assertNotIn("claude", lowered)
        self.assertNotIn("openai", lowered)
        self.assertNotIn("litellm", lowered)

    def test_has_bounded_controlled_loop_and_state(self):
        loops = self.node_data("loop")
        self.assertEqual(len(loops), 1)
        self.assertEqual(loops[0]["loop_count"], 5)
        self.assertEqual(loops[0]["logical_operator"], "and")
        self.assertTrue(loops[0]["loop_variables"])
        self.assertEqual(loops[0]["loop_variables"][0]["label"], "state_json")

        required_state = {
            "video_id",
            "duration_seconds",
            "current_step",
            "completed_actions",
            "used_timestamps",
            "visual_evidence",
            "script_evidence",
            "missing_dimensions",
            "errors",
            "retry_count",
            "supplementary_rounds",
            "needs_human_review",
            "final_status",
        }
        for field in required_state:
            self.assertIn(field, self.text)

        assigners = self.node_data("assigner")
        self.assertEqual(len(assigners), 5)
        self.assertTrue(all(node.get("version") == "2" for node in assigners))
        self.assertTrue(all(len(node.get("items", [])) == 2 for node in assigners))

    def test_decision_is_structured_and_actions_are_whitelisted(self):
        decision = next(node for node in self.node_data("llm") if node["title"] == "Agent 决策")
        schema = decision["structured_output"]["schema"]
        self.assertTrue(decision["structured_output_enabled"])
        self.assertEqual(
            set(schema["required"]), {"action", "reason", "arguments", "should_stop"}
        )
        self.assertEqual(
            set(schema["properties"]["action"]["enum"]),
            {
                "analyze_frames",
                "extract_additional_frames",
                "check_ad_script",
                "generate_optimization_plan",
                "stop",
            },
        )

    def test_agent_api_lifecycle_and_cleanup_are_present(self):
        http_nodes = self.node_data("http-request")
        urls = [node["url"] for node in http_nodes]
        self.assertIn(
            "http://host.docker.internal:8000/api/v1/agent-videos",
            urls,
        )
        self.assertTrue(any("/api/v1/agent-videos/{{#" in url and url.endswith("/frames") for url in urls))
        cleanup = [node for node in http_nodes if node["title"] == "清理 Agent 视频任务"]
        self.assertEqual(len(cleanup), 1)
        self.assertEqual(cleanup[0]["method"], "delete")

    def test_dify_video_url_is_forwarded_without_serializing_file(self):
        templates = self.node_data("template-transform")
        self.assertFalse(
            any(node["title"] == "提取 Dify 视频引用" for node in templates)
        )

        create = next(
            node
            for node in self.node_data("http-request")
            if node["title"] == "创建 Agent 视频任务"
        )
        self.assertEqual(create["body"]["type"], "form-data")
        self.assertEqual(
            create["body"]["data"],
            [
                {
                    "id": "video-url",
                    "key": "video_url",
                    "type": "text",
                    "value": "{{#1900000000001.video.url#}}",
                }
            ],
        )

        edges = self.graph["edges"]
        self.assertTrue(
            any(
                edge["source"] == "1900000000001"
                and edge["target"] == "1900000000002"
                for edge in edges
            )
        )

    def test_terminal_report_is_deterministic_and_secret_free(self):
        templates = self.node_data("template-transform")
        self.assertTrue(any(node["title"] == "生成最终报告" for node in templates))
        for status in ("completed", "partial", "human_review_required"):
            self.assertIn(status, self.text)
        secret_patterns = [
            r"sk-[A-Za-z0-9_-]{16,}",
            r"(?i)api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_-]{16,}",
            r"(?i)bearer\s+[A-Za-z0-9._-]{16,}",
        ]
        for pattern in secret_patterns:
            self.assertIsNone(re.search(pattern, self.text), pattern)


if __name__ == "__main__":
    unittest.main()
