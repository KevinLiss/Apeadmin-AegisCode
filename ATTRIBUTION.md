---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '1aff2dbf-4b35-4876-b254-82e12f0acbf2'
  PropagateID: '1aff2dbf-4b35-4876-b254-82e12f0acbf2'
  ReservedCode1: '93c6a697-ea07-496b-953a-662ef55a37f2'
  ReservedCode2: '93c6a697-ea07-496b-953a-662ef55a37f2'
---

# 项目来源与版权标注

> 本文档是新项目的**强制保留文件**，记录本仓库的代码来源与许可证关系，禁止删除或修改本文件中的来源声明。

## 项目性质

本仓库是一个**全新独立项目**，与下列来源仓库**无 git 历史关联、无远程仓库关联、无分支关联**：

- 本仓库以独立 `git init` 方式初始化，不继承任何来源仓库的提交历史
- 本仓库的远程地址为 `git@github.com:KevinLiss/Apeadmin-AegisCode.git`（新仓库）
- 不从原仓库 pull / push / merge，重构工作全部在新仓库内独立进行

## 代码来源

### 1. 项目底座：ApeAdmin

| 项目 | 信息 |
|---|---|
| 仓库地址 | https://github.com/KevinLiss/ApeAdmin |
| 用途 | 后台管理框架底座（RBAC 权限、插件系统、MCP-SSE 网关、安装向导等基础能力） |
| 许可证 | MIT License |
| 底座版本 | v0.2.0（2026-09 快照） |
| 使用方式 | 整体作为本项目的框架底座，在其插件体系之上开发业务功能 |

**MIT 许可证原文要求**：需在软件的所有副本中包含版权声明与许可声明。ApeAdmin 底座代码的版权声明与 MIT 许可证全文见 [`LICENSE-BASE`](./LICENSE-BASE)。

### 2. 重构对象：AegisCode

| 项目 | 信息 |
|---|---|
| 仓库地址 | https://github.com/KevinLiss/AegisCode |
| 用途 | Agentic Coding 平台的原有实现（Agent 运行时、多 Agent 工作流、工具体系等），本项目对其架构进行重构与优化 |
| 许可证 | 项目为 KevinLiss 自有项目，版权归属原作者，原仓库未附加开源许可证文件 |
| 使用方式 | 仅作为重构参考与功能迁移来源；本项目不直接复制原仓库代码，重构后的代码为本项目独立成果 |

## 重构说明

1. **底座选择**：采用 ApeAdmin（MIT）作为管理后台与插件化底座，替代 AegisCode 原有的独立后台实现
2. **业务重构**：AegisCode 的 Agent 核心能力（长任务执行、多 Agent 工作流、Token 用量统计、工具体系）将以 ApeAdmin 插件形式重新实现
3. **优化方向**：参考业界开源 Agent 项目（Aider、Cline、OpenHands、Continue、Roo Code、Goose、OpenCode、Pi、Gemini CLI、Void）的设计，重点解决：
   - 长任务的稳定性与上下文管理
   - Token 消耗的精细化统计与预算控制
   - AI Agent 运转机制（调度、恢复、并发准入）

## 义务与边界

- 本项目对外分发时，须随附 [`LICENSE-BASE`](./LICENSE-BASE)（ApeAdmin 的 MIT 许可证与版权声明）
- 引用或借鉴其他开源项目代码时，须在本文件"第三方代码引用"章节登记来源、许可证与用途
- 商用许可遵循 MIT 许可证边界：AGPL/GPL 项目只借鉴架构思想，不复制代码

## 第三方代码引用登记

（后续引入第三方代码时在此登记：项目名 / 地址 / 许可证 / 引用文件 / 用途）