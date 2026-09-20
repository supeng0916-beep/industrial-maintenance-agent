// 助手问答面板：输入/等待/结果/引用/限制/失败六状态。
// 模型文本按纯文本渲染；引用URL仅允许http/https。
import { useState } from 'react'
import { sendAssistantMessage, type HistoryItem } from './assistantClient'
import { assistantStatusLabel, type AssistantError, type AssistantReply } from './assistantModel'

export type AssistantPhase = 'idle' | 'loading' | 'done' | 'failed'

const STATUS_HINT: Record<string, string> = {
  answered: '回答基于下列工具证据',
  insufficient_evidence: '资料与数据不足以回答该问题',
  incomplete: '回答过程未完成，以下为已取得的部分结果',
  unavailable: '模型暂不可用，稍后重试',
}

function safeUrl(url?: string | null): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.toString() : null
  } catch { return null }
}

function localTime(iso?: string): string {
  if (!iso) return '—'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

function devicesOf(evidence: AssistantReply['evidence']): string[] {
  const devices = new Set<string>()
  for (const entry of evidence) {
    const data = entry.data as { device_id?: string } | undefined
    if (data && typeof data.device_id === 'string') devices.add(data.device_id)
  }
  return [...devices]
}

function ErrorNotice({ error }: { error: AssistantError }) {
  if (error.kind === 'http' && error.code === 'assistant_unavailable') {
    return <p className="assistant-error-detail">模型未配置：请在后端环境设置 ASSISTANT_MODEL 等变量后重启服务。监控功能不受影响。</p>
  }
  if (error.kind === 'http' && error.code === 'invalid_parameters') {
    return <p className="assistant-error-detail">问题过长或为空，请调整后重试。</p>
  }
  if (error.kind === 'busy') return <p className="assistant-error-detail">上一条问题仍在处理中，请稍后重试。</p>
  if (error.kind === 'network') return <p className="assistant-error-detail">无法连接后端服务；请确认后端已启动。这与设备在线状态无关。</p>
  return <p className="assistant-error-detail">{error.message}</p>
}

export function AssistantPanel({ phase, reply, error }: {
  phase: AssistantPhase
  reply?: AssistantReply
  error?: AssistantError
}) {
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [result, setResult] = useState<AssistantReply | undefined>(reply)
  const [failure, setFailure] = useState<AssistantError | undefined>(error)
  const [state, setState] = useState<AssistantPhase>(phase)
  const [lastDevice, setLastDevice] = useState<string>('')

  const disabled = busy || state === 'loading' || !draft.trim()

  async function submit() {
    const message = draft.trim()
    if (!message || busy) return
    setBusy(true)
    setState('loading')
    setFailure(undefined)
    const sent: HistoryItem[] = [...history, { role: 'user' as const, content: message }].slice(-6)
    const replyOrError = await sendAssistantMessage(message, sent.slice(0, -1))
    if (replyOrError.ok) {
      setResult(replyOrError.result)
      setState('done')
      setHistory([...sent, { role: 'assistant' as const, content: replyOrError.result.answer }].slice(-6))
      setLastDevice(devicesOf(replyOrError.result.evidence).join('、'))
    } else {
      setFailure(replyOrError.error)
      setState('failed')
    }
    setDraft('')
    setBusy(false)
  }

  return <section className="assistant-panel" aria-label="维护助手问答">
    <div className="assistant-heading">
      <h2>维护助手（实验性）</h2>
      <p>回答基于只读工具证据与本地维护资料；文档候选需人工核对，不构成诊断结论。</p>
    </div>
    <div className="assistant-input">
      <label htmlFor="assistant-question">问点什么</label>
      <textarea id="assistant-question" rows={2} maxLength={4000} value={draft}
        placeholder="例如：motor-a 现在温度多少？资料里 20hp 变频器 12.5% 负载的效率是多少？"
        onChange={event => setDraft(event.target.value)} />
      <button type="button" onClick={submit} disabled={disabled}>{state === 'loading' || busy ? '正在查询…' : '提问'}</button>
    </div>
    {state === 'idle' && <p className="assistant-hint">回答会附上证据与限制说明。</p>}
    {(state === 'loading' || busy) && <p className="assistant-loading" data-testid="assistant-loading">正在查询工具与资料，最长约60秒…</p>}
    {state === 'failed' && failure && <div className="assistant-error" data-testid="assistant-error" role="alert">
      <strong>本次提问未能完成</strong><ErrorNotice error={failure} />
    </div>}
    {state === 'done' && result && <div className="assistant-result" data-testid="assistant-result">
      <div className="assistant-status-row">
        <span className={`badge assistant-status ${result.status}`}>{assistantStatusLabel(result.status)}</span>
        <span className="assistant-checked">查询时刻：<time dateTime={result.checked_at}>{localTime(result.checked_at)}</time></span>
        {lastDevice && <span className="assistant-device">涉及设备：{lastDevice}</span>}
      </div>
      <p className="assistant-answer">{result.answer}</p>
      <p className="assistant-status-hint">{STATUS_HINT[result.status]}</p>
      {result.evidence.length === 0
        ? <p className="assistant-no-evidence">本次回答未附带工具证据</p>
        : <details className="assistant-evidence" open>
          <summary>证据与引用（{result.evidence.length} 条）</summary>
          <ol className="assistant-evidence-list">
            {result.evidence.map(entry => <li key={entry.evidence_id}>
              <strong>{entry.evidence_id}</strong> · 工具 {entry.tool}
              {entry.candidates ? entry.candidates.map(candidate => <div key={candidate.evidence_id} className="assistant-candidate">
                <div className="candidate-meta">
                  <span>{candidate.document_id}{candidate.source_pages.length ? ` 第${candidate.source_pages.join('/')}页` : ''}</span>
                  {candidate.version ? <span>版本 {candidate.version}</span> : null}
                  <span className="candidate-applicability">{candidate.product_model ? `型号 ${candidate.product_model}` : '适用性未核实'}</span>
                  {(() => { const url = safeUrl(candidate.source_url); return url ? <a href={url} target="_blank" rel="noreferrer noopener">来源文件</a> : null })()}
                </div>
                <pre className="candidate-text">{candidate.original_text}</pre>
              </div>) : entry.data ? <pre className="assistant-tool-data">{JSON.stringify(entry.data, null, 1)}</pre> : null}
            </li>)}
          </ol>
        </details>}
      {result.limitations.length > 0 && <ul className="assistant-limitations">
        {result.limitations.map((item, index) => <li key={index}>{item}</li>)}
      </ul>}
    </div>}
  </section>
}
