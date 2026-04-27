import './zrenderEnv'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  CanvasRenderer,
  GridComponent,
  LineChart,
  MarkLineComponent,
  TooltipComponent,
])

export { echarts }
