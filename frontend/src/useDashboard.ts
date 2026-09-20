import { useEffect, useState } from 'react'
import type { Metric, Snapshot, Status, Measurement, AlarmSnapshot, MetricSnapshot, OpcuaStatus } from './model'
import { startPolling } from './poll'

async function get<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, cache: 'no-store' })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.error?.message || `接口请求失败（HTTP ${response.status}）`)
  }
  return response.json()
}

export async function loadSnapshot(signal: AbortSignal, deviceId = 'motor-a'): Promise<Snapshot> {
  const list = await get<{ devices: Snapshot['device'][] }>('/api/devices', signal)
  const device = list.devices.find(item => item.id === deviceId)
  if (!device) throw new Error(`设备列表中未找到 ${deviceId}`)
  const statusRequestedAt = performance.now()
  const latest = await get<{ measurement: Measurement | null; status: Status; alarm?: AlarmSnapshot; opcua?: OpcuaStatus | null; replay?: Snapshot['replay'] }>(`/api/devices/${device.id}/latest`, signal)
  // 使用服务端检查时间定义窗口，避免浏览器和后端时钟不同导致漏掉最新样本。
  const to = latest.status.checked_at
  const from = new Date(Date.parse(to) - 10 * 60_000).toISOString()
  const query = new URLSearchParams({ metric: 'temperature', from, to, limit: '1000' })
  const history = await get<Snapshot['history']>(`/api/devices/${device.id}/history?${query}`, signal)
  // 附加指标按设备白名单动态获取；温度已由上方单独查询。
  async function extraMetric(metric: Metric): Promise<MetricSnapshot> {
    const requestedAt = performance.now()
    const result = await get<{ metric: string; measurement: Measurement | null; status: Status }>(`/api/devices/${device!.id}/latest?metric=${metric}`, signal)
    if (result.metric !== metric) throw new Error(`${metric}接口返回了不匹配的指标`)
    const end = result.status.checked_at
    const start = new Date(Date.parse(end) - 10 * 60_000).toISOString()
    const params = new URLSearchParams({ metric, from: start, to: end, limit: '1000' })
    const metricHistory = await get<Snapshot['history']>(`/api/devices/${device!.id}/history?${params}`, signal)
    return { ...result, history: metricHistory, statusRequestedAt: requestedAt }
  }
  const metrics = (device.metrics ?? ['temperature']).filter(metric => metric !== 'temperature') as Metric[]
  const extras: Partial<Record<Metric, MetricSnapshot>> = {}
  await Promise.all(metrics.map(async metric => { extras[metric] = await extraMetric(metric) }))
  return { device, devices: list.devices, ...latest, history, statusRequestedAt, ...extras }
}

export function useDashboard(deviceId = 'motor-a') {
  const [snapshot, setSnapshot] = useState<Snapshot>()
  const [phase, setPhase] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [error, setError] = useState<string>()
  const [fetchedAt, setFetchedAt] = useState<number>()
  useEffect(() => {
    setSnapshot(undefined); setFetchedAt(undefined); setError(undefined); setPhase('idle')
    return startPolling(signal => loadSnapshot(signal, deviceId),
    () => setPhase('loading'),
    value => { setSnapshot(value); setFetchedAt(Date.now()); setError(undefined); setPhase('ready') },
    message => { setError(message); setPhase('error') },
    )
  }, [deviceId])
  // 切换时 effect 尚未运行也不把上一台设备的读数展示在新设备名下。
  const selected = snapshot?.device.id === deviceId ? snapshot : undefined
  return { snapshot: selected, phase, error, fetchedAt: selected ? fetchedAt : undefined }
}
