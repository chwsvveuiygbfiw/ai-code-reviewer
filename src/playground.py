"""
AI Code Reviewer — Streamlit Testing Interface

Paste any code snippet to see what the reviewer would flag.
Run: streamlit run src/playground.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from server import analyze_diff_static

st.set_page_config(page_title="Code Reviewer", page_icon="🤖", layout="wide")
st.title("🤖 AI Code Reviewer — Playground")
st.caption("粘贴代码片段,预览 AI 会标记哪些问题")

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("📝 输入代码")
    code = st.text_area(
        "粘贴需要审查的代码",
        height=300,
        placeholder="# 粘贴你的代码...\ncursor.execute(f\"SELECT * FROM users WHERE id={user_input}\")\npassword = \"admin123\"\nexcept:\n    pass",
    )
    language = st.selectbox("语言", ["python", "javascript", "go", "typescript"])
    review_btn = st.button("🔍 审查代码", type="primary", use_container_width=True)

with col2:
    st.subheader("🔍 审查结果")
    if review_btn and code.strip():
        # Convert code to diff format
        diff_lines = [f"+{line}" for line in code.strip().split("\n")]
        diff = "\n".join(diff_lines)

        findings = analyze_diff_static(diff)

        if not findings:
            st.success("✅ 未发现明显问题")

        else:
            # Group by severity
            by_cat = {}
            for f in findings:
                by_cat.setdefault(f["category"], []).append(f)

            for cat, items in by_cat.items():
                emoji = {"security": "🔴", "performance": "🟡", "error": "🟠", "style": "🔵"}.get(cat, "⚪")
                with st.expander(f"{emoji} {cat.upper()} ({len(items)} issues)", expanded=cat=="security"):
                    for item in items:
                        st.markdown(f"**{item['message']}**")
                        st.code(item.get("code_snippet", "")[:120], language=language)
                        st.markdown("---")

        # Stats
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("总问题数", len(findings))
        col_b.metric("严重问题", sum(1 for f in findings if f["category"] == "security"))
        col_c.metric("代码行数", len(code.strip().split("\n")))

    elif not review_btn:
        st.info("👆 输入代码后点击审查按钮")

st.sidebar.markdown("### 📋 审查规则 (已启用)")
rules = [
    "SQL注入检测", "命令注入检测", "硬编码密码/密钥",
    "eval/exec 动态执行", "资源泄漏(文件未关闭)",
    "裸 except 语句", "异常静默吞噬", "N+1 查询模式"
]
for r in rules:
    st.sidebar.markdown(f"- {r}")

st.sidebar.markdown("---")
st.sidebar.caption("AI Code Reviewer v1.0.0")
