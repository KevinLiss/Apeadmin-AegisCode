/**
 * AegisCode 工作台 API
 *
 * 复用底座 request 实例（已处理 token 注入和信封拆包），
 * 调用方直接拿内层 data。
 */
import request from '@/api/request'

// ── 项目 ──
export const workspaceApi = {
  listProjects: (params?: { page?: number; page_size?: number }) =>
    request.get('/aegis-workspace/projects', { params }),
  getProject: (id: number) => request.get(`/aegis-workspace/projects/${id}`),
  createProject: (data: { name: string; description?: string; storage_type?: 'cloud' | 'local'; root_hint?: string; git_enabled?: boolean }) =>
    request.post('/aegis-workspace/projects', data),
  deleteProject: (id: number) => request.delete(`/aegis-workspace/projects/${id}`),
  listFiles: (projectId: number, path = '.', recursive = false) =>
    request.get(`/aegis-workspace/projects/${projectId}/files`, { params: { path, recursive } }),
  readFile: (projectId: number, path: string) =>
    request.get(`/aegis-workspace/projects/${projectId}/files/read`, { params: { path } }),
  writeFile: (projectId: number, path: string, content: string) =>
    request.post(`/aegis-workspace/projects/${projectId}/files/write`, { path, content }),
  uploadFile: (projectId: number, file: File, folder = '用户上传') => {
    const form = new FormData()
    form.append('file', file)
    form.append('folder', folder)
    return request.post(`/aegis-workspace/projects/${projectId}/files/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listFolders: (projectId: number) =>
    request.get(`/aegis-workspace/projects/${projectId}/folders`),
  createFolder: (projectId: number, name: string) =>
    request.post(`/aegis-workspace/projects/${projectId}/folders`, { name }),
  deleteFolder: (projectId: number, name: string) =>
    request.delete(`/aegis-workspace/projects/${projectId}/folders`, { params: { name } }),
  deleteFile: (projectId: number, path: string) =>
    request.delete(`/aegis-workspace/projects/${projectId}/files`, { params: { path } }),
  reorderFolders: (projectId: number, order: string[]) =>
    request.post(`/aegis-workspace/projects/${projectId}/folders/reorder`, { order }),
  executeCommand: (projectId: number, command: string, cwd = '.', timeout = 60) =>
    request.post(`/aegis-workspace/projects/${projectId}/execute`, { command, cwd, timeout }),
  createSnapshot: (projectId: number, data?: { commit_message?: string; run_id?: number; step_index?: number }) =>
    request.post(`/aegis-workspace/projects/${projectId}/snapshot`, data),
  listSnapshots: (projectId: number) =>
    request.get(`/aegis-workspace/projects/${projectId}/snapshots`),
  reviewSnapshot: (projectId: number, snapshotId: number, data: { status: string; comment?: string }) =>
    request.post(`/aegis-workspace/projects/${projectId}/snapshots/${snapshotId}/review`, data),
  rollbackSnapshot: (projectId: number, snapshotId: number) =>
    request.post(`/aegis-workspace/projects/${projectId}/snapshots/${snapshotId}/rollback`),
}

// ── Agent 运行 ──
export const agentApi = {
  createRun: (data: {
    workspace_id?: number
    provider_id?: number
    model_name?: string
    title?: string
    max_tokens?: number
    max_steps?: number
    workflow_type?: string
    system_prompt?: string
  }) => request.post('/aegis-agent/runs', data),

  listRuns: (params?: { page?: number; page_size?: number; status?: string; workspace_id?: number; include_archived?: boolean }) =>
    request.get('/aegis-agent/runs', { params }),

  renameRun: (runId: number, title: string) =>
    request.put(`/aegis-agent/runs/${runId}/title`, { title }),

  pinRun: (runId: number, isPinned: boolean) =>
    request.put(`/aegis-agent/runs/${runId}/pin`, { is_pinned: isPinned }),

  archiveRun: (runId: number, isArchived: boolean) =>
    request.put(`/aegis-agent/runs/${runId}/archive`, { is_archived: isArchived }),

  getRun: (runId: number) => request.get(`/aegis-agent/runs/${runId}`),

  deleteRun: (runId: number) => request.delete(`/aegis-agent/runs/${runId}`),

  /** 发送消息 — stream=true 返回 fetch Response（SSE），stream=false 返回结果 */
  sendMessage: (runId: number, content: string | any[], stream = true, signal?: AbortSignal): Promise<Response> | Promise<any> => {
    if (stream) {
      // SSE 用原生 fetch（axios 不支持流式）
      const token = localStorage.getItem('apeadmin_token') || ''
      return fetch(`/api/v1/aegis-agent/runs/${runId}/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content, stream: true }),
        signal,
      }) as Promise<Response>
    }
    return request.post(`/aegis-agent/runs/${runId}/message`, { content, stream: false })
  },

  controlRun: (runId: number, action: 'pause' | 'resume' | 'cancel') =>
    request.post(`/aegis-agent/runs/${runId}/control`, { action }),

  /** 批准/拒绝运行中待审批的高危命令 */
  approveCommand: (runId: number, decision: boolean) =>
    request.post(`/aegis-agent/runs/${runId}/approve`, null, { params: { decision } }),

  /** 从检查点恢复运行 */
  restoreRun: (runId: number) =>
    request.post(`/aegis-agent/runs/${runId}/restore`),

  getRunStatus: (runId: number) => request.get(`/aegis-agent/runs/${runId}/status`),

  listSteps: (runId: number) => request.get(`/aegis-agent/runs/${runId}/steps`),

  listMessages: (runId: number) => request.get(`/aegis-agent/runs/${runId}/messages`),

  listCheckpoints: (runId: number) => request.get(`/aegis-agent/runs/${runId}/checkpoints`),

  getUsageSummary: (params?: { run_id?: number }) =>
    request.get('/aegis-agent/usage/summary', { params }),
}

