// 回放面板：诚实标注不缺失，故障史显示数据集标注而非系统诊断。
import { expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ReplayFaultPanel, ReplayMetricsPanel, replayRunningLabel } from './ReplayPanel'
import { OperatingPanel, RunningHistory } from './OperatingPanel'
import type { MetricSnapshot, ReplayStatus } from './model'

const dataset = {
  name: 'AI4I 2020 Predictive Maintenance Dataset', author: 'Stephan Matzka (HTW Berlin), UCI Machine Learning Repository',
  source: 'https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset',
  license: 'CC BY 4.0', synthetic: true, sha256: 'dc6630', rows_total: 10000,
}
const replay: ReplayStatus = {
  mode: 'historical_replay', dataset, note: '合成数据集历史回放：时间为回放时刻，非原始采集时间；故障标注来自数据集自身，本系统不做再判定。',
  faults: [{ occurred_at: '2026-09-20T08:00:01+00:00', message: '数据集标注故障：散热不良（HDF）' }], faults_total: 1,
}

it('故障史面板保留来源、许可与合成声明，故障显示数据集标注原文', () => {
  const html = renderToStaticMarkup(<ReplayFaultPanel replay={replay} unverified={false} />)
  expect(html).toContain('数据集标注故障')
  expect(html).toContain('散热不良（HDF）')
  expect(html).toContain('CC BY 4.0')
  expect(html).toContain('archive.ics.uci.edu')
  expect(html).toContain('10000')
  expect(html).toContain('合成数据')
  expect(html).toContain('不做再判定')
})

it('无故障窗口提示继续回放，未加载时不显示编造内容', () => {
  const html = renderToStaticMarkup(<ReplayFaultPanel replay={{ ...replay, faults: [], faults_total: 0 }} unverified={false} />)
  expect(html).toContain('还没有数据集标注的故障行')
  const loading = renderToStaticMarkup(<ReplayFaultPanel unverified={false} />)
  expect(loading).toContain('回放信息待加载')
  expect(loading).not.toContain('散热不良')
})

const reading = (value: number, age = 1): MetricSnapshot => ({
  measurement: { id: 1, device_id: 'motor-c', metric: 'torque', value, unit: 'Nm',
    collected_at: '2026-09-20T08:00:02+00:00', source_time: null, quality: 'good', protocol: 'replay' },
  status: {
    has_data: true, last_attempt_status: 'success', last_attempt_at: '2026-09-20T08:00:02+00:00',
    last_success_at: '2026-09-20T08:00:02+00:00', last_failure_at: null, last_failure_type: null, last_failure_message: null,
    data_age_seconds: age, is_stale: false, checked_at: '2026-09-20T08:00:03+00:00', stale_after_seconds: 5,
  },
  statusRequestedAt: performance.now(),
})

it('附加指标卡显示数据集原值，回放停止后如实标注过期', () => {
  const html = renderToStaticMarkup(<ReplayMetricsPanel torque={reading(46.3)} toolWear={reading(9)} airTemperature={reading(25)} unverified={false} />)
  expect(html).toContain('46.3')
  expect(html).toContain('刀具磨损')
  expect(html).toContain('空气温度')
  expect(html).toContain('回放进行中')
  const stale = renderToStaticMarkup(<ReplayMetricsPanel torque={reading(46.3, 99)} unverified={false} />)
  expect(stale).toContain('回放已停止：数据过期')
})

it('回放设备运行状态语义为正常运转/数据集标注故障，不是停止/运行', () => {
  expect(replayRunningLabel(1)).toBe('正常运转')
  expect(replayRunningLabel(0)).toBe('数据集标注故障')
  const html = renderToStaticMarkup(<OperatingPanel metric="running_state" reading={reading(0)} unverified={false} replay />)
  expect(html).toContain('数据集标注故障')
  expect(html).not.toContain('>停止<')
  expect(html).toContain('Machine failure 列')
  expect(html).toContain('该行回放时间')
})

it('运行状态历史表使用回放语义与回放时间列名', () => {
  const html = renderToStaticMarkup(<RunningHistory history={{
    from: '2026-09-20T08:00:00+00:00', to: '2026-09-20T08:00:02+00:00', limit: 1000,
    points: [reading(0).measurement!, reading(1).measurement!],
  }} replay />)
  expect(html).toContain('该行回放时间')
  expect(html).toContain('正常运转')
  expect(html).not.toContain('>停止<')
})
