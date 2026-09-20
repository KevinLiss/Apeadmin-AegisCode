---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: 'b45de355-eb8d-439d-b105-43810c79673a'
  PropagateID: 'b45de355-eb8d-439d-b105-43810c79673a'
  ReservedCode1: '2eb991fc-7aee-4f41-b287-189d0c5b0c87'
  ReservedCode2: '2eb991fc-7aee-4f41-b287-189d0c5b0c87'
---

# AegisCode 重构项目（基于 ApeAdmin 底座）

> **新项目说明**：本仓库是全新独立项目，以 [ApeAdmin](https://github.com/KevinLiss/ApeAdmin)（MIT）为管理后台底座，重构 [AegisCode](https://github.com/KevinLiss/AegisCode) Agentic Coding 平台的 Agent 核心能力。与原仓库无 git 关联，来源与许可证标注见 [ATTRIBUTION.md](./ATTRIBUTION.md)。

## 项目定位

面向企业内网的 Agentic Coding 平台，围绕项目工作区持续执行规划、代码修改、命令运行、测试验证、审阅、恢复和交付。本版本基于 ApeAdmin 插件化底座重新构建：

- **底座能力**（继承自 ApeAdmin）：RBAC 权限、插件市场、安装向导、审计日志、MCP-SSE 网关
- **业务能力**（重构自 AegisCode）：可恢复 Agent、自适应长任务、多 Agent 工作流、双工作区、用量统计

## 重构重点（对标业界开源项目优化）

| 方向 | 现存问题 | 参考项目 |
|---|---|---|
| 长任务 | 分段扩展机制的上下文膨胀、恢复稳定性 | OpenHands、Goose、OpenCode |
| Token 统计 | 统计粒度粗（仅按调用记录）、缺实时预算反馈 | OpenCode、Gemini CLI、Cline |
| Agent 运转机制 | 调度/DAG/准入策略复杂度高、可观测性不足 | Aider、Roo Code、Pi、Void |

## 目录结构

```
├── ATTRIBUTION.md        # 来源与许可证标注（强制保留）
├── LICENSE-BASE          # ApeAdmin MIT 许可证副本
├── backend/              # FastAPI 后端（ApeAdmin 底座 + Agent 插件）
├── frontend/             # Vue3 管理后台前端
├── docs/                 # 项目文档
├── deploy/               # 部署配置
└── 运维经验/              # 底座运维经验沉淀
```

## 开发启动

### 后端

```bash
cd backend
python3 -m venv ../.venv
../.venv/bin/pip install -e ".[dev]"
../.venv/bin/python -m src.cli run          # 首次访问 http://127.0.0.1:8000 进入安装向导
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

详细配置见底座 README（原 ApeAdmin 使用文档已移至 [docs/base-README.md](./docs/base-README.md)），数据库、JWT_SECRET 等由安装向导自动处理。

## 来源与致谢

- **ApeAdmin**（MIT）— 项目底座，提供插件化框架、RBAC、MCP 网关
- **AegisCode** — 原有 Agentic Coding 平台实现，本项目重构对象

完整标注与第三方引用登记见 [ATTRIBUTION.md](./ATTRIBUTION.md)。