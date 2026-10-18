# AI-Ad-QA Dify 受控 Agent 第一版设计

## 1. 目标

在保留当前固定 Dify 工作流基线的前提下，新增一个作品集级的受控多模态广告质检 Agent。第一版不使用 Dify 1.15.0 的新版 Agent 节点，而是在 Dify Workflow 中通过“模型决策、条件分支、工具执行、状态更新、Loop 再决策和显式停止”实现 Agent 闭环。

系统必须证明：

- 模型能够根据当前证据选择下一步动作；
- 工具结果会返回模型并影响下一轮决策；
- 系统具备最大步数、重试限制和停止条件；
- 每条广告问题和建议可以追溯到关键帧、脚本或用户输入；
- 当前固定工作流和现有 `/api/v1/videos/extract` 契约不受破坏。

## 2. 第一版范围

第一版包含：

- 一个 Dify Workflow 中的受控 Agent 循环；
- Dify 官方 DeepSeek 提供器 `0.0.24` 的 `DeepSeek V4.1 Flash` 模型；
- 四类动作：关键帧分析、补帧、脚本检查和优化方案生成；
- 一个 Agent 专用视频任务生命周期；
- 最多五个决策步骤；
- 最多一次补帧；
- 同一失败操作最多重试一次；
- `completed`、`partial`、`human_review_required` 三种终态；
- FastAPI 单元与集成测试；
- Dify 模拟决策测试和一次真实 API 闭环验证。

第一版不包含：

- 多 Agent；
- Dify 1.15.0 新版 Agent 节点或额外 Agent backend 部署；
- LiteLLM；
- Claude 或 OpenAI 模型；
- `deepseek-v4-pro`；
- RAG、向量数据库、MCP、长期记忆；
- Redis、消息队列、Kubernetes；
- 自动发布或生产部署。

## 3. 已有基线

当前工作流为固定路径：

```text
用户输入
→ FastAPI 上传并切片
→ 解析结果与成功/失败分支
→ 下载关键帧
→ Claude 视觉评价
→ Claude 优化方案
→ Markdown 报告
```

当前 FastAPI 已提供：

- `GET /health`；
- `POST /api/v1/videos/extract`；
- `GET /files/{video_id}/{filename}`；
- MP4/MOV 文件校验；
- 500 MiB 默认上传限制；
- FFmpeg/FFprobe 显式超时；
- UUID 任务目录；
- 七天过期目录清理；
- 成功切片后立即删除源视频。

现有 `/api/v1/videos/extract` 必须保持当前行为和响应结构，继续服务固定工作流。

## 4. 目标架构

```text
用户上传视频和广告信息
→ 固定预处理
  → 创建 Agent 视频任务
  → 校验视频
  → 初始切片
  → 下载初始关键帧
  → 初始化 Agent 状态
→ Dify Loop，最多五轮
  → DeepSeek V4.1 Flash 输出结构化决策
  → 校验动作和参数
  → 条件分支执行动作
  → 将结果合并回 Agent 状态
  → 判断继续或停止
→ 校验最终报告
→ 清理 Agent 视频任务
→ 输出 Markdown 报告
```

固定流程负责文件校验、上传、切片、解析、超时、错误分类、状态合并、格式校验、任务清理和报告渲染。模型只负责需要判断的部分：证据是否充分、下一步动作、补帧时间点、问题归纳和优化建议。

## 5. 用户输入

继续沿用当前 DSL 中已经存在的实际输入字段。实施时必须从当前 DSL 读取并映射字段，不得仅根据本设计中的展示名称擅自重命名。

业务输入至少覆盖：

- 广告视频；
- 产品名称或产品信息；
- 目标人群；
- 转化目标；
- 广告脚本；
- 其他要求。

缺失的非必填信息由状态记录为 `missing_input`。第一版不增加多轮用户追问；缺失信息会降低结论范围，必要时输出 `partial` 或 `human_review_required`。

## 6. 固定评估维度

第一版不允许模型自由发明评估框架。必须检查以下六项：

| 维度 | 证据充分条件 |
| --- | --- |
| 前三秒钩子 | 能关联具体关键帧或脚本内容 |
| 商品展示 | 至少有一张能够判断商品展示情况的关键帧 |
| 核心卖点 | 脚本或画面中存在可引用的卖点证据，或明确判定缺失 |
| 目标人群 | 能将画面或脚本与用户输入的目标人群进行对照 |
| 脚本结构 | 能判断钩子、痛点、卖点和行动引导是否存在 |
| CTA | 能关联明确 CTA 证据，或明确判定 CTA 缺失 |

“证据充分”不代表广告表现优秀；明确、可追溯的缺失同样是一种有效证据。

## 7. Agent 状态

每一轮使用结构化状态，最小字段如下：

```json
{
  "video_id": "uuid",
  "duration_seconds": 30.0,
  "current_step": 1,
  "completed_actions": [],
  "used_timestamps": [0.0, 3.0, 6.0],
  "visual_evidence": [],
  "script_evidence": [],
  "missing_dimensions": [],
  "errors": [],
  "retry_count": 0,
  "supplementary_rounds": 0,
  "needs_human_review": false,
  "final_status": "running"
}
```

