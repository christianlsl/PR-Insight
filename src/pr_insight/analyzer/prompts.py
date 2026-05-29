"""Prompt templates for AI code review analysis."""

from __future__ import annotations

from typing import Any

# ── System prompts ──────────────────────────────────────────────────────────

SYSTEM_BASE = """You are a senior code reviewer with deep expertise in software engineering,
security, performance, and best practices. You are thorough but practical —
you focus on real issues, not style nitpicks.

Rules:
- Always respond in the JSON format specified in each task.
- Be specific: reference file paths and line numbers.
- Distinguish between "confirmed issue" (high confidence) and "potential concern" (lower confidence).
- Do NOT report:
  - Minor style preferences (indentation, quote style, trailing commas)
  - Framework conventions that are standard practice
  - Test code mock/stub behavior
  - Documentation typo or formatting issues
- Focus on actionable findings that help the developer improve the code."""

SYSTEM_ZH = """你是一位资深代码审查专家，精通软件工程、安全、性能和最佳实践。你严谨但务实——关注真正的问题，而不是风格上的吹毛求疵。

规则：
- 严格按照每个任务指定的 JSON 格式回复。
- 具体明确：引用文件路径和行号。
- 区分"确定性问题"（高置信度）和"潜在风险"（较低置信度）。
- 不要报告以下内容：
  - 代码风格偏好差异（缩进、引号风格、尾逗号）
  - 框架约定（标准实践）
  - 测试代码中的 mock/stub 行为
  - 注释/文档中的小问题
- 聚焦于可操作的发现，帮助开发者改进代码。"""


def get_system_prompt(language: str = "zh") -> str:
    return SYSTEM_ZH if language == "zh" else SYSTEM_BASE


# ── Strategy prompts ────────────────────────────────────────────────────────

def build_summary_prompt(pr_info_text: str, diff_text: str, language: str = "zh") -> str:
    if language == "zh":
        return f"""请分析以下 Pull Request 的代码变更，生成结构化总结。

## PR 信息
{pr_info_text}

## 代码变更
{diff_text}

请以 JSON 格式返回：
{{
    "purpose": "这个 PR 的目的（一句话）",
    "impact": "影响范围（涉及的模块/功能）",
    "tech_details": "技术实现要点",
    "risk_areas": ["可能需要关注的风险区域"]
}}"""
    return f"""Analyze the following Pull Request changes and generate a structured summary.

## PR Info
{pr_info_text}

## Code Changes
{diff_text}

Return JSON:
{{
    "purpose": "One-line description of what this PR does",
    "impact": "Affected modules/features",
    "tech_details": "Key technical implementation details",
    "risk_areas": ["Areas that may need attention"]
}}"""


def build_risk_prompt(
    pr_info_text: str,
    file_changes_text: str,
    language: str = "zh",
    focus: str = "all",
) -> str:
    focus_instruction = ""
    if focus != "all":
        focus_map = {
            "security": "Focus on security vulnerabilities (injection, auth bypass, data exposure, etc.)",
            "performance": "Focus on performance issues (N+1 queries, memory leaks, inefficient algorithms)",
            "style": "Focus on code quality (anti-patterns, code smells, maintainability)",
        }
        focus_instruction = focus_map.get(focus, "")

    if language == "zh":
        return f"""请分析以下代码变更，识别潜在风险和问题。

## PR 信息
{pr_info_text}

## 代码变更
{file_changes_text}

{focus_instruction}

关注以下风险类型：
- 安全漏洞（注入、权限绕过、敏感数据泄露）
- 性能问题（N+1 查询、内存泄漏、低效算法）
- 并发问题（竞态条件、死锁）
- 资源泄漏（未关闭的连接、文件句柄）
- 错误处理缺失（未捕获异常、空指针）
- 逻辑错误（边界条件、类型错误）

请以 JSON 格式返回：
{{
    "risks": [
        {{
            "file": "文件路径",
            "line": "行号或行号范围",
            "severity": "high/medium/low",
            "confidence": "high/medium/low",
            "type": "security/performance/concurrency/resource/logic/error_handling",
            "description": "问题描述",
            "suggestion": "修复建议"
        }}
    ]
}}"""
    return f"""Analyze the following code changes and identify potential risks.

## PR Info
{pr_info_text}

## Code Changes
{file_changes_text}

{focus_instruction}

Focus on:
- Security vulnerabilities (injection, auth bypass, data exposure)
- Performance issues (N+1 queries, memory leaks, inefficient algorithms)
- Concurrency issues (race conditions, deadlocks)
- Resource leaks (unclosed connections, file handles)
- Missing error handling (uncaught exceptions, null pointers)
- Logic errors (boundary conditions, type errors)

Return JSON:
{{
    "risks": [
        {{
            "file": "file path",
            "line": "line number or range",
            "severity": "high/medium/low",
            "confidence": "high/medium/low",
            "type": "security/performance/concurrency/resource/logic/error_handling",
            "description": "Issue description",
            "suggestion": "Fix suggestion"
        }}
    ]
}}"""


def build_review_prompt(
    pr_info_text: str,
    file_changes_text: str,
    language: str = "zh",
) -> str:
    if language == "zh":
        return f"""请对以下代码变更进行审查，提供改进建议。

## PR 信息
{pr_info_text}

## 代码变更
{file_changes_text}

请关注：
- 代码可读性和命名规范
- 设计模式和架构合理性
- 测试覆盖建议
- API 设计和接口合理性

请以 JSON 格式返回：
{{
    "suggestions": [
        {{
            "file": "文件路径",
            "line": "行号或行号范围",
            "category": "readability/design/testing/api/naming",
            "priority": "high/medium/low",
            "description": "问题描述",
            "improvement": "改进建议",
            "example": "改进示例代码（可选）"
        }}
    ]
}}"""
    return f"""Review the following code changes and provide improvement suggestions.

## PR Info
{pr_info_text}

## Code Changes
{file_changes_text}

Focus on:
- Code readability and naming conventions
- Design patterns and architecture
- Test coverage suggestions
- API design and interface quality

Return JSON:
{{
    "suggestions": [
        {{
            "file": "file path",
            "line": "line number or range",
            "category": "readability/design/testing/api/naming",
            "priority": "high/medium/low",
            "description": "Issue description",
            "improvement": "Improvement suggestion",
            "example": "Improved code example (optional)"
        }}
    ]
}}"""


def build_style_prompt(
    diff_text: str,
    language: str = "zh",
) -> str:
    if language == "zh":
        return f"""请检查以下代码变更中的反模式和代码质量问题。

## 代码变更
{diff_text}

请关注：
- 常见反模式
- 重复代码
- 过长函数（超过 50 行）
- 魔法数字（硬编码常量）
- 过度复杂的条件逻辑

请以 JSON 格式返回：
{{
    "issues": [
        {{
            "file": "文件路径",
            "line": "行号或行号范围",
            "type": "anti_pattern/long_function/magic_number/complexity/duplication",
            "description": "问题描述",
            "suggestion": "改进建议"
        }}
    ]
}}"""
    return f"""Check the following code changes for anti-patterns and code quality issues.

## Code Changes
{diff_text}

Focus on:
- Common anti-patterns
- Duplicate code
- Overly long functions (50+ lines)
- Magic numbers (hardcoded constants)
- Overly complex conditional logic

Return JSON:
{{
    "issues": [
        {{
            "file": "file path",
            "line": "line number or range",
            "type": "anti_pattern/long_function/magic_number/complexity/duplication",
            "description": "Issue description",
            "suggestion": "Improvement suggestion"
        }}
    ]
}}"""
