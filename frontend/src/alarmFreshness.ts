import type { Status, AlarmSnapshot } from './model'

export function alarmUnverified(
  snapshot: { status: Pick<Status, 'data_age_seconds' | 'stale_after_seconds'>; statusRequestedAt?: number; alarm?: Pick<AlarmSnapshot, 'current'> & { rule?: Pick<AlarmSnapshot['rule'], 'max_gap_seconds'> } } | undefined,
  unavailable: boolean, monotonicNow: number,
) {
  if (unavailable || !snapshot || snapshot.statusRequestedAt === undefined) return true
  if (snapshot.alarm?.current === 'not_enabled') return false
  const age = snapshot.status.data_age_seconds
  if (age === null) return true
  // 用本地单调时钟累加等待时间，不比较浏览器/服务器绝对时钟。
  // 从 latest 请求开始计时，网络往返计入年龄上界，宁可早显示未知。
  const threshold = snapshot.alarm?.current === 'pending' && snapshot.alarm.rule?.max_gap_seconds != null
    ? Math.min(snapshot.status.stale_after_seconds, snapshot.alarm.rule.max_gap_seconds) : snapshot.status.stale_after_seconds
  return age + Math.max(0, monotonicNow - snapshot.statusRequestedAt) / 1000 > threshold
}

/** 诊断源年龄独立于最后有效温度年龄；新鲜Bad也仍是新鲜的诊断。 */
export function diagnosticExpired(snapshot: {
  status: Pick<Status, 'checked_at' | 'stale_after_seconds'>; statusRequestedAt?: number
  opcua?: { diagnostic: { source_time: string | null } | null } | null
} | undefined, monotonicNow: number) {
  const source = snapshot?.opcua?.diagnostic?.source_time
  if (!snapshot || !source || snapshot.statusRequestedAt === undefined) return false
  const age = (Date.parse(snapshot.status.checked_at) - Date.parse(source)) / 1000
  return age + Math.max(0, monotonicNow - snapshot.statusRequestedAt) / 1000 > snapshot.status.stale_after_seconds
}

export function runtimeExpired(snapshot: {
  status: Pick<Status, 'checked_at'>; statusRequestedAt?: number
  opcua?: { runtime?: { updated_at: string; state: string } | null } | null
} | undefined, monotonicNow: number) {
  const runtime = snapshot?.opcua?.runtime
  if (!snapshot || !runtime || ['stopped', 'failed'].includes(runtime.state)) return false
  if (snapshot.statusRequestedAt === undefined) return true
  const age = (Date.parse(snapshot.status.checked_at) - Date.parse(runtime.updated_at)) / 1000
  return !Number.isFinite(age) || age < 0 || age + Math.max(0, monotonicNow - snapshot.statusRequestedAt) / 1000 > 5
}
