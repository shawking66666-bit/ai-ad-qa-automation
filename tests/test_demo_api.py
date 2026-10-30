import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from demo.app import create_demo_app
from demo.dify_client import DifyError


class FakeDify:
    def __init__(self, error=None):
        self.error = error
        self.uploads = []
        self.runs = []

    def upload_file(self, content, filename, user):
        self.uploads.append((content, filename, user))
        return "file-123"

    def run_workflow(self, inputs, user):
        self.runs.append((inputs, user))
        if self.error:
            raise self.error
        return {"report_markdown": "# 测试报告", "final_status": "human_review_required",
                "technical_details": {"state_json": "must-not-leak"}}


class DemoApiTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDify()
        self.client = TestClient(create_demo_app(self.fake))

    def test_script_run_maps_inputs_and_strips_technical_details(self):
        response = self.client.post("/api/evaluate", data={
            "asset_type": "script", "script": "通勤保温杯广告文案",
            "product_context": "保温杯", "target_audience": "通勤人群",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "report_markdown": "# 测试报告", "final_status": "human_review_required"
        })
        inputs, user = self.fake.runs[0]
        self.assertEqual(inputs["script"], "通勤保温杯广告文案")
        self.assertEqual(inputs["target_audience"], "通勤人群")
        self.assertEqual(user, "portfolio-demo")

    def test_video_upload_maps_dify_file_input(self):
        response = self.client.post("/api/evaluate", data={"asset_type": "video"}, files={
            "video": ("sample.mp4", b"\x00\x00\x00\x18ftypisom", "video/mp4")
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake.uploads[0][1], "sample.mp4")
        self.assertEqual(self.fake.runs[0][0]["video"], {
            "transfer_method": "local_file", "upload_file_id": "file-123", "type": "video"
        })

    def test_image_upload_maps_dify_file_input(self):
        response = self.client.post("/api/evaluate", data={"asset_type": "image"}, files={
            "image": ("sample.png", b"\x89PNG\r\n\x1a\nabc", "image/png")
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake.runs[0][0]["image"]["type"], "image")

    def test_rejects_invalid_extension_and_empty_script(self):
        invalid_file = self.client.post("/api/evaluate", data={"asset_type": "video"}, files={
            "video": ("sample.txt", b"text", "text/plain")
        })
        empty_script = self.client.post("/api/evaluate", data={"asset_type": "script", "script": "  "})
        self.assertEqual(invalid_file.status_code, 415)
        self.assertEqual(empty_script.status_code, 400)
        self.assertEqual(self.fake.uploads, [])

    def test_rejects_file_with_invalid_signature(self):
        response = self.client.post("/api/evaluate", data={"asset_type": "image"}, files={
            "image": ("sample.png", b"not a PNG", "image/png")
        })
        self.assertEqual(response.status_code, 415)

    def test_rejects_oversized_file_before_dify(self):
        response = self.client.post("/api/evaluate", data={"asset_type": "image"}, files={
            "image": ("sample.png", b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024), "image/png")
        })
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.fake.uploads, [])

    def test_reports_missing_key_without_contacting_dify(self):
        with patch.dict("os.environ", {}, clear=True):
            client = TestClient(create_demo_app())
            response = client.post("/api/evaluate", data={"asset_type": "script", "script": "文案"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("密钥", response.json()["detail"])

    def test_dify_error_is_safe_for_browser(self):
        client = TestClient(create_demo_app(FakeDify(DifyError("Dify 工作流未成功完成"))))
        response = client.post("/api/evaluate", data={"asset_type": "script", "script": "文案"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("state_json", response.text)

    def test_page_and_assets_load_without_technical_outputs_or_unsafe_html(self):
        page = self.client.get("/")
        script = self.client.get("/static/app.js")
        style = self.client.get("/static/style.css")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertEqual(style.status_code, 200)
        self.assertIn("AIGC 广告素材质检", page.text)
        self.assertIn("textContent", script.text)
        self.assertNotIn("innerHTML", script.text)
        self.assertNotIn("technical_details", page.text + script.text)
        self.assertNotIn("DIFY_DEMO_API_KEY", page.text + script.text)


if __name__ == "__main__":
    unittest.main()