// ── 项目统计（右侧项目管理面板） ──
export const projectApi = {
  getStats: (projectId: number) =>
    request.get(`/aegis-workspace/projects/${projectId}/stats`),
}

// ── 项目成员 ──
export const memberApi = {
  listMembers: (projectId: number) =>
    request.get(`/aegis-workspace/projects/${projectId}/members`),
  addMember: (projectId: number, data: { user_id: number; role?: string; permissions?: string[] }) =>
    request.post(`/aegis-workspace/projects/${projectId}/members`, data),
  updateMember: (projectId: number, userId: number, data: { role?: string; permissions?: string[] }) =>
    request.put(`/aegis-workspace/projects/${projectId}/members/${userId}`, data),
  removeMember: (projectId: number, userId: number) =>
    request.delete(`/aegis-workspace/projects/${projectId}/members/${userId}`),
  listCandidates: (projectId: number, params?: { keyword?: string; limit?: number }) =>
    request.get(`/aegis-workspace/projects/${projectId}/members/candidates`, { params }),
}

// ── AI Provider（复用底座） ──
export const providerApi = {
  listProviders: () => request.get('/ai/providers'),
}

// ── 预算策略 ──
export const budgetApi = {
  listPolicies: (params?: { page?: number; page_size?: number; is_active?: boolean }) =>
    request.get('/aegis-budget/policies', { params }),
  createPolicy: (data: any) => request.post('/aegis-budget/policies', data),
  updatePolicy: (id: number, data: any) => request.put(`/aegis-budget/policies/${id}`, data),
  deletePolicy: (id: number) => request.delete(`/aegis-budget/policies/${id}`),
  matchPolicy: (params: { model_name?: string; user_id?: number; task_type?: string }) =>
    request.get('/aegis-budget/policies/match', { params }),
}

// ── 技能中心 ──
export const skillApi = {
  listSkills: (params?: any) => request.get('/aegis-skill/skills', { params }),
  createSkill: (data: any) => request.post('/aegis-skill/skills', data),
  updateSkill: (id: number, data: any) => request.put(`/aegis-skill/skills/${id}`, data),
  deleteSkill: (id: number) => request.delete(`/aegis-skill/skills/${id}`),
  listTools: (params?: any) => request.get('/aegis-skill/tools', { params }),
  createTool: (data: any) => request.post('/aegis-skill/tools', data),
  updateTool: (id: number, data: any) => request.put(`/aegis-skill/tools/${id}`, data),
  deleteTool: (id: number) => request.delete(`/aegis-skill/tools/${id}`),
}

// ── MCP 服务器 ──
export const mcpApi = {
  listServers: (params?: any) => request.get('/aegis-mcp/servers', { params }),
  createServer: (data: any) => request.post('/aegis-mcp/servers', data),
  updateServer: (id: number, data: any) => request.put(`/aegis-mcp/servers/${id}`, data),
  deleteServer: (id: number) => request.delete(`/aegis-mcp/servers/${id}`),
  testServer: (id: number) => request.post(`/aegis-mcp/servers/${id}/test`),
}
