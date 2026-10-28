# Dify 受控 Agent V1 运行手册

## 多模态候选补充

`workflow/candidate/AIGC-Multimodal-QA-v1.yml` 是独立候选应用，增加 `video / image / script` 路由。导入时必须新建候选应用，不得覆盖 current 或既有 Agent V1。

最小验证素材位于 `tests/fixtures/multimodal/`。图片与脚本使用固定公开夹具；视频由 `tests/video_fixtures.py` 生成。每次 live run 记录状态、分数、问题数、证据数、人工复核标记、报告标题和原始 JSON 泄漏检查。完整验证状态见 `docs/multimodal-v1-validation.md`。

## 1. 边界

- 当前固定工作流保持不变；Agent V1 作为独立候选应用验证。
- 只使用 Dify Workflow 的 Loop、条件分支和 HTTP 工具，不使用 Agent V2。
- 模型只使用 DeepSeek 官方提供器 `0.0.24` 的 `DeepSeek V4.1 Flash`，不经过 LiteLLM。
- API Key 由用户在 Dify 凭据界面手动填写，不复制到聊天、代码、DSL、日志或截图。
- 未通过单图视觉预检前，不创建完整 Agent 画布，不宣称已经具备视频视觉分析能力。

## 2. 服务启动

1. 启动现有 Docker Desktop 和既有 Dify Compose；不得修改 `.env` 或 Compose。
2. 在项目根目录运行 `启动FastAPI.cmd`，或运行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\start_video_processor.ps1
   ```

3. 运行 `检查FastAPI状态.cmd`，确认宿主机 `http://localhost:8000/health` 返回 `{"status":"ok"}`。
4. 从 Dify 容器确认 `http://host.docker.internal:8000/health` 可访问。

## 3. DeepSeek 单图视觉预检

1. 在 Dify 中确认版本为 `1.15.0`，且 Workflow 画布可创建 Loop 和支持图片输入的 LLM 节点。
2. 新建临时 Workflow，不导入或覆盖当前应用。
3. 在模型提供器中选择 DeepSeek 官方提供器 `0.0.24` 和界面标识 `DeepSeek V4.1 Flash`。
4. 由用户直接在 Dify 中填写 API Key；执行者不观察、不记录该值。
5. 上传一张无敏感信息的本地 JPEG。必须把图片文件内容作为 LLM 的视觉输入，不能只把 `host.docker.internal` URL 当文字发给云端模型。
6. 要求模型返回结构化字段：

   ```json
   {
     "summary": "string",
    "visible_text": "string",
     "confidence": 0.0
   }
   ```

7. 成功标准：节点执行成功，三个字段均能被 Dify Schema 解析，`confidence` 是 0 到 1 的数值，并且结果确实描述图片内容。
8. 失败时只记录脱敏后的错误。若提供器不支持传图或仅处理文字，停止 Agent 画布开发；FastAPI 直连模型属于新的密钥与运行边界设计，需另行批准。

## 4. 预检记录

| 字段 | 结果 |
|---|---|
| 执行时间 | `2026-10-10 18:32:54` |
| Dify 版本 | `1.15.0`（2026-10-10 界面确认） |
| 模型标识 | DeepSeek 官方提供器 `0.0.24` / `DeepSeek V4.1 Flash` / `VISION` |
| 图片来源 | `.test-runtime/preflight/deepseek-vision-preflight.jpg`，640×360，深蓝底白字 `VISION TEST 2026` |
| `summary` Schema | 通过：`A solid dark blue background with white centered text reading "VISION TEST 2026".` |
| `visible_text` Schema | 通过：`VISION TEST 2026` |
| `confidence` Schema | 通过：`0.99` |
| 耗时 | `1.300s`，587 tokens，3 步 |
| 脱敏错误 | 无 |
| 结论 | 通过硬门禁：Dify 已将本地 JPEG 文件作为 `File` 视觉输入传给 DeepSeek，三个字段被 JSON Schema 正确解析，允许进入 Task 7。 |

## 5. Agent 临时文件生命周期

- `POST /api/v1/agent-videos` 创建任务并保留源视频最多两小时。
- 每个任务最多调用一次补帧接口，每次最多接受三个新的有效时间点。
- 工作流正常结束时调用 `DELETE /api/v1/agent-videos/{video_id}`，立即删除源视频、帧和元数据。
- 进程异常退出时，FastAPI 下次启动会删除超过两小时且元数据完整的 Agent 任务目录。
- 元数据损坏的目录按短周期清理规则保守保留；旧工作流的纯帧目录继续使用原有七天 UUID 目录清理规则。
- 最终报告由 Dify 输出，不保存在上述临时 Agent 任务目录中。