状态由 Dify 节点显式传递和更新，不依赖模型自行记忆。模型每一轮必须读取完整的当前状态，只返回本轮决策，不得直接覆盖历史证据。

## 8. 决策输出

模型决策必须符合固定 Schema：

```json
{
  "action": "extract_additional_frames",
  "reason": "现有关键帧没有清晰展示商品",
  "arguments": {
    "timestamps": [8.0, 12.0]
  },
  "should_stop": false
}
```

允许的 `action`：

- `analyze_frames`；
- `extract_additional_frames`；
- `check_ad_script`；
- `generate_optimization_plan`；
- `stop`。

未知动作、缺少必需参数或类型错误均不得执行。第一次格式错误进入一次结构修复；第二次格式错误终止循环并设为 `human_review_required`。

## 9. 动作与工具契约

### 9.1 analyze_frames

职责：使用 `DeepSeek V4.1 Flash` 分析当前可用关键帧。

输入：

- 关键帧文件及时间点；
- 产品信息；
- 目标人群；
- 转化目标；
- 当前缺失维度。

输出至少包含：

- 带时间点引用的视觉证据；
- 缺失维度；
- 建议补看的时间点；
- 置信度；
- 是否需要更多关键帧。

### 9.2 extract_additional_frames

职责：从仍处于 Agent 任务生命周期内的源视频按指定时间点补帧。

输入：

- `video_id`；
- `timestamps`。

约束：

- 每次最多三个时间点；
- 时间点必须大于等于零且小于视频时长；
- 第一版最多执行一次补帧动作；
- 已使用时间点不得重复生成；
- FFmpeg 调用必须使用现有显式超时。

输出：

- 新关键帧的时间点、阶段提示、文件名和本地 URL；
- 被忽略的重复或无效时间点；
- 警告列表。

### 9.3 check_ad_script

职责：检查脚本与产品、受众和转化目标的匹配情况。

输出至少覆盖：

- 钩子；
- 痛点；
- 核心卖点；
- CTA；
- 目标人群匹配；
- 缺失维度；
- 置信度。

### 9.4 generate_optimization_plan

职责：只基于已经记录的视觉证据、脚本证据和用户输入生成优化方案。

仅当视觉分析和脚本检查均完成，且不存在仍可通过允许工具补充的必需维度时允许调用。

输出至少包含：

- 总体结论；
- 按优先级排序的问题；
- 每个问题对应的证据；
- 可执行修改建议；
- A/B 测试建议；
- 最终状态。

## 10. Agent 专用视频任务 API

保留原接口不变，新增：

```text
POST /api/v1/agent-videos
POST /api/v1/agent-videos/{video_id}/frames
DELETE /api/v1/agent-videos/{video_id}
```

### 10.1 创建任务

`POST /api/v1/agent-videos` 接收一个 MP4 或 MOV 文件，执行现有上传限制、空文件检查、FFprobe 时长检查和初始切片，但不立即删除源视频。

响应沿用现有帧结构，并增加 Agent 生命周期所需信息：

```json
{
  "video_id": "uuid",
  "duration_seconds": 30.0,
  "frames": [],
  "warnings": [],
  "source_retained_until": "ISO-8601 timestamp"
}
```

### 10.2 补帧

`POST /api/v1/agent-videos/{video_id}/frames` 接收 JSON：

```json
{
  "timestamps": [8.0, 12.0]
}
```

任务不存在、已过期、源视频已删除或 ID 非法时返回 404；参数无效返回 422；磁盘不足沿用 507；其他受控运行错误返回明确错误信息。

### 10.3 清理任务

`DELETE /api/v1/agent-videos/{video_id}` 删除对应 UUID 任务目录。删除操作必须限制在配置的数据根目录内，不跟随符号链接。

任务正常结束时立即清理。未正常清理的 Agent 源视频最长保留两小时；现有七天目录清理仍作为其他生成数据的总兜底，但 Agent 源视频使用更短的两小时生命周期。

## 11. DeepSeek 接入

第一版直接使用 Dify 官方 DeepSeek 提供器的 `DeepSeek V4.1 Flash`：

- 不经过 LiteLLM；
- 不混用其他模型；
- 同一模型承担视觉分析、决策、脚本检查和报告生成；
- API 密钥由用户在 Dify 中手动配置；
- 代码、DSL、文档、日志和测试中不得出现密钥。

本地帧 URL `host.docker.internal` 只能由本地 Dify 容器访问，不能假设 DeepSeek 云端可以下载。Dify 必须先读取本地图片，再将图片数据作为模型视觉输入发送。实施完整循环前必须完成“一张本地测试图片 → Dify → DeepSeek 官方 API → 结构化结果”的最小验证。

如果 Dify 1.15.0 中的 DeepSeek 提供器无法把图片作为视觉输入发送，必须停止完整画布改造并报告证据；不得把只处理文字的调用称为视频分析成功。备用方案需要另行设计和批准。

