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
  listFiles: (projectId: number, path = '.') =>
    request.get(`/aegis-workspace/projects/${projectId}/files`, { params: { path } }),
  readFile: (projectId: number, path: string) =>
    request.get(`/aegis-workspace/projects/${projectId}/files/read`, { params: { path } }),
  writeFile: (projectId: number, path: string, content: string) =>
    request.post(`/aegis-workspace/projects/${projectId}/files/write`, { path, content }),
  executeCommand: (projectId: number, command: string, cwd = '.', timeout = 60) =>
    request.post(`/aegis-workspace/projects/${projectId}/execute`, { command, cwd, timeout }),
  listSnapshots: (projectId: number) =>
    request.get(`/aegis-workspace/projects/${projectId}/snapshots`),
  reviewSnapshot: (projectId: number, snapshotId: number, data: { review_status: string; review_comment?: string }) =>
    request.post(`/aegis-workspace/projects/${projectId}/snapshots/${snapshotId}/review`, data),
}

// ── Agent 运行 ──
export const agentApi = {
  createRun: (data: {
    workspace_id?: number
    provider_id?: number
    model_name?: string
    max_tokens?: number
    max_steps?: number
    workflow_type?: string
    system_prompt?: string
  }) => request.post('/aegis-agent/runs', data),

  listRuns: (params?: { page?: number; page_size?: number; status?: string }) =>
    request.get('/aegis-agent/runs', { params }),

  getRun: (runId: number) => request.get(`/aegis-agent/runs/${runId}`),

  deleteRun: (runId: number) => request.delete(`/aegis-agent/runs/${runId}`),

  /** 发送消息 — stream=true 返回 fetch Response（SSE），stream=false 返回结果 */
  sendMessage: (runId: number, content: string, stream = true): Promise<Response> | Promise<any> => {
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
      }) as Promise<Response>
    }
    return request.post(`/aegis-agent/runs/${runId}/message`, { content, stream: false })
  },

  controlRun: (runId: number, action: 'pause' | 'resume' | 'cancel') =>
    request.post(`/aegis-agent/runs/${runId}/control`, { action }),

  getRunStatus: (runId: number) => request.get(`/aegis-agent/runs/${runId}/status`),

  listSteps: (runId: number) => request.get(`/aegis-agent/runs/${runId}/steps`),

  listMessages: (runId: number) => request.get(`/aegis-agent/runs/${runId}/messages`),

  listCheckpoints: (runId: number) => request.get(`/aegis-agent/runs/${runId}/checkpoints`),

  getUsageSummary: (params?: { run_id?: number }) =>
    request.get('/aegis-agent/usage/summary', { params }),
}

// ── AI Provider（复用底座） ──
export const providerApi = {
  listProviders: () => request.get('/ai-providers'),
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
