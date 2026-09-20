import { describe, expect, it } from 'vitest'
import { assistantStatusLabel, isAssistantErrorBody, parseAssistantReply } from './assistantModel'

const answered = {
  status: 'answered',
  answer: '当前温度 64.0℃',
  evidence: [{ evidence_id: 'ev-1', tool: 'get_device_status', data: { points: { temperature_c: 64 } } }],
  limitations: ['数据已过期'],
  calls: [{ name: 'get_device_status', outcome: 'ok', args_digest: 'ab', elapsed_seconds: 0.4 }],
  citations: ['ev-1'],
  checked_at: '2026-09-20T04:00:00+00:00',
}

describe('assistantModel 合同解析', () => {
  it('完整结果透传：状态/答案/证据/引用/限制/时间', () => {
    const reply = parseAssistantReply(answered)
    expect(reply.ok).toBe(true)
    if (!reply.ok) return
    expect(reply.result.status).toBe('answered')
    expect(reply.result.answer).toContain('64.0')
    expect(reply.result.evidence[0].evidence_id).toBe('ev-1')
    expect(reply.result.citations).toEqual(['ev-1'])
    expect(reply.result.checked_at).toBe('2026-09-20T04:00:00+00:00')
    expect(assistantStatusLabel('answered')).toBe('已回答')
    expect(assistantStatusLabel('insufficient_evidence')).toBe('证据不足')
    expect(assistantStatusLabel('incomplete')).toBe('未完成')
    expect(assistantStatusLabel('unavailable')).toBe('模型不可用')
  })

  it('文档证据候选完整保留：标识/文档/页/原文/适用性', () => {
    const doc = { ...answered, evidence: [{ evidence_id: 'ev-1', tool: 'search_maintenance_docs', candidates: [{ evidence_id: 'doc-1', document_id: 'doe-motor-ts11', chunk_id: 'cz', version: 'November 2012', section: 'Page 2', source_pages: ['2'], source_url: 'https://www.energy.gov/x.pdf', original_text: '20 47 86 93 94 95 96 97', context_text: '', applicability: 'General guidance', product_model: null }] }] }
    const reply = parseAssistantReply(doc)
    if (!reply.ok) throw new Error('should parse')
    const candidate = reply.result.evidence[0]?.candidates?.[0]
    if (!candidate) throw new Error('candidate missing')
    expect(candidate.evidence_id).toBe('doc-1')
    expect(candidate.document_id).toBe('doe-motor-ts11')
    expect(candidate.source_pages).toEqual(['2'])
    expect(candidate.original_text).toContain('86')
    expect(candidate.product_model).toBe(null)
  })

  it('缺失必填字段判为无效结果而非崩溃', () => {
    for (const bad of [{}, { status: 'answered' }, { ...answered, status: 'weird' }]) {
      const reply = parseAssistantReply(bad)
      expect(reply.ok).toBe(false)
      if (reply.ok === false) expect(['contract']).toContain(reply.error.kind)
    }
  })

  it('503错误体识别：模型未配置/忙是两种不同的失败', () => {
    expect(isAssistantErrorBody({ error: { code: 'assistant_unavailable', message: 'x' } })).toBe(true)
    expect(isAssistantErrorBody({ error: { code: 'assistant_busy', message: 'x' } })).toBe(true)
    expect(isAssistantErrorBody({ error: { code: 'invalid_parameters', message: 'x' } })).toBe(true)
    expect(isAssistantErrorBody(answered)).toBe(false)
    expect(isAssistantErrorBody(null)).toBe(false)
    expect(isAssistantErrorBody({ error: { message: 'no code' } })).toBe(false)
  })
})
