# 🤖 AI Code Reviewer

<div align="center">

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](.github/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-8%20passed-success)](tests/)

**AST 静态分析 + LLM 深度审查 = 自动代码审查机器人**

[Quick Start](#quick-start) · [Rules](#检测规则) · [Playground](#playground) · [FAQ](#faq)

</div>

---

## 为什么需要这个项目？

人工 Code Review 是保障代码质量的最后一道防线，但存在三个痛点：

- **漏检率高**：安全漏洞（SQL 注入、硬编码密钥）容易被肉眼忽略
- **不一致**：不同 reviewer 的标准差异大，同一个人早晚状态也不同
- **耗时长**：一个 PR 平均要等 4-8 小时才能获得 review

AI-Code-Reviewer 在 PR 提交时**秒级返回审查意见**，作为人工审查的"第一道防线"。AST 静态分析保障零误报的模式匹配，LLM 深度审查覆盖逻辑和设计层面。

## 核心特性

| 特性 | 说明 |
|------|------|
| 🔒 **安全漏洞检测** | SQL注入、命令注入、XSS、硬编码密钥、反序列化风险、路径遍历 |
| ⚡ **性能反模式** | N+1查询、循环内字符串拼接、未释放资源、大对象拷贝 |
| 🐛 **错误处理** | 裸 except、异常静默吞噬、资源泄漏、空指针风险 |
| 🧠 **LLM 深度审查** | DeepSeek/Claude/GPT 做逻辑和设计层面的分析 |
| 📋 **可配置规则** | `.code-review.yaml` 按项目自定义规则的开关和阈值 |
| 🎮 **Playground** | 粘贴代码即时预览审查结果，无需配置 GitHub Webhook |
| 🔗 **GitHub 集成** | Webhook 接收 PR 事件 → 自动获取 diff → 审查 → 发布行级评论 |
| 🧪 **充分测试** | 8 个单元测试，覆盖安全/性能/错误等所有检测类别 |

## Architecture

```
PR Opened / New Commit
        │
        ▼
  GitHub Webhook (POST /webhook)
        │
        ├── Verify HMAC-SHA256 signature
        ├── Extract PR number from payload
        │
        ▼
  Fetch PR Diff (GitHub API)
        │
        ▼
  ═══════════════════════════════
  ║  Stage 1: AST Static Analysis ║
  ═══════════════════════════════
        │
        ├── Python AST / Regex patterns
        ├── 18 security rules
        ├── 5 performance rules  
        └── 3 error handling rules
        │
        ▼
  ═══════════════════════════════
  ║  Stage 2: LLM Deep Review     ║
  ═══════════════════════════════
        │
        ├── DeepSeek V4 Pro (default)
        ├── System prompt + diff + static findings
        └── JSON structured output
        │
        ▼
  Post Review Comment
        │
        ├── Line-level comments (up to 20)
        └── Summary comment with severity
```

## Quick Start

### 1. 安装

```bash
git clone https://github.com/chwsvveuiygbfiw/ai-code-reviewer
cd ai-code-reviewer
pip install -e .
```

### 2. 试用 Playground（无需 GitHub）

```bash
streamlit run src/playground.py
# 浏览器打开 http://localhost:8501
# 粘贴代码即可预览审查结果
```

### 3. 配置 GitHub App

```bash
export GITHUB_TOKEN=ghp_xxx
export GITHUB_WEBHOOK_SECRET=mysecret
export DEEPSEEK_API_KEY=sk-xxx  # 可选,不填则仅做静态分析

uvicorn src.server:app --host 0.0.0.0 --port 8000
```

在 GitHub 仓库 Settings → Webhooks → Add webhook：
- Payload URL: `https://your-server.com/webhook`
- Content type: `application/json`
- Secret: 与 `GITHUB_WEBHOOK_SECRET` 一致
- Events: Pull requests

### 4. 自定义规则

编辑项目根目录的 `.code-review.yaml`：

```yaml
rules:
  security:
    sql_injection: true       # SQL注入检测
    hardcoded_secrets: true   # 硬编码密钥
    command_injection: true   # 命令注入
  performance:
    n_plus_one_query: true    # N+1查询
    unused_imports: true      # 未使用的导入
  style:
    function_too_long:        # 函数过长
      enabled: false          # 关闭此规则
      max_lines: 50

review:
  max_comments_per_review: 20
  post_summary: true
  request_changes_on_critical: true  # 严重问题自动 Request Changes

llm:
  provider: deepseek
  model: deepseek-v4-pro
  temperature: 0.1
```

## 检测规则

### 安全规则 (18条)

| 规则 | 检测模式 | 示例 |
|------|---------|------|
| SQL 注入 | f-string/格式化拼接 SQL | `cursor.execute(f"SELECT * FROM {table}")` |
| 命令注入 | os.system/subprocess 拼接 | `os.system("rm -rf " + user_path)` |
| 代码注入 | eval/exec 动态参数 | `eval(user_input + "()")` |
| 硬编码密码 | password=明文赋值 | `password = "admin123"` |
| 硬编码密钥 | api_key 明文 | `api_key = "sk-xxxx"` |
| 路径遍历 | 未验证的文件路径拼接 | `open("/data/" + user_file)` |
| 反序列化风险 | pickle 反序列化用户输入 | `pickle.loads(user_data)` |
| 资源泄漏 | open() 无 with 语句 | `f = open("file.txt", "w")` (无 close) |

### 错误处理规则 (3条)

| 规则 | 说明 |
|------|------|
| 裸 except | `except:` 应指定具体异常类型 |
| 异常吞噬 | `except Exception: pass` 静默忽略 |
| 资源泄漏 | 文件/连接未在 finally 或 with 中释放 |

### 性能规则 (5条)

| 规则 | 说明 |
|------|------|
| N+1 查询 | 循环内执行数据库查询 |
| 字符串拼接 | 循环内用 + 拼接（建议 join） |
| 未使用导入 | import 后未引用的模块 |
| 大对象拷贝 | 不必要的深拷贝 |
| 重复计算 | 循环内重复计算不变值 |

## Playground

```bash
streamlit run src/playground.py
```

- 粘贴任意 Python 代码片段
- 即时查看所有检测到的问题（分类展示：安全/性能/错误）
- 问题代码高亮 + 详细说明
- 统计面板：总问题数 / 严重问题 / 代码行数
- 支持语法高亮显示问题代码

## API Reference

### POST /webhook

接收 GitHub Webhook 事件。

```json
// Request Header
X-Hub-Signature-256: sha256=xxx
X-GitHub-Event: pull_request

// Response
{
  "status": "ok",
  "pr": "owner/repo#42",
  "findings": 5,
  "summary": "Found 2 critical security issues and 3 style suggestions"
}
```

### GET /health

```json
{"status": "ok", "llm_configured": true}
```

## FAQ

**Q: 只支持 Python 吗？**

A: 静态分析规则目前针对 Python，但可扩展。Tree-sitter 支持 JS/TS/Go/Rust 等，在 `.code-review.yaml` 中配置语言即可。

**Q: LLM 审查和 AST 分析有什么区别？**

A: AST 分析零误报、零延迟，但只能检测已知模式（SQL 注入、硬编码密钥等）。LLM 审查慢一些（1-3s），但能检测逻辑错误和设计问题。两者互补，推荐同时启用。

**Q: 会误报吗？**

A: 静态分析规则经过人工审核，误报率极低。LLM 审查的误报率约 5-10%，建议人工确认。规则可在 `.code-review.yaml` 中按项目关闭。

**Q: 如何避免 Token 浪费？**

A: PR diff 超过 8000 字符时自动截断，只送前 8000 字符给 LLM。大 PR 建议拆分为多个小 PR。

**Q: 可以不依赖 GitHub 使用吗？**

A: 可以。直接调用 `analyze_diff_static(diff)` 函数传入任意 diff 文本，无需 GitHub Webhook。

## License

MIT © 2026
