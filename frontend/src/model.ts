export interface Measurement {
  id: number; device_id: string; metric: string; value: number; unit: string
  collected_at: string; source_time: string | null; quality: string; protocol: string
}
export type Metric = 'temperature' | 'air_temperature' | 'current' | 'speed' | 'torque' | 'tool_wear' | 'running_state'
export interface MetricSnapshot {
  measurement: Measurement | null; status: Status; statusRequestedAt?: number; history?: Snapshot['history']
}
export interface Status {
  last_failure_type?: string | null; last_failure_message?: string | null
  has_data: boolean; last_attempt_status: 'success' | 'failure' | 'unknown'
  last_attempt_at: string | null; last_success_at: string | null; last_failure_at: string | null
  data_age_seconds: number | null; is_stale: boolean | null; checked_at: string; stale_after_seconds: number
}
export interface OpcuaRuntime {
  mode: 'read' | 'subscribe'
  state: 'reading' | 'connecting' | 'subscribed' | 'reconnecting' | 'stopped' | 'failed' | 'unknown'
  reported_state?: string
  generation: number; updated_at: string; last_notification_at: string | null; last_publish_at: string | null
  reconnect_count: number; duplicate_count: number; dropped_count: number; error: string | null
  revised: { publishing_interval_ms: number; sampling_interval_ms: number; queue_size: number; keepalive_count: number; lifetime_count: number } | null
}
export interface OpcuaStatus {
  runtime?: OpcuaRuntime | null
  communication: 'success' | 'failure' | 'unknown'
  quality: 'good' | 'bad' | 'uncertain' | 'unknown'
  source_freshness: 'fresh' | 'missing' | 'stale' | 'future' | 'duplicate' | 'backward' | 'unknown'
  eligible: boolean; reason: string
  diagnostic: { value_json: string; status_code: number; status_name: string; source_time: string | null; server_time: string | null; received_at: string; accepted: boolean; variant_type: string; reason?: string; decision_at?: string | null } | null
}
export interface ReplayFault { occurred_at: string; message: string }
export interface ReplayStatus {
  mode: 'historical_replay'
  dataset: { name: string; author: string; source: string; license: string; synthetic: boolean; sha256: string; rows_total: number }
  note: string
  faults: ReplayFault[]
  faults_total: number
}
export interface Snapshot {
  devices?: Snapshot['device'][]
  opcua?: OpcuaStatus | null
  replay?: ReplayStatus | null
  statusRequestedAt?: number
  device: { id: string; name: string; protocol: string; metrics?: string[] }
  current?: MetricSnapshot; speed?: MetricSnapshot; running_state?: MetricSnapshot
  air_temperature?: MetricSnapshot; torque?: MetricSnapshot; tool_wear?: MetricSnapshot
  measurement: Measurement | null; status: Status; alarm?: AlarmSnapshot
  history: { from: string; to: string; limit: number; points: Measurement[] }
}

export function freshness(status: Pick<Status, 'has_data' | 'is_stale'> | undefined, unverified: boolean) {
  if (unverified) return { label: '当前状态未能核实', tone: 'neutral' }
  if (!status?.has_data) return { label: '暂无温度样本', tone: 'neutral' }
  if (status.is_stale) return { label: '数据已过期', tone: 'warn' }
  return { label: '数据未过期', tone: '' }
}

export function buildSeries(points: Pick<Measurement, 'collected_at' | 'value'>[]): [number, number | null][] {
  const result: [number, number | null][] = []
  let previous: number | undefined
  for (const point of points) {
    const time = Date.parse(point.collected_at)
    if (!Number.isFinite(time) || !Number.isFinite(point.value)) continue
    if (previous !== undefined && time - previous > 1500) result.push([previous + 1, null])
    result.push([time, point.value])
    previous = time
  }
  return result
}

export function yBounds(values: number[]): [number, number] {
  if (!values.length) return [0, 1]
  const min = Math.min(...values), max = Math.max(...values)
  const padding = Math.max(1, (max - min) * 0.15)
  return [min - padding, max + padding]
}

export function localTime(value: string | number | null | undefined) {
  if (value == null) return '—'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

export interface AlarmEvent {
  id: number; started_at: string; trigger_value: number; trigger_measurement_id: number
  recovered_at: string | null; recovery_value: number | null; recovery_measurement_id: number | null
  trigger_above: number; recover_below: number
  confirm_seconds?: number; observed_seconds?: number | null; max_gap_seconds?: number | null; first_exceeded_at?: string | null
  first_exceeded_measurement_id?: number | null; first_exceeded_value?: number | null
}
export interface AlarmSnapshot {
  enabled: boolean; current: 'not_enabled' | 'unknown' | 'pending' | 'active' | 'clear'
  active: AlarmEvent | null; history: AlarmEvent[]; total: number; limit: number
  evaluated_measurement_id: number | null
  pending?: { first_exceeded_at: string; first_exceeded_measurement_id: number; first_exceeded_value: number; elapsed_seconds: number } | null
  rule: { confirm_seconds?: number; max_gap_seconds?: number | null; trigger_above: number; recover_below: number; unit: string; teaching_only: boolean }
}
