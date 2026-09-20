import { describe, expect, it } from 'vitest'
import { buildSeries, freshness, yBounds } from './model'

describe('状态不能把历史成功误当作当前已核实', () => {
  it('请求失败或延迟更新优先于之前的新鲜状态', () => {
    expect(freshness({ has_data: true, is_stale: false }, true).label).toBe('当前状态未能核实')
    expect(freshness({ has_data: true, is_stale: false }, false).label).toBe('数据未过期')
    expect(freshness({ has_data: true, is_stale: true }, false).label).toBe('数据已过期')
    expect(freshness({ has_data: false, is_stale: null }, false).label).toBe('暂无温度样本')
  })
})

describe('真实时间曲线', () => {
  it('缺口加空标记，不插值、不补零，保留不同offset真实时刻', () => {
    const data = buildSeries([
      { collected_at: '2026-09-16T08:00:00+08:00', value: 65.3 },
      { collected_at: '2026-09-16T00:00:01Z', value: 65.3 },
      { collected_at: '2026-09-16T00:00:07Z', value: 72.8 },
    ])
    expect(data).toEqual([[1789516800000,65.3], [1789516801000,65.3], [1789516801001,null], [1789516807000,72.8]])
  })
  it('空数组不造样本，单点/固定值有可见Y轴范围', () => {
    expect(buildSeries([])).toEqual([])
    expect(yBounds([65.3])).toEqual([64.3,66.3])
    expect(yBounds([65.3,65.3])).toEqual([64.3,66.3])
    expect(buildSeries([{collected_at: '2026-09-16T00:00:00Z', value:0}])[0][1]).toBe(0)
  })
  it('默认1秒采样漏掉一轮形成2秒间隔时也断线', () => {
    expect(buildSeries([
      { collected_at: '2026-09-16T00:00:00Z', value: 65.3 },
      { collected_at: '2026-09-16T00:00:02Z', value: 65.3 },
    ]).map(point => point[1])).toEqual([65.3, null, 65.3])
  })
})
