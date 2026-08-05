from setuptools import setup, find_packages
setup(
    name="ai-code-reviewer",
    version="1.0.0",
    author="chwsvveuiygbfiw",
    description="AI Code Reviewer — AST静态分析+LLM深度审查的GitHub代码审查机器人",
    url="https://github.com/chwsvveuiygbfiw/ai-code-reviewer",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=["fastapi>=0.110","uvicorn>=0.29","requests>=2.31","loguru>=0.7"],
    classifiers=["License :: OSI Approved :: MIT License","Programming Language :: Python :: 3.10"],
)
