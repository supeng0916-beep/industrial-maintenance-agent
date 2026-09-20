// 助手聊天API客户端：只发送 message + history，绝不携带工具结果或模型配置。
import { isAssistantErrorBody, parseAssistantReply, type AssistantReplyOrError } from './assistantModel'

export interface HistoryItem { role: 'user' | 'assistant'; content: string }

type FetchLike = (url: string, init?: RequestInit) => Promise<Response>

export async function sendAssistantMessage(
  message: string,
  history: HistoryItem[],
  fetchLike: FetchLike = (url, init) => fetch(url, init),
): Promise<AssistantReplyOrError> {
  let response: Response
  try {
    response = await fetchLike('/api/assistant/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ message, history }),
    })
  } catch (error) {
    // 不透传底层异常细节（可能含内部地址），只给可理解的原因。
    void error
    return { ok: false, error: { kind: 'network', message: '无法连接后端服务，请确认服务已启动' } }
  }
  let body: unknown = null
  try { body = await response.json() } catch { body = null }
  if (!response.ok) {
    if (isAssistantErrorBody(body)) {
      const code = (body as { error: { code: string; message: string } }).error.code
      const message = (body as { error: { message: string } }).error.message
      if (response.status === 503 && code === 'assistant_busy') {
        return { ok: false, error: { kind: 'busy', message: '上一条问题仍在处理中，请稍后重试' } }
      }
      return { ok: false, error: { kind: 'http', code, message } }
    }
    return { ok: false, error: { kind: 'http', code: `http_${response.status}`, message: `服务返回 ${response.status}` } }
  }
  return parseAssistantReply(body)
}
