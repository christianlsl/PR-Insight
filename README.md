# PR-Insight

AI 代码评审工具，帮助开发者提升 Pull Request 的 Review 效率与质量。

## 功能特性

- **变更总结** — 自动生成 PR 的目的、影响范围和技术要点
- **风险识别** — 检测安全漏洞、性能问题、并发风险、资源泄漏等
- **Review 建议** — 提供可操作的代码改进方案，附带示例代码
- **风格检查** — 识别反模式、重复代码、魔法数字等问题
- **多模型支持** — Claude、DeepSeek、Mimo 等，统一走 Anthropic 兼容接口
- **多格式输出** — 终端彩色报告、可分享的 HTML 报告、GitHub PR 评论

## 安装

```bash
# 克隆项目
git clone https://github.com/christianlsl/PR-Insight.git
cd PR-Insight

# 使用 uv 安装（推荐）
uv sync --all-extras

# 或使用 pip
pip install -e ".[dev]"
```

## 快速开始

### 1. 配置 API Keys

```bash
# GitHub Token（需要 repo 权限）
pr-insight config set github_token ghp_xxxxxxxxxxxx

# AI API Key
pr-insight config set anthropic_key sk-ant-xxxxxxxxxxxx

# 可选：设置模型和自定义 API 地址
pr-insight config set model mimo-v2.5-pro
pr-insight config set base_url https://token-plan-cn.xiaomimimo.com/anthropic
```

也可以通过环境变量配置：

```bash
export GITHUB_TOKEN=ghp_xxxx
export API_KEY=sk-ant-xxxx
export BASE_URL=https://token-plan-cn.xiaomimimo.com/anthropic
```

或使用交互式向导：

```bash
pr-insight config init
```

### 2. 分析 PR

```bash
# 基础用法 — 终端 + HTML 报告
pr-insight review https://github.com/owner/repo/pull/123

# 生成 HTML 报告 + 发布 PR 评论
pr-insight review https://github.com/owner/repo/pull/123 -o terminal,html,comment

# 聚焦安全问题，只显示中高风险
pr-insight review https://github.com/owner/repo/pull/123 -f security -r medium

# 查看分块计划（不调用 AI）
pr-insight review https://github.com/owner/repo/pull/123 --dry-run

# 使用简写格式
pr-insight review owner/repo#123
```

## 命令参考

### `pr-insight review <PR_URL>`

分析指定 GitHub PR。

| 选项               | 说明                                           | 默认值        |
| ------------------ | ---------------------------------------------- | ------------- |
| `-o, --output`     | 输出格式：terminal, html, comment（逗号分隔）  | terminal,html |
| `--output-dir`     | HTML 报告保存目录                              | ./reports     |
| `-r, --risk-level` | 最低显示风险级别：low / medium / high          | low           |
| `-l, --language`   | 报告语言：zh / en                              | zh            |
| `-f, --focus`      | 分析重点：security / performance / style / all | all           |
| `--no-context`     | 跳过上下文代码获取（更快但分析较浅）           | false         |
| `--dry-run`        | 仅展示分块计划，不执行 AI 分析                 | false         |
| `-v, --verbose`    | 开启详细日志                                   | false         |

### `pr-insight config`

管理配置项。

```bash
pr-insight config init               # 交互式配置向导
pr-insight config set <key> <value>  # 设置配置
pr-insight config unset <key>        # 删除配置项
pr-insight config show               # 查看当前配置
pr-insight config models             # 列出支持的模型
```

## 支持的模型

默认使用 Claude Sonnet。如使用国产模型需配置 `base_url`，符合 Anthropic 接口要求：

```bash
pr-insight config set model mimo
pr-insight config set base_url https://token-plan-cn.xiaomimimo.com/anthropic
```

## 输出示例

### 终端输出

```
╭─────── PR-Insight Review ────────╮
│ PR #42: Fix critical bug         │
│ #42 by dev | fix → main          │
│ 2 files, +20/-10                 │
╰──────────────────────────────────╯

Found: 1 high / 1 medium / 2 total risks | 1 suggestions | 0 style issues

┌─ Summary ────────────────────────┐
│ Purpose: Fix SQL injection bug   │
│ Impact:  core module             │
└──────────────────────────────────┘

┌─ Risks & Issues ─────────────────────────────────────────┐
│ Severity │ File        │ Line │ Description    │ Suggestion│
│ !! HIGH  │ src/main.py │ 10   │ SQL injection  │ Use params│
│ ! MEDIUM │ src/main.py │ 20   │ unused var     │ remove    │
└──────────┴─────────────┴──────┴────────────────┴───────────┘
```

### HTML 报告

生成独立的 HTML 文件，包含统计卡片、分类表格，响应式设计适配桌面和移动端。

### GitHub PR 评论

自动发布 Markdown 格式的审查摘要到 PR 评论区。

## 设计思路

### 模型选择：统一 Anthropic 兼容接口

系统**不直接对接各家 LLM 的原生 API**，而是统一使用 Anthropic Messages API 格式。这是本工具最核心的架构决策。

**为什么这样做？**

- Anthropic SDK 的 `messages.create()` 接口语义清晰（system + messages + max_tokens），且原生支持 extended thinking，适合作为"标准接口"
- DeepSeek、Mimo 等国产模型均提供 Anthropic 兼容端点（`/anthropic` 路径），只需配置 `base_url` 即可切换，无需改动任何代码
- 避免为每家模型写适配层——一个 `AIClient` + 一个 `base_url` 参数覆盖所有场景

