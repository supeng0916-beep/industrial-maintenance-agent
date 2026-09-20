import { expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { OpcuaPanel } from './OpcuaPanel'
import type { OpcuaStatus } from './model'

const diagnostic={value_json:'90',status_code:0,status_name:'Good',source_time:'2026-09-17T00:00:00Z',server_time:'2026-09-17T00:00:00Z',received_at:'2026-09-17T00:00:01Z',accepted:true,variant_type:'Double'}
const base:OpcuaStatus={communication:'success',quality:'good',source_freshness:'fresh',eligible:true,reason:'accepted',diagnostic}
it('质量Bad与通信成功分开，诊断原始值不能冒充有效温度',()=>{
  const html=renderToStaticMarkup(<OpcuaPanel evidence={{...base,quality:'bad',eligible:false,reason:'bad_quality',diagnostic:{...diagnostic,status_name:'Bad',status_code:2147483648,accepted:false}}} unverified={false}/> )
  expect(html).toContain('读取成功')
  expect(html).toContain('Bad')
  expect(html).toContain('不可参与温度告警')
  expect(html).toContain('原始值（诊断）')
  expect(html).not.toContain('通信失败')
})
it('缺源保持null，接收时间不能替代源时间',()=>{
  const html=renderToStaticMarkup(<OpcuaPanel evidence={{...base,eligible:false,source_freshness:'missing',diagnostic:{...diagnostic,source_time:null,accepted:false}}} unverified={false}/> )
  expect(html).toContain('设备未提供源时间，测量新鲜度无法核实')
  expect(html).toContain('接收时间')
  expect(html).toContain('设备源时间')
})
it('请求延迟或错误使旧可用证据显示当前未知',()=>{
  const html=renderToStaticMarkup(<OpcuaPanel evidence={base} unverified/> )
  expect(html).toContain('当前未知')
  expect(html).not.toContain('可以参与温度告警')
})

it('没有有效温度时，新鲜Bad诊断不误标为源过期', async () => {
  const { diagnosticExpired } = await import('./alarmFreshness')
  expect(diagnosticExpired({ status: { checked_at: '2026-09-17T00:00:01Z', stale_after_seconds: 5 }, statusRequestedAt: 1000, opcua: base }, 2000)).toBe(false)
  expect(diagnosticExpired({ status: { checked_at: '2026-09-17T00:00:01Z', stale_after_seconds: 5 }, statusRequestedAt: 1000, opcua: base }, 6001)).toBe(true)
})

const subscribed = {
  mode: 'subscribe' as const, state: 'subscribed' as const, generation: 2,
  updated_at: '2026-09-17T00:00:01Z', last_notification_at: '2026-09-17T00:00:00Z', last_publish_at: '2026-09-17T00:00:01Z',
  reconnect_count: 1, duplicate_count: 3, dropped_count: 0, error: null,
  revised: { publishing_interval_ms: 250, sampling_interval_ms: 250, queue_size: 16, keepalive_count: 4, lifetime_count: 12 },
}
it('订阅活性与温度可用分开，保活不能让Bad可参与告警', () => {
  const html = renderToStaticMarkup(<OpcuaPanel evidence={{ ...base, quality: 'bad', eligible: false, diagnostic: { ...diagnostic, status_code: 2147483648, status_name: 'Bad', accepted: false }, runtime: subscribed }} unverified={false} />)
  expect(html).toContain('订阅通知')
  expect(html).toContain('已订阅')
  expect(html).toContain('最近发布响应（含保活）')
  expect(html).toContain('不可参与温度告警')
  expect(html).toContain('250 ms')
})
it('重连和停止状态不把旧订阅说成在线，不解除历史告警', () => {
  for (const [state, label] of [['reconnecting', '等待重连'], ['stopped', '采集已停止'], ['failed', '采集故障停止']] as const) {
    const html = renderToStaticMarkup(<OpcuaPanel evidence={{ ...base, eligible: false, runtime: { ...subscribed, state, error: 'test interruption' } }} unverified={false} />)
    expect(html).toContain(label)
    expect(html).toContain('不可参与温度告警')
    expect(html).toContain('test interruption')
  }
})
it('已过期的订阅心跳不能持续显示已订阅或参与告警', () => {
  const html = renderToStaticMarkup(<OpcuaPanel evidence={{ ...base, runtime: subscribed }} unverified={false} runtimeExpired />)
  expect(html).toContain('当前未知')
  expect(html).not.toContain('可以参与温度告警')
  expect(html).not.toContain('>已订阅<')
})

it('排队后的判定时间独立显示，不覆盖通知的真实接收时间', () => {
  const html = renderToStaticMarkup(<OpcuaPanel evidence={{ ...base, eligible: false, source_freshness: 'stale', diagnostic: { ...diagnostic, accepted: false, received_at: '2026-09-17T00:00:01Z', decision_at: '2026-09-17T00:00:21Z', reason: 'stale_at_decision' } }} unverified={false} />)
  expect(html).toContain('判定时间')
  expect(html).toContain('2026-09-17T00:00:21Z')
  expect(html).toContain('2026-09-17T00:00:01Z')
  expect(html).toContain('不可参与温度告警')
})
