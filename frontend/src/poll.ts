/** 轮次串行，完成后再排下一次；停止时取消网络和定时器。 */
export function startPolling<T>(
  load: (signal: AbortSignal) => Promise<T>, onStart: () => void,
  onData: (value: T) => void, onError: (message: string) => void,
) {
  let stopped = false
  let next: ReturnType<typeof setTimeout> | undefined
  let timeout: ReturnType<typeof setTimeout> | undefined
  let controller: AbortController | undefined
  async function run() {
    controller = new AbortController()
    const current = controller
    onStart()
    timeout = setTimeout(() => current.abort(), 8000)
    try {
      const value = await load(current.signal)
      if (!stopped && !current.signal.aborted) onData(value)
    } catch (error) {
      if (!stopped) onError(current.signal.aborted ? '请求超过 8 秒，请检查后端服务。' :
        error instanceof Error ? error.message : '接口请求失败')
    } finally {
      clearTimeout(timeout)
      if (!stopped) next = setTimeout(run, 2000)
    }
  }
  void run()
  return () => { stopped = true; clearTimeout(next); clearTimeout(timeout); controller?.abort() }
}
