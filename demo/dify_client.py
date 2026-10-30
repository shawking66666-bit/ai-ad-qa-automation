"""Small server-side adapter for the fixed local Dify Workflow API."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


DIFY_API_BASE_URL = "http://localhost:18080/v1"


class DifyError(Exception):
    """A safe-to-display Dify integration failure."""


class DifyClient:
    def __init__(self, key: str, opener=None):
        if not key or not key.strip():
            raise DifyError("演示服务未配置 Dify API 密钥")
        self._key = key.strip()
        self._opener = opener or urlopen

    def _request(self, path: str, data: bytes, content_type: str, timeout: int) -> dict:
        request = Request(
            DIFY_API_BASE_URL + path,
            data=data,
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": content_type,
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise DifyError("Dify API 密钥无效或没有访问该工作流的权限") from None
            if exc.code == 413:
                raise DifyError("文件超过 Dify 允许的上传大小") from None
            raise DifyError(f"Dify 请求失败（HTTP {exc.code}）") from None
        except (URLError, TimeoutError):
            raise DifyError("无法连接本地 Dify，或工作流运行超时") from None
        except (ValueError, UnicodeError, TypeError):
            raise DifyError("Dify 返回了无法解析的响应") from None
        if not isinstance(payload, dict):
            raise DifyError("Dify 返回了无法解析的响应")
        return payload

    def upload_file(self, content: bytes, filename: str, user: str) -> str:
        boundary = uuid4().hex
        safe_name = Path(filename).name.replace('"', "").replace("\r", "").replace("\n", "")
        media_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="user"\r\n\r\n{user}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
            f"Content-Type: {media_type}\r\n\r\n"
        ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode()
        payload = self._request(
            "/files/upload", body, f"multipart/form-data; boundary={boundary}", 45
        )
        file_id = payload.get("id")
        if not isinstance(file_id, str) or not file_id:
            raise DifyError("Dify 文件上传成功，但未返回文件 ID")
        return file_id

    def run_workflow(self, inputs: dict, user: str) -> dict[str, str]:
        body = json.dumps(
            {"inputs": inputs, "response_mode": "blocking", "user": user},
            ensure_ascii=False,
        ).encode("utf-8")
        payload = self._request("/workflows/run", body, "application/json", 120)
        data = payload.get("data")
        if not isinstance(data, dict) or data.get("status") != "succeeded":
            raise DifyError("Dify 工作流未成功完成，请在 Dify 日志中查看详情")
        outputs = data.get("outputs")
        if not isinstance(outputs, dict):
            raise DifyError("Dify 工作流没有返回报告")
        report = outputs.get("report_markdown")
        if not isinstance(report, str) or not report.strip():
            raise DifyError("Dify 工作流没有返回可读报告")
        status = outputs.get("final_status")
        return {
            "report_markdown": report,
            "final_status": status if isinstance(status, str) else "unknown",
        }
