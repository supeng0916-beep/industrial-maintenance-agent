import { afterEach, expect, it, vi } from 'vitest'
import { startPolling } from './poll'

afterEach(() => vi.useRealTimers())
it('慢请求不重叠；卸载取消且不能写入迟到响应', async () => {
  vi.useFakeTimers()
  let resolve!: (value: number) => void
  let signal!: AbortSignal
  const load = vi.fn((s: AbortSignal) => { signal = s; return new Promise<number>(r => { resolve = r }) })
  const data = vi.fn()
  const stop = startPolling(load, () => {}, data, () => {})
  await vi.advanceTimersByTimeAsync(5000)
  expect(load).toHaveBeenCalledTimes(1)
  stop()
  expect(signal.aborted).toBe(true)
  resolve(1)
  await vi.advanceTimersByTimeAsync(10000)
  expect(data).not.toHaveBeenCalled()
  expect(load).toHaveBeenCalledTimes(1)
})

it('8秒超时报告错误，下一轮仍能恢复且只提交新响应', async () => {
  vi.useFakeTimers()
  const load = vi.fn()
    .mockImplementationOnce((signal: AbortSignal) => new Promise((_, reject) => {
      signal.addEventListener('abort', () => reject(new Error('aborted')))
    }))
    .mockResolvedValueOnce(72.8)
  const data = vi.fn(), error = vi.fn()
  const stop = startPolling(load, () => {}, data, error)
  await vi.advanceTimersByTimeAsync(8000)
  expect(error).toHaveBeenCalledWith('请求超过 8 秒，请检查后端服务。')
  expect(data).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(2000)
  expect(data).toHaveBeenCalledExactlyOnceWith(72.8)
  stop()
})
