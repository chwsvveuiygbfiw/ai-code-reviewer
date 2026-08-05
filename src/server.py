"""
AI Code Reviewer — FastAPI server receiving GitHub webhooks.

Flow: Webhook → Fetch PR diff → AST analysis + LLM review → Post comment
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException, Request
from loguru import logger

app = FastAPI(title="AI Code Reviewer", version="1.0.0")

# ============================================================
# Config
# ============================================================

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
LLM_BASE = os.environ.get("LLM_BASE", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-pro")

# ============================================================
# AST Static Analysis Rules
# ============================================================

SECURITY_PATTERNS = [
    (r"os\.system\(.*\+", "命令注入风险: 使用字符串拼接构造系统命令"),
    (r"subprocess\.(call|run|Popen)\(.*shell\s*=\s*True", "Shell注入风险: shell=True"),
    (r"exec\(.*\+", "代码注入风险: exec()接受动态拼接的字符串"),
    (r"eval\(.*\+", "代码注入风险: eval()接受动态拼接的字符串"),
    (r"pickle\.(loads|load)\(.*user", "反序列化风险: pickle反序列化用户输入"),
    (r"\.execute\(.*f[\"']", "SQL注入风险: f-string拼接SQL查询"),
    (r"\.execute\(.*%s", "SQL注入风险: %s 格式化拼接SQL"),
    (r"\.execute\(.*\.format\(", "SQL注入风险: .format()拼接SQL"),
    (r"password\s*=\s*[\"'][^\"']{1,20}[\"']", "硬编码密码: 疑似明文密码"),
    (r"api_key\s*=\s*[\"'][^\"']{5,}[\"']", "硬编码密钥: 疑似API Key硬编码"),
    (r"open\(.*['\"].*w[\"'].*\)(?!.*with)", "资源泄漏: 未使用with语句的文件写入"),
]

PERFORMANCE_PATTERNS = [
    (r"for\s+\w+\s+in\s+range.*:\s*\n\s*.*\.execute\(", "N+1查询: 循环内执行数据库查询"),
    (r"\.append\(.*\+\s*['\"]", "字符串拼接: 建议用参数化查询"),
    (r"import\s+\w+\s*$.*(?!.*used)", "未使用的导入"),
]

ERROR_PATTERNS = [
    (r"except\s*:", "裸except: 应指定具体异常类型"),
    (r"except\s+Exception\s*:\s*\n\s*pass", "吞噬异常: 异常被静默忽略"),
    (r"return\s+None\s*$", "返回None: 考虑抛出明确异常"),
]


# ============================================================
# GitHub API
# ============================================================

def get_pr_diff(owner: str, repo: str, pr_number: int) -> str:
    """Fetch PR diff from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}",
               "Accept": "application/vnd.github.v3.diff"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.text


def post_review(owner: str, repo: str, pr_number: int, comments: List[dict], summary: str):
    """Post review comments on PR."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    body = {
        "body": summary,
        "event": "COMMENT",  # "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
        "comments": [
            {
                "path": c["file"],
                "position": c.get("line", 1),
                "body": c["message"],
            }
            for c in comments[:20]  # GitHub limits
        ],
    }
    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()


# ============================================================
# AST + Pattern Analysis
# ============================================================

def analyze_diff_static(diff: str) -> List[dict]:
    """Run AST and regex pattern analysis on PR diff."""
    findings = []

    # Extract changed lines
    lines = diff.split("\n")
    current_file = ""
    for line_num, line in enumerate(lines):
        if line.startswith("diff --git") or line.startswith("+++ b/"):
            current_file = line.split("/")[-1] if "/" in line else current_file
        if not line.startswith("+"):
            continue
        code = line[1:]  # remove +

        # Run all patterns
        for pattern_list, category in [
            (SECURITY_PATTERNS, "security"),
            (PERFORMANCE_PATTERNS, "performance"),
            (ERROR_PATTERNS, "error"),
        ]:
            for pattern, message in pattern_list:
                if re.search(pattern, code):
                    findings.append({
                        "file": current_file,
                        "line": line_num,
                        "category": category,
                        "message": message,
                        "code_snippet": code[:100],
                    })

    return findings


# ============================================================
# LLM Review
# ============================================================

REVIEW_PROMPT = """你是一名资深代码审查工程师。请审查以下 Pull Request 的代码变更。

## 审查重点
1. **安全漏洞**: SQL注入、XSS、认证绕过、敏感信息泄露
2. **逻辑错误**: 边界条件、空指针、并发问题
3. **性能问题**: 不必要的循环、重复计算、大对象拷贝
4. **最佳实践**: 异常处理、命名规范、测试覆盖

## 代码变更 (diff)
```diff
{diff}
```

## 静态分析发现的问题
{static_findings}

请用以下 JSON 格式输出审查结果:
```json
{{
  "summary": "整体评价 (1-2句)",
  "severity": "critical / warning / info",
  "findings": [
    {{
      "file": "文件名",
      "line": 行号,
      "severity": "critical/warning/info",
      "category": "security/performance/style/logic",
      "message": "问题描述",
      "suggestion": "修改建议"
    }}
  ]
}}
```
"""


def llm_review(diff: str, static_findings: List[dict]) -> Tuple[str, List[dict]]:
    """Use DeepSeek/Claude for deep code review."""
    if not LLM_API_KEY:
        return "LLM not configured, static analysis only.", static_findings

    findings_text = "\n".join(
        f"- [{f['category']}] {f['message']} ({f.get('file', '')}:{f.get('line', '')})"
        for f in static_findings[:10]
    )

    prompt = REVIEW_PROMPT.format(
        diff=diff[:8000],  # Truncate for token limit
        static_findings=findings_text,
    )

    try:
        resp = requests.post(
            f"{LLM_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "你是一名资深代码审查工程师。请用 JSON 格式返回审查结果。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
            },
            timeout=60,
        )

        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*"findings"[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group(0))
                return data.get("summary", "Review complete"), data.get("findings", [])

        return f"LLM returned {resp.status_code}", static_findings

    except Exception as e:
        return f"LLM review failed: {e}", static_findings


# ============================================================
# Webhook Endpoint
# ============================================================

@app.post("/webhook")
async def webhook(request: Request):
    """Receive GitHub webhook and trigger code review."""
    body = await request.body()

    # Verify signature
    if WEBHOOK_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    payload = json.loads(body)

    if event == "ping":
        return {"message": "pong"}

    if event not in ("pull_request", "pull_request_review"):
        return {"message": f"Ignored event: {event}"}

    # Extract PR info
    action = payload.get("action", "")
    if action not in ("opened", "synchronize"):
        return {"message": f"Ignored action: {action}"}

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    owner = repo.get("owner", {}).get("login", "")
    repo_name = repo.get("name", "")
    pr_number = pr.get("number", 0)

    try:
        # Fetch diff
        diff = get_pr_diff(owner, repo_name, pr_number)

        # Static analysis
        static_findings = analyze_diff_static(diff)

        # LLM review
        summary, findings = llm_review(diff, static_findings)

        # Post review
        all_comments = static_findings + findings
        post_review(owner, repo_name, pr_number, all_comments, summary)

        return {
            "status": "ok",
            "pr": f"{owner}/{repo_name}#{pr_number}",
            "findings": len(all_comments),
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Review failed: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok", "llm_configured": bool(LLM_API_KEY)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
