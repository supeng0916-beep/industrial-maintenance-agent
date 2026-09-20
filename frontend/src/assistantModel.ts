// 助手结果合同（与 assistant/agent_contracts.py 对齐）。只描述类型与解析，
// 不含任何模型配置——浏览器永远接触不到密钥与端点。

export type AssistantStatus = 'answered' | 'insufficient_evidence' | 'unavailable' | 'incomplete'

export interface DocumentCandidate {
  evidence_id: string
  document_id: string
  chunk_id?: string
  version?: string | null
  section?: string | null
  source_pages: string[]
  source_url?: string | null
  original_text: string
  context_text?: string
  applicability?: string | null
  product_model?: string | null
}

export interface AssistantEvidence {
  evidence_id: string
  tool: string
  data?: Record<string, unknown>
  candidates?: DocumentCandidate[]
}

export interface AssistantCall {
  name: string
  args_digest?: string
  outcome: string
  elapsed_seconds?: number | null
}

export interface AssistantReply {
  status: AssistantStatus
  answer: string
  evidence: AssistantEvidence[]
  limitations: string[]
  calls: AssistantCall[]
  citations: string[]
  checked_at: string
}

export type AssistantReplyOrError =
  | { ok: true; result: AssistantReply }
  | { ok: false; error: AssistantError }

export type AssistantError =
  | { kind: 'network'; message: string }
  | { kind: 'busy'; message: string }
  | { kind: 'contract'; message: string }
  | { kind: 'http'; code: string; message: string }

const STATUSES: AssistantStatus[] = ['answered', 'insufficient_evidence', 'unavailable', 'incomplete']

export function assistantStatusLabel(status: AssistantStatus): string {
  switch (status) {
    case 'answered': return '已回答'
    case 'insufficient_evidence': return '证据不足'
    case 'incomplete': return '未完成'
    case 'unavailable': return '模型不可用'
  }
}

export function isAssistantErrorBody(body: unknown): boolean {
  if (body === null || typeof body !== 'object') return false
  const error = (body as { error?: unknown }).error
  return error !== null && typeof error === 'object'
    && typeof (error as { code?: unknown }).code === 'string'
}

export function parseAssistantReply(body: unknown): AssistantReplyOrError {
  if (body === null || typeof body !== 'object') return { ok: false, error: { kind: 'contract', message: '响应不是有效对象' } }
  const candidate = body as Partial<AssistantReply>
  const valid = STATUSES.includes(candidate.status as AssistantStatus)
    && typeof candidate.answer === 'string'
    && Array.isArray(candidate.evidence)
    && Array.isArray(candidate.limitations)
    && Array.isArray(candidate.calls)
    && Array.isArray(candidate.citations)
    && typeof candidate.checked_at === 'string'
  if (!valid) return { ok: false, error: { kind: 'contract', message: '响应缺少必填字段' } }
  return { ok: true, result: candidate as AssistantReply }
}