## 12. Loop 与停止条件

Loop 最多执行五轮。无论模型输出什么，第五轮结束后必须退出。

额外限制：

- 最多一次补帧；
- 同一失败动作最多重试一次；
- 视觉分析最多两次；
- 脚本检查最多一次成功结果；
- 优化方案最多生成一次。

终态：

- `completed`：六项维度均有可追溯证据或可追溯的明确缺失，且已生成优化方案；
- `partial`：保留了部分可靠证据，但因工具或模型失败无法完整分析；
- `human_review_required`：输入不足、证据冲突、连续格式错误、源视频不可用或低置信度导致无法可靠判断。

## 13. 错误处理

### 视频处理失败

格式错误、空视频、FFprobe 失败、FFmpeg 失败或磁盘空间不足时，不进入 Agent Loop，直接返回对应阶段和错误。

### DeepSeek 调用失败

第一次失败允许重试一次。第二次失败结束循环，根据已有证据输出 `partial`；没有可用证据时输出 `human_review_required`。

### 决策格式错误

第一次要求模型仅按 Schema 修复；第二次设为 `human_review_required` 并停止。

### 补帧失败

无效时间点不执行并记录警告；源视频不存在或已过期时停止并转人工复核；FFmpeg 失败最多重试一次。

### 清理失败

报告仍可输出，但必须包含内部运行警告并依赖两小时清理兜底。最终用户报告不得暴露本地绝对路径、堆栈或密钥。

## 14. 报告输出

最终报告至少包含：

- 运行状态；
- 广告总体评价；
- 六项评估维度；
- 带时间点或输入来源的证据；
- 按优先级排序的问题；
- 可执行优化建议；
- A/B 测试建议；
- 缺失信息和人工复核提示；
- Agent 运行摘要：步骤数、是否补帧、停止原因。

报告格式由确定性模板节点完成，不让模型控制 Markdown 外壳。

## 15. 测试策略

### FastAPI 自动化测试

- 创建 Agent 视频任务成功；
- 任务期间源视频存在；
- 指定合法时间点补帧成功；
- 拒绝负数和超出时长的时间点；
- 一次最多补取三帧；
- 重复时间点不重复生成；
- 非 UUID、未知和过期任务返回 404；
- 删除任务后帧和源视频不可访问；
- 超过两小时的 Agent 源视频能够被清理；
- 原有 `/api/v1/videos/extract` 行为和响应契约保持不变；
- 完整现有测试套件继续通过。

### Agent 循环测试

使用固定模拟决策覆盖：

- 初始证据充分，直接生成报告；
- 初始证据不足，补帧后完成；
- DeepSeek 连续失败，输出 `partial`；
- 决策 JSON 连续错误，转人工复核；
- 达到五步限制后强制停止；
- 重复请求补帧时拒绝第二轮；
- 未完成必要分析时拒绝提前生成优化方案。

### 真实链路验证

按顺序验证：

1. 一张本地测试图片的 DeepSeek 视觉输入；
2. 程序生成的非敏感短视频完成上传、初始切片和补帧；
3. 模拟决策完成 Dify Loop；
4. DeepSeek 官方 API 完成一次受控 Loop；
5. 用户提供的非敏感真实广告视频生成报告并由用户人工复核。

程序生成视频只能证明技术链路，不能证明广告分析质量。

## 16. 文件与版本策略

不得修改现有：

```text
workflow/current/AI-Ad-QA-current.yml
```

新版 DSL 保存为候选版本：

```text
workflow/candidate/AI-Ad-QA-agent-v1.yml
```

实施前先创建 `workflow/candidate/` 并在 `workflow/README.md` 中定义候选版本的用途、命名和晋级规则，再放置 DSL，以遵守“新目录先定结构约定”的项目纪律。

预计代码变化集中在：

- `video_processor/app.py`：Agent 视频任务 API；
- `video_processor/service.py`：补帧和时间点校验所需的可复用能力；
- `tests/`：新 API、生命周期和兼容性测试；
- `workflow/candidate/`：候选 Dify DSL；
- `workflow/README.md`：版本管理约定；
- `docs/`：运行与验证说明。

当前目录不是 Git 仓库，因此本设计可以保存和执行验证，但无法在此目录提交 commit。不得擅自初始化 Git、推送或发布 Dify 应用。

## 17. 验收标准

第一版完成必须同时满足：

- 当前固定 DSL 和 `/extract` 接口未被破坏；
- Agent 视频任务支持真实的第二轮指定时间点补帧；
- Dify Loop 中至少发生一次“决策 → 工具 → 结果反馈 → 再决策”；
- 最大步数、最大补帧次数和重试限制生效；
- 三种终态均有自动化覆盖；
- 最终报告中的问题可以追溯到关键帧、脚本或用户输入；
- 自动化测试全部通过；
- 使用同一测试案例对比固定工作流版与 Agent 版；
- 真实广告视频报告经过人工复核；
- 没有修改 `.env`、密钥、Docker 配置、系统设置；
- 没有推送、发布或公开任何内容。
