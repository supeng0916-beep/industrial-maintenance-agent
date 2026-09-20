import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { AssistantPanel } from './AssistantPanel'
import type { AssistantReply } from './assistantModel'

const base: AssistantReply = {
  status: 'answered',
  answer: '当前温度 64.0℃，数据已过期约16小时。',
  evidence: [
    { evidence_id: 'ev-1', tool: 'get_device_status', data: { points: { temperature_c: 64 } } },
    { evidence_id: 'ev-2', tool: 'search_maintenance_docs', candidates: [
      { evidence_id: 'doc-1', document_id: 'doe-motor-ts11', chunk_id: 'cz', version: 'November 2012', section: 'Page 2', source_pages: ['2'], source_url: 'https://www.energy.gov/x.pdf', original_text: '20 47 86 93 94 95 96 97', context_text: '', applicability: 'General guidance; verify model', product_model: null },
    ] },
  ],
  limitations: ['数据已过期，当前状态未核实', '文档候选不证明适用性'],
  calls: [{ name: 'get_device_status', outcome: 'ok', args_digest: 'ab12', elapsed_seconds: 0.4 }],
  citations: ['ev-1', 'doc-1'],
  checked_at: '2026-09-20T04:00:00+00:00',
}

describe('AssistantPanel 六状态渲染', () => {
  it('空闲态：输入框与提示，无结果区', () => {
    const html = renderToStaticMarkup(<AssistantPanel phase="idle" />)
    expect(html).toContain('问点什么')
    expect(html).not.toContain('data-testid="assistant-result"')
  })

  it('等待态：明确等待提示且禁用提交', () => {
    const html = renderToStaticMarkup(<AssistantPanel phase="loading" />)
    expect(html).toContain('正在查询')
    expect(html).toContain('disabled')
  })

  it('结果态：答案+引用可点+候选原文+限制+查询时刻+设备标注', () => {
    const html = renderToStaticMarkup(<AssistantPanel phase="done" reply={base} />)
    expect(html).toContain('64.0')
    expect(html).toContain('href="https://www.energy.gov/x.pdf"')
    expect(html).toContain('20 47 86 93 94 95 96 97')
    expect(html).toContain('适用性未核实')
    expect(html).toContain('数据已过期，当前状态未核实')
    expect(html).toContain('查询时刻')
    expect(html).toContain('motor-a')
  })

  it('javascript:链接被拒绝渲染为文本', () => {
    const docEvidence = base.evidence[1]
    const firstCandidate = docEvidence?.candidates?.[0]
    if (!docEvidence || !firstCandidate) throw new Error('fixture missing')
    const evil = { ...base, evidence: [{ ...docEvidence, candidates: [{ ...firstCandidate, source_url: 'javascript:alert(1)' }] }] }
    const html = renderToStaticMarkup(<AssistantPanel phase="done" reply={evil} />)
    expect(html).not.toContain('href="javascript')
    expect(html).toContain('doe-motor-ts11')
  })

  it('失败态：区分模型未配置/忙/网络/无效问题，均不显示设备离线', () => {
    const unconfigured = renderToStaticMarkup(<AssistantPanel phase="failed" error={{ kind: 'http', code: 'assistant_unavailable', message: '助手服务未配置' }} />)
    expect(unconfigured).toContain('模型未配置')
    expect(unconfigured).not.toContain('设备离线')
    const busy = renderToStaticMarkup(<AssistantPanel phase="failed" error={{ kind: 'busy', message: '忙' }} />)
    expect(busy).toContain('稍后重试')
    const network = renderToStaticMarkup(<AssistantPanel phase="failed" error={{ kind: 'network', message: '网络错误' }} />)
    expect(network).toContain('后端服务')
    const invalid = renderToStaticMarkup(<AssistantPanel phase="failed" error={{ kind: 'http', code: 'invalid_parameters', message: '参数不合法' }} />)
    expect(invalid).toContain('问题过长或为空')
  })

  it('业务状态语义：证据不足/未完成/模型不可用分别呈现', () => {
    const insufficient = renderToStaticMarkup(<AssistantPanel phase="done" reply={{ ...base, status: 'insufficient_evidence', answer: '资料中没有该型号手册' }} />)
    expect(insufficient).toContain('证据不足')
    const incomplete = renderToStaticMarkup(<AssistantPanel phase="done" reply={{ ...base, status: 'incomplete' }} />)
    expect(incomplete).toContain('未完成')
    expect(incomplete).toContain('64.0')
    const unavailable = renderToStaticMarkup(<AssistantPanel phase="done" reply={{ ...base, status: 'unavailable' }} />)
    expect(unavailable).toContain('模型不可用')
  })

  it('无数据不显示0：空证据时说明无证据而非0', () => {
    const empty = renderToStaticMarkup(<AssistantPanel phase="done" reply={{ ...base, evidence: [], citations: [] }} />)
    expect(empty).toContain('本次回答未附带工具证据')
    expect(empty).not.toContain('>0<')
  })
})
