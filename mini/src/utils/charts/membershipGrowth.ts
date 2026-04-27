interface GrowthTierPoint {
  name: string
  grade: number
  exp_required: number
  reached: boolean
  active: boolean
}

interface GrowthChartTheme {
  primary: string
  primarySoft: string
  accent: string
  axis: string
  muted: string
}

export function buildMembershipGrowthOption(points: GrowthTierPoint[], totalExp: number, theme: GrowthChartTheme) {
  const labels = points.map(item => `Lv.${item.grade}`)
  const expValues = points.map(item => item.exp_required)
  const currentIndex = Math.max(0, points.findIndex(item => item.active))
  const maxExp = Math.max(...expValues, totalExp, 1)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      confine: true,
      formatter(params: Array<{ dataIndex: number }>) {
        const point = points[params[0]?.dataIndex || 0]
        if (!point) {
          return ''
        }
        return `${point.name}<br/>门槛：${point.exp_required} 经验`
      },
    },
    grid: {
      left: 10,
      right: 14,
      top: 18,
      bottom: 22,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#E2E8F0' } },
      axisLabel: {
        color: '#64748B',
        fontSize: 10,
        fontWeight: 700,
        fontStyle: 'italic',
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: Math.ceil(maxExp / 1000) * 1000,
      splitNumber: 4,
      axisLabel: {
        color: '#94A3B8',
        fontSize: 10,
      },
      splitLine: {
        lineStyle: {
          color: theme.axis,
          type: 'dashed',
        },
      },
    },
    series: [
      {
        name: '等级经验',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: expValues,
        lineStyle: {
          width: 4,
          color: theme.primary,
          cap: 'round',
        },
        itemStyle: {
          color(params: { dataIndex: number }) {
            const point = points[params.dataIndex]
            if (point?.active) {
              return theme.accent
            }
            return point?.reached ? theme.primary : theme.muted
          },
          borderColor: '#FFFFFF',
          borderWidth: 3,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: theme.primarySoft },
              { offset: 1, color: 'rgba(255, 255, 255, 0.02)' },
            ],
          },
        },
        markLine: {
          symbol: 'none',
          silent: true,
          label: {
            formatter: '当前',
            color: theme.accent,
            fontSize: 10,
            fontStyle: 'italic',
            position: 'insideEndTop',
          },
          lineStyle: {
            color: theme.accent,
            type: 'dashed',
            width: 1,
          },
          data: [{ yAxis: totalExp }],
        },
      },
      {
        name: '当前等级',
        type: 'line',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        data: expValues.map((value, index) => (index <= currentIndex ? value : null)),
        areaStyle: {
          color: 'rgba(15, 118, 110, 0.08)',
        },
      },
    ],
  }
}
