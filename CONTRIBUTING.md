# 贡献指南 (Contributing)

感谢考虑为本项目做贡献。

## 开发环境

```bash
git clone <repo>
cd 合约交易系统
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 代码规范

- 使用 **Python 3.10+**。
- 公共模块与类建议添加 **docstring**（中文或英文均可）。
- 敏感逻辑处避免使用裸 `except:`，请指定异常类型或使用 `logging` 记录。
- 新功能建议补充 **单元测试**（`tests/`）。

## 提交与 PR

- 提交前可在项目根目录运行：`pytest tests/`、`flake8 src/`（若已配置）。
- PR 请描述变更目的与影响范围，并确保不包含 `.env`、密钥或本地路径等敏感信息。

## 文档

- 新模块或重要 API 请在 `docs/` 下补充说明，或在 README 中链接到现有文档。
