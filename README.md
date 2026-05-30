# PR-Insight

AI 代码评审工具，帮助开发者提升 Pull Request 的 Review 效率与质量。

## 功能特性

- **变更总结** — 自动生成 PR 的目的、影响范围和技术要点
- **风险识别** — 检测安全漏洞、性能问题、并发风险、资源泄漏等
- **Review 建议** — 提供可操作的代码改进方案，附带示例代码
- **风格检查** — 识别反模式、重复代码、魔法数字等问题
- **多模型支持** — Claude、DeepSeek、Mimo 等，统一走 Anthropic 兼容接口
- **多格式输出** — 终端彩色报告、GitHub PR 评论、可分享的 HTML 报告

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

### 2. 分析 PR

```bash
# 基础用法 — 终端输出
pr-insight review https://github.com/owner/repo/pull/123

# 生成 HTML 报告 + 发布 PR 评论
pr-insight review https://github.com/owner/repo/pull/123 -o terminal,html,comment

# 聚焦安全问题，只显示中高风险
pr-insight review https://github.com/owner/repo/pull/123 -f security -r medium

# 使用简写格式
pr-insight review owner/repo#123
```

## 命令参考

### `pr-insight review <PR_URL>`

分析指定 GitHub PR。

| 选项               | 说明                                           | 默认值    |
| ------------------ | ---------------------------------------------- | --------- |
| `-o, --output`     | 输出格式：terminal, html, comment（逗号分隔）  | terminal  |
| `--output-dir`     | HTML 报告保存目录                              | ./reports |
| `-r, --risk-level` | 最低显示风险级别：low / medium / high          | low       |
| `-l, --language`   | 报告语言：zh / en                              | zh        |
| `-f, --focus`      | 分析重点：security / performance / style / all | all       |
| `--no-context`     | 跳过上下文代码获取（更快但分析较浅）           | false     |
| `-v, --verbose`    | 开启详细日志                                   | false     |

### `pr-insight config`

管理配置项。

```bash
pr-insight config set <key> <value>   # 设置配置
pr-insight config show                 # 查看当前配置
```

## 支持的模型

默认为claude，如使用国产模型需配置 `base_url`，符合anthropic接口要求：

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

## 项目结构

```
src/pr_insight/
├── cli.py              # CLI 入口
├── config.py           # 配置管理
├── ai/
│   ├── client.py       # Claude API 客户端（含重试、并行）
│   └── parser.py       # AI 响应 JSON 解析
├── analyzer/
│   ├── chunker.py      # 大 PR 分块处理
│   ├── engine.py       # 分析引擎（调度、合并、去重）
│   ├── prompts.py      # Prompt 模板（中英文）
│   └── strategies.py   # 四类分析策略
├── github/
│   ├── client.py       # GitHub API 封装
│   └── models.py       # 数据模型
├── output/
│   ├── terminal.py     # Rich 终端渲染
│   ├── github_comment.py # PR 评论发布
│   └── html_report.py  # HTML 报告生成
└── templates/
    └── report.html.j2  # HTML 报告模板
```

## 开发

### 运行测试

```bash
uv run pytest tests/ -v

# 实际测试
# 1. Flask #5918 - automatic options as separate route (5 files)
uv run pr-insight review https://github.com/pallets/flask/pull/5918 -o terminal -r medium

# 2. Django #21370 - Changed inline admin button text (7 files)
uv run pr-insight review https://github.com/django/django/pull/21370 -o terminal -r medium

# 3. FastAPI #15554 - Enable Hindi docs translations (8 files)
uv run pr-insight review https://github.com/fastapi/fastapi/pull/15554 -o terminal -r medium

# 4. Ruff #25448 - TimeoutError alias UP041 (7 files)
uv run pr-insight review https://github.com/astral-sh/ruff/pull/25448 -o terminal -r medium

# 5. Ruff #25446 - Preserve slice-bound types (9 files)
uv run pr-insight review https://github.com/astral-sh/ruff/pull/25446 -o terminal -r medium

```
