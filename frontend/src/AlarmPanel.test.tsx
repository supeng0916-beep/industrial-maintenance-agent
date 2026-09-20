import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { AlarmPanel } from './AlarmPanel'
import type { AlarmSnapshot } from './model'

const active = { id: 1, started_at: '2026-09-16T12:00:00Z', trigger_value: 81, trigger_measurement_id: 1, recovered_at: null, recovery_value: null, recovery_measurement_id: null, trigger_above: 80, recover_below: 78 }
const snapshot: AlarmSnapshot = { enabled: true, current: 'active', active, history: [active], total: 1, limit: 20, evaluated_measurement_id: 1, rule: { trigger_above: 80, recover_below: 78, unit: '℃', teaching_only: true } }
describe('告警面板的事实与当前可知性', () => {
  it('接口失效时保留未解除证据，同时明确当前未知', () => {
    const html = renderToStaticMarkup(<AlarmPanel alarm={snapshot} unverified />)
    expect(html).toContain('当前未知')
    expect(html).toContain('历史快照中有未解除告警')
    expect(html).toContain('81.0')
    expect(html).not.toContain('当前温度告警中')
  })
  it('区分旧库未启用、未评估与已恢复记录', () => {
    const disabled = renderToStaticMarkup(<AlarmPanel alarm={{ ...snapshot, enabled: false, current: 'not_enabled', active: null, history: [], total: 0 }} unverified={false} />)
    expect(disabled).toContain('告警规则未启用')
    expect(disabled).not.toContain('当前无未解除告警')
    const unknown = renderToStaticMarkup(<AlarmPanel alarm={{ ...snapshot, current: 'unknown' }} unverified={false} />)
    expect(unknown).toContain('当前未知')
    expect(unknown).toContain('仍有未解除告警')
    const restored = renderToStaticMarkup(<AlarmPanel alarm={{ ...snapshot, current: 'clear', active: null, history: [{ ...active, recovered_at: '2026-09-16T12:00:02Z', recovery_value: 77.9, recovery_measurement_id: 2 }] }} unverified={false} />)
    expect(restored).toContain('当前无未解除告警')
    expect(restored).toContain('已恢复')
    expect(restored).toContain('77.9')
  })
})

it('待确认只显示服务端已观测时长，未知时不继续倒计时；历史区分首超限和触发', () => {
  const pending = { first_exceeded_at: '2026-09-16T12:00:00Z', first_exceeded_measurement_id: 1, first_exceeded_value: 81, elapsed_seconds: 3 }
  const result = { ...snapshot, current: 'pending' as const, active: null, history: [], total: 0, pending, rule: { ...snapshot.rule, confirm_seconds: 5, max_gap_seconds: 1.5 } }
  const html = renderToStaticMarkup(<AlarmPanel alarm={result} unverified={false} />)
  expect(html).toContain('超限待确认')
  expect(html).toContain('已观测累计 3.0 秒')
  expect(html).not.toContain('当前无未解除告警')
  const unknown = renderToStaticMarkup(<AlarmPanel alarm={result} unverified />)
  expect(unknown).toContain('当前未知')
  expect(unknown).not.toContain('已观测累计 3.0 秒')
  const history = renderToStaticMarkup(<AlarmPanel alarm={{ ...snapshot, history: [{ ...active, confirm_seconds: 5, first_exceeded_at: pending.first_exceeded_at, first_exceeded_measurement_id: 1, first_exceeded_value: 81 }] }} unverified={false} />)
  expect(history).toContain('首次超限')
  expect(history).toContain('正式触发')
})
