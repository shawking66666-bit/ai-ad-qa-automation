# Dify 工作流版本管理

## 目录

- `current/AI-Ad-QA-current.yml`：个人电脑应导入的当前版本。
- `candidate/AI-Ad-QA-<功能>-v<版本>.yml`：开发和评审中的候选版本；未获明确批准前不能替换 `current`。
- `archive/`：已经发布过的历史版本，只用于回滚和比较。
- `tools/`：只放用于生成或校验 DSL 的确定性脚本；脚本不得读取 Dify 凭据，也不得直接导入或发布应用。

## 候选版本规则

1. 新功能先在 `candidate/` 中形成独立 DSL，禁止直接修改 `current`。
2. 文件名使用 `AI-Ad-QA-<功能>-v<版本>.yml`；受控 Agent 使用 `AI-Ad-QA-agent-v1.yml`，多模态内容质检 V1 使用 `AIGC-Multimodal-QA-v1.yml`。
3. 候选 DSL 必须完成导入检查、模拟分支测试、真实最小闭环测试和凭据扫描。
4. 扫描确认不得包含 API Key、密码、Token、Cookie 或本机私密路径；模型凭据只保存在 Dify 的凭据管理中。
5. 评审通过后，先把原 `current` 复制到带版本和日期的 `archive`，再由用户明确批准是否替换 `current`。
6. 导入候选应用只用于开发验证，不等于发布，也不得覆盖现有应用。

## 多模态内容质检 V1

- 候选文件：`candidate/AIGC-Multimodal-QA-v1.yml`。
- 输入按 `asset_type` 路由到视频、图片或脚本分支；三类分支最终都输出统一的结构化评估结果和可读 Markdown 报告。
- `technical_details` 只用于排障，不进入对外报告正文。
- 当前 `current/AI-Ad-QA-current.yml` 与既有 `candidate/AI-Ad-QA-agent-v1.yml` 均为受保护基线；多模态候选通过完整验证并获得用户明确批准前，不得替换它们。

## 更新步骤

1. 在 Dify 中创建名称清晰的候选应用，不修改现有应用。
2. 完成测试后导出到 `candidate/`，执行凭据扫描和人工评审。
3. 用户明确批准升级后，把旧 `current` 复制到 `archive/AI-Ad-QA-v<版本>-<日期>.yml`。
4. 再将获批候选复制为 `current/AI-Ad-QA-current.yml`。
5. Git 提交、推送以及 Dify 发布仍分别需要用户授权。
6. 另一台电脑取得更新后，仍需在 Dify 界面手动导入 current DSL。

> Dify 不会自动监听 GitHub 中的 DSL 变化。Git 更新完成后，仍需在
> Dify 界面中导入新版本。
