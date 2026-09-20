import { expect, it } from 'vitest'
import { alarmUnverified } from './alarmFreshness'

it('等待历史接口期间或页面停留期间跨过过期边界，告警变未知', () => {
  const snapshot = { status: { data_age_seconds: 4, stale_after_seconds: 5 }, statusRequestedAt: 1000 }
  expect(alarmUnverified(snapshot, false, 2000)).toBe(false)
  expect(alarmUnverified(snapshot, false, 2001)).toBe(true)
  expect(alarmUnverified(snapshot, true, 1000)).toBe(true)
  expect(alarmUnverified(undefined, false, 1000)).toBe(true)
})

it('旧库无样本或样本过期时仍明确未启用，接口失效才变未知', () => {
  for (const age of [null, 100]) {
    const snapshot = { alarm: { current: 'not_enabled' as const }, status: { data_age_seconds: age, stale_after_seconds: 5 }, statusRequestedAt: 1000 }
    expect(alarmUnverified(snapshot, false, 3000)).toBe(false)
    expect(alarmUnverified(snapshot, true, 3000)).toBe(true)
  }
})

it('pending使用采样间隔容忍判断时效，不等待5秒数据过期', () => {
  const snapshot = { alarm: { current: 'pending' as const, rule: { max_gap_seconds: 1.5 } }, status: { data_age_seconds: .5, stale_after_seconds: 5 }, statusRequestedAt: 1000 }
  expect(alarmUnverified(snapshot,false,2000)).toBe(false)
  expect(alarmUnverified(snapshot,false,2001)).toBe(true)
})

it('订阅心跳在本地等待期间过期；终态和旧API不伪装为活跃订阅', async () => {
  const { runtimeExpired } = await import('./alarmFreshness')
  const runtime = { state: 'subscribed', updated_at: '2026-09-17T00:00:00Z' }
  const snapshot = { status: { checked_at: '2026-09-17T00:00:04Z' }, statusRequestedAt: 1000, opcua: { runtime } }
  expect(runtimeExpired(snapshot, 1500)).toBe(false)
  expect(runtimeExpired(snapshot, 2100)).toBe(true)
  expect(runtimeExpired({ ...snapshot, opcua: { runtime: { ...runtime, state: 'stopped' } } }, 10000)).toBe(false)
  expect(runtimeExpired({ ...snapshot, opcua: { runtime: null } }, 10000)).toBe(false)
})
