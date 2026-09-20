import { describe, expect, it, vi } from 'vitest'
import { sendAssistantMessage } from './assistantClient'
import type { AssistantError } from './assistantModel'

const answered = {
  status: 'answered' as const,
  answer: 'ok',
  evidence: [],
  limitations: [],
  calls: [],
  citations: [],
  checked_at: '2026-09-20T04:00:00+00:00',
}

function okResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
}
function errorResponse(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: code } }), { status, headers: { 'content-type': 'application/json' } })
}

describe('assistantClient 请求与失败语义', () => {
  it('发送严格负载：message+history，不带任何工具结果/模型配置', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse(answered))
    const reply = await sendAssistantMessage('现在温度多少？', [{ role: 'user', content: '你好' }], fetchMock)
    expect(reply.ok).toBe(true)
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toBe('/api/assistant/chat')
    const payload = JSON.parse(init.body as string)
    expect(payload).toEqual({ message: '现在温度多少？', history: [{ role: 'user', content: '你好' }] })
    expect(Object.keys(payload)).toEqual(['message', 'history'])
  })

  it('422/503转为明确失败；不把业务结果伪装成异常', async () => {
    const invalid = await sendAssistantMessage('x', [], vi.fn().mockResolvedValue(errorResponse(422, 'invalid_parameters')))
    expect(invalid.ok).toBe(false)
    if (invalid.ok === false) {
      const failure: AssistantError = invalid.error
      if (failure.kind === 'http') expect(failure.code).toBe('invalid_parameters')
      else throw new Error('expected http error')
    }
    const unconfigured = await sendAssistantMessage('x', [], vi.fn().mockResolvedValue(errorResponse(503, 'assistant_unavailable')))
    expect(unconfigured.ok).toBe(false)
    if (unconfigured.ok === false) expect((unconfigured.error as Extract<AssistantError, { kind: 'http' }>).code).toBe('assistant_unavailable')
    const busy = await sendAssistantMessage('x', [], vi.fn().mockResolvedValue(errorResponse(503, 'assistant_busy')))
    expect(busy.ok).toBe(false)
    if (busy.ok === false) expect(busy.error.kind).toBe('busy')
    const contract = await sendAssistantMessage('x', [], vi.fn().mockResolvedValue(okResponse({ nonsense: true })))
    expect(contract.ok).toBe(false)
    if (contract.ok === false) expect(contract.error.kind).toBe('contract')
  })

  it('网络异常与超时给出可理解原因，不暴露堆栈', async () => {
    const down = await sendAssistantMessage('x', [], vi.fn().mockRejectedValue(new TypeError('fetch failed at http://127.0.0.1:9999')))
    expect(down.ok).toBe(false)
    if (down.ok === false) {
      expect(down.error.kind).toBe('network')
      expect(down.error.message).not.toContain('127.0.0.1:9999')
    }
  })
})
