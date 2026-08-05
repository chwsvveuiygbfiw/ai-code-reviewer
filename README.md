# AI Code Reviewer — 智能代码审查机器人

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **GitHub App + LLM + AST 静态分析 = 自动代码审查**

提交 PR 后自动触发深度代码审查：安全漏洞检测、性能反模式识别、代码风格检查、最佳实践建议。支持 DeepSeek / Claude / GPT 作为审查引擎。

## 为什么需要这个项目？

人工 Code Review 耗时且容易漏检——安全漏洞（SQL 注入、XSS）、性能问题（N+1 查询）、风格不一致。AI-Code-Reviewer 在 PR 提交时自动运行，秒级返回审查意见，作为人工审查的"第一道防线"。

## 功能

| 检查维度 | 检测内容 | 示例 |
|---------|---------|------|
| **安全** | SQL注入、XSS、硬编码密钥、路径遍历 | `cursor.execute(f"SELECT * FROM {table}")` → 警告 |
| **性能** | N+1查询、未使用的import、大对象拷贝 | 循环内拼接SQL → 建议用批量查询 |
| **错误** | 空指针、类型错误、资源泄漏 | `f.open()` 无 `f.close()` → 建议用 `with` |
| **风格** | 命名规范、函数长度、注释质量 | 函数超过50行 → 建议拆分 |
| **最佳实践** | 异常处理、日志规范、测试覆盖 | 裸except → 建议指定异常类型 |

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/yourname/ai-code-reviewer
cd ai-code-reviewer
pip install -r requirements.txt

# 2. 设置环境变量
export DEEPSEEK_API_KEY=sk-xxx
export GITHUB_TOKEN=ghp_xxx
export GITHUB_WEBHOOK_SECRET=mysecret

# 3. 启动
python src/server.py

# 4. 配置 GitHub Webhook → http://your-server:8000/webhook
```

## 工作原理

```
PR opened / new commit
        │
        ▼
  GitHub Webhook
        │
        ▼
  Fetch PR diff (GitHub API)
        │
        ▼
  AST 静态分析 (Python AST / Tree-sitter)
  │ 检测: SQL注入模式、不安全函数调用、资源泄漏
        │
        ▼
  LLM 深度审查 (DeepSeek / Claude)
  │ 分析: 逻辑错误、设计问题、最佳实践偏离
        │
        ▼
  Post review comment on PR
  │ 行级评论 + 总结性评论
```

## 技术栈

- **GitHub API**: 获取 PR diff、发布评论
- **AST 分析**: Python `ast` 模块 + Tree-sitter (多语言)
- **LLM**: DeepSeek V4 Pro (默认) / Claude API (可选)
- **FastAPI**: Webhook 接收服务
- **SQLite**: 审查记录持久化

## License

MIT