**如何切换模型？**

```bash
# 使用 Claude（默认，无需 base_url）
pr-insight config set model claude-sonnet-4-20250514

# 使用 Mimo
pr-insight config set model mimo
pr-insight config set base_url https://token-plan-cn.xiaomimimo.com/anthropic

# 使用 DeepSeek
pr-insight config set model deepseek-chat
pr-insight config set base_url https://api.deepseek.com/anthropic
```

只要模型端点兼容 Anthropic Messages API，就可以接入。未来新增模型只需在 `config.py` 的 `SUPPORTED_MODELS` 中注册即可。

**容错设计**：`AIClient` 内置指数退避重试（最多 3 次）、并发控制（信号量限制为 3 个并行请求）、300 秒超时，以及 extended thinking 场景下的 ThinkingBlock 降级提取。

### 上下文获取：分块 + 上下文注入

PR 的 diff 只展示变更行，缺少周围的代码上下文，AI 难以理解变更的完整语义。系统通过两层机制解决这个问题：

**第一层：智能分块（chunker.py）**

大 PR 无法一次性送入 AI 的上下文窗口，需要分块处理：

| PR 规模 | 策略 |
|---------|------|
| 小型（< 20 文件，< 500 行变更） | 单块，直接分析 |
| 中型（20-100 文件） | 按目录分组，每块最多 15 个文件或 80K 字符 |
| 大型（> 100 文件） | 先生成文件列表摘要块，再按目录分组 |

分块时按目录排序，让同一模块的文件落在同一个 chunk 中，AI 能更好地理解模块内的关联。

**第二层：上下文代码注入（chunker.py:64-91）**

对于每个 diff hunk，系统会通过 GitHub API 获取该文件的完整内容，提取 hunk 前后各 20 行代码作为上下文注入到 diff 中。这样 AI 看到的不仅是 `+` / `-` 行，还有它们所处的函数、类、条件分支等完整语境。

```bash
# 跳过上下文获取（更快，但分析深度降低）
pr-insight review <URL> --no-context

# 查看分块计划
pr-insight review <URL> --dry-run
```

**多块 PR 的摘要先行策略**

当 PR 被分成多个 chunk 时，系统会**先运行 Summary 任务**获取 PR 整体概览，再将摘要作为上下文注入到后续的 Risk / Review / Style 任务中。这确保了每个 chunk 的分析不会只见树木不见森林。

### 分析策略：四维度并行

系统将代码审查拆分为四个独立维度，每个维度对每个 chunk 生成一个 AI 任务：

| 维度 | 关注点 | 输出 |
|------|--------|------|
| Summary | PR 目的、影响范围、技术要点、风险区域 | 结构化摘要 |
| Risk | 安全漏洞、性能问题、并发风险、资源泄漏、逻辑错误 | 严重级别 + 置信度 + 修复建议 |
| Review | 可读性、设计模式、测试覆盖、API 设计 | 改进建议 + 示例代码 |
| Style | 反模式、重复代码、过长函数、魔法数字、复杂条件 | 问题描述 + 改进建议 |

所有任务通过 `asyncio.Semaphore` 控制并发（默认 3 个并行 API 调用），在速度和 API 限流之间取得平衡。结果合并时自动去重（相同文件 + 行号 + 描述）。

Prompt 中明确要求 AI **不报告**琐碎问题（空白变更、import 重排、框架惯例、测试 mock 等），聚焦于真正有价值的发现。

## 项目结构

```
src/pr_insight/
├── cli.py              # CLI 入口（Click + Rich）
├── config.py           # 配置管理（env > file > default）
├── ai/
│   ├── client.py       # AI 客户端（重试、并发、超时、ThinkingBlock 兜底）
│   └── parser.py       # JSON 响应解析（容错提取）
├── analyzer/
│   ├── chunker.py      # PR 分块 + 上下文注入
│   ├── engine.py       # 分析引擎（调度、合并、去重）
│   ├── prompts.py      # Prompt 模板（中英文）
│   └── strategies.py   # 四类分析策略构建
├── github/
│   ├── client.py       # GitHub API 封装（PR 数据 + 文件内容）
│   └── models.py       # 数据模型（PRInfo, FileChange, DiffHunk）
├── output/
│   ├── terminal.py     # Rich 终端渲染
│   ├── html_report.py  # HTML 报告生成（Jinja2）
│   ├── json_report.py  # JSON 报告生成
│   └── github_comment.py # PR 评论发布
└── templates/
    └── report.html.j2  # HTML 报告模板
```

## 未来扩展方向

- **增量审查** — 只分析最新 commit 的变更，避免重复审查已 merge 的代码
- **自定义规则** — 支持用户定义审查规则（如 "禁止使用 `eval`"），作为 Prompt 的附加约束
- **CI/CD 集成** — GitHub Actions 模板，PR 创建时自动触发审查并发布评论
- **多仓库上下文** — 跨仓库引用分析（如 monorepo 中一个包的变更对其他包的影响）
- **审查历史学习** — 基于团队历史 Review 记录调整 Prompt，适应项目特有的编码规范

## 开发

### 运行测试

```bash
uv run pytest tests/ -v

# 实际测试
# 1. Flask #5918 - automatic options as separate route (5 files)
uv run pr-insight review https://github.com/pallets/flask/pull/5918 -r medium

# 2. FastAPI #15617
uv run pr-insight review https://github.com/fastapi/fastapi/pull/15617
```
