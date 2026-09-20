import { useEffect, useRef } from 'react'
import { init, use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { buildSeries, yBounds, type Snapshot } from './model'

use([LineChart, GridComponent, TooltipComponent, SVGRenderer])

export function TemperatureChart({ history, metric = 'temperature' }: { history: Snapshot['history']; metric?: 'temperature' | 'current' | 'speed' }) {
  const label = metric === 'speed' ? '转速' : metric === 'current' ? '电流' : '温度'
  const unit = metric === 'speed' ? 'rpm' : metric === 'current' ? 'A' : '℃'
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
        axisLine: { lineStyle: { color: '#cedce8' } }, axisTick: { show: false },
        axisLabel: { color: '#60788b', fontSize: 12, hideOverlap: true, formatter: '{HH}:{mm}' } },
      yAxis: { type: 'value', min, max, name: unit, splitNumber: 4,
        nameTextStyle: { color: '#60788b', padding: [0, 18, 0, 0] },
        axisLabel: { color: '#60788b', fontSize: 12, formatter: (value: number) => value.toFixed(metric === 'speed' ? 0 : metric === 'current' ? 2 : 1) },
        splitLine: { lineStyle: { color: '#e4ecf3', type: 'dashed' } } },
      series: [{ name: label, type: 'line', data: buildSeries(history.points), connectNulls: false,
        smooth: false, showSymbol: true, symbolSize: 4, lineStyle: { width: 2, color: '#356489' },
        itemStyle: { color: '#356489' } }],
    }, true)
  }, [history, metric, label, unit])
  return <div className="chart" ref={element} role="img" aria-label={`最近十分钟${label}曲线，${history.points.length}个真实样本，缺口不连线`} />
}
