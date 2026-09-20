import { useEffect, useRef } from 'react'
import { init, use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { buildSeries, yBounds, type Metric, type Snapshot } from './model'

use([LineChart, GridComponent, TooltipComponent, SVGRenderer])

const LABELS: Record<Metric, { label: string; unit: string; decimals: number }> = {
  temperature: { label: '温度', unit: '℃', decimals: 1 },
  air_temperature: { label: '空气温度', unit: '℃', decimals: 1 },
  current: { label: '电流', unit: 'A', decimals: 2 },
  speed: { label: '转速', unit: 'rpm', decimals: 0 },
  torque: { label: '扭矩', unit: 'Nm', decimals: 1 },
  tool_wear: { label: '刀具磨损', unit: 'min', decimals: 0 },
  running_state: { label: '运行状态', unit: '', decimals: 0 },
}

export function TemperatureChart({ history, metric = 'temperature' }: { history: Snapshot['history']; metric?: Metric }) {
  const { label, unit, decimals } = LABELS[metric]
  const element = useRef<HTMLDivElement>(null)
  const chart = useRef<ReturnType<typeof init> | null>(null)
  useEffect(() => {
    const instance = init(element.current!, undefined, { renderer: 'svg' })
    chart.current = instance
    const resize = new ResizeObserver(() => instance.resize())
    resize.observe(element.current!)
    return () => { resize.disconnect(); instance.dispose(); chart.current = null }
  }, [])
  useEffect(() => {
    const [min, max] = yBounds(history.points.map(point => point.value))
    chart.current?.setOption({
      animation: false,
      grid: { top: 28, bottom: 32, left: 48, right: 16 },
      tooltip: { trigger: 'axis', confine: true, valueFormatter: (value: unknown) => value == null ? '缺口' : `${value} ${unit}` },
      xAxis: { type: 'time', min: Date.parse(history.from), max: Date.parse(history.to), splitNumber: 4,
        axisLine: { lineStyle: { color: '#464b47' } }, axisTick: { show: false },
        axisLabel: { color: '#a9aca0', fontSize: 12, hideOverlap: true, formatter: '{HH}:{mm}' } },
      yAxis: { type: 'value', min, max, name: unit, splitNumber: 4,
        nameTextStyle: { color: '#a9aca0', padding: [0, 18, 0, 0] },
        axisLabel: { color: '#a9aca0', fontSize: 12, formatter: (value: number) => value.toFixed(decimals) },
        splitLine: { lineStyle: { color: '#3a3f3c', type: 'dashed' } } },
      series: [{ name: label, type: 'line', data: buildSeries(history.points), connectNulls: false,
        smooth: false, showSymbol: true, symbolSize: 4, lineStyle: { width: 2, color: '#ffb000' },
        itemStyle: { color: '#ffb000' } }],
    }, true)
  }, [history, metric, label, unit, decimals])
  return <div className="chart" ref={element} role="img" aria-label={`最近十分钟${label}曲线，${history.points.length}个真实样本，缺口不连线`} />
}
