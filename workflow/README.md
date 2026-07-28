# Dify 工作流版本管理

## 目录

- `current/AI-Ad-QA-current.yml`：个人电脑应导入的当前版本。
- `archive/`：已经发布过的历史版本，只用于回滚和比较。

## 更新步骤

1. 在公司电脑的 Dify 中完成修改和测试。
2. 从 Dify 导出最新 DSL。
3. 将其复制为 `current/AI-Ad-QA-current.yml`。
4. 同时复制到 `archive/AI-Ad-QA-v<版本>-<日期>.yml`。
5. 检查 DSL 不包含 API Key、密码或其他凭据。
6. 提交并推送到 GitHub 私有仓库。
7. 个人电脑执行 `git pull`，再在 Dify 中手动导入 current DSL。

> Dify 不会自动监听 GitHub 中的 DSL 变化。Git 更新完成后，仍需在
> Dify 界面中导入新版本。
