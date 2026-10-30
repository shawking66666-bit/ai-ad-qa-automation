import io
import json
import unittest
from urllib.error import HTTPError, URLError

from demo.dify_client import DifyClient, DifyError


class DifyClientTests(unittest.TestCase):
    def test_upload_file_uses_local_api_and_returns_id(self):
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return io.BytesIO(json.dumps({"id": "uploaded-123"}).encode())

        client = DifyClient("private-key", opener=opener)
        self.assertEqual(client.upload_file(b"video", "sample.mp4", "demo-user"), "uploaded-123")
        request, timeout = requests[0]
        self.assertEqual(request.full_url, "http://localhost:18080/v1/files/upload")
        self.assertIn(b'name="file"', request.data)
        self.assertIn(b'name="user"', request.data)
        self.assertEqual(request.get_header("Authorization"), "Bearer private-key")
        self.assertGreater(timeout, 0)

    def test_run_workflow_extracts_only_report_and_status(self):
        def opener(request, timeout):
            payload = json.loads(request.data)
            self.assertEqual(payload["inputs"]["asset_type"], "script")
            self.assertEqual(payload["response_mode"], "blocking")
            return io.BytesIO(json.dumps({"data": {"status": "succeeded", "outputs": {
                "report_markdown": "# 报告", "final_status": "completed",
                "technical_details": {"state_json": "private"},
            }}}).encode())

        result = DifyClient("private-key", opener=opener).run_workflow(
            {"asset_type": "script"}, "demo-user"
        )
        self.assertEqual(result, {"report_markdown": "# 报告", "final_status": "completed"})

    def test_run_workflow_rejects_missing_report(self):
        client = DifyClient("private-key", opener=lambda request, timeout: io.BytesIO(
            b'{"data":{"status":"succeeded","outputs":{}}}'
        ))
        with self.assertRaises(DifyError):
            client.run_workflow({"asset_type": "script"}, "demo-user")

    def test_run_workflow_rejects_failed_status(self):
        client = DifyClient("private-key", opener=lambda request, timeout: io.BytesIO(
            b'{"data":{"status":"failed","outputs":{"report_markdown":"ok"}}}'
        ))
        with self.assertRaises(DifyError):
            client.run_workflow({"asset_type": "script"}, "demo-user")

    def test_upload_rejects_malformed_response(self):
        client = DifyClient("private-key", opener=lambda request, timeout: io.BytesIO(b"not json"))
        with self.assertRaises(DifyError):
            client.upload_file(b"data", "sample.png", "demo-user")

    def test_auth_error_never_exposes_key(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 401, "unauthorized", None, None)

        client = DifyClient("private-key", opener=opener)
        with self.assertRaisesRegex(DifyError, "密钥无效") as raised:
            client.run_workflow({}, "demo-user")
        self.assertNotIn("private-key", str(raised.exception))

    def test_upload_size_error_is_actionable(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 413, "too large", None, None)

        client = DifyClient("private-key", opener=opener)
        with self.assertRaisesRegex(DifyError, "上传大小"):
            client.upload_file(b"data", "sample.mp4", "demo-user")

    def test_timeout_is_actionable(self):
        def opener(request, timeout):
            raise URLError("timed out")

        client = DifyClient("private-key", opener=opener)
        with self.assertRaisesRegex(DifyError, "无法连接本地 Dify"):
            client.run_workflow({}, "demo-user")


if __name__ == "__main__":
    unittest.main()
