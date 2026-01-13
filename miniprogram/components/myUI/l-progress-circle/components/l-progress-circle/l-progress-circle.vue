<template>
  <view class="progress-container">
    <canvas class="progress-canvas" :canvas-id="`progressCanvas${index}`" :style="{ width: parsedWidth + 'px', height: parsedHeight + 'px' }"> </canvas>
    <view class="progress-content">
      <slot />
    </view>
  </view>
</template>

<script>
export default {
  props: {
    percent: {
      type: [Number, String],
      default: 0,
      validator: (value) => value >= 0 && value <= 100,
    },
    strokeWidth: {
      type: Number,
      default: 4,
    },
    bgColor: {
      type: String,
      default: '#eeeeee',
    },
    progressColor: {
      type: [String, Object], // 支持字符串或对象格式
      default: '#19be6b',
      validator: (value) => {
        if (typeof value === 'string') return true
        if(!value.type) value.type = 'linear'
        // 验证渐变配置对象
        return value?.type && ['linear', 'radial'].includes(value.type) && Array.isArray(value.colors) && value.colors.every((stop) => stop.offset >= 0 && stop.offset <= 1 && stop.color)
      },
    },
    dotColor: {
      type: String,
    },
    width: {
      type: [Number, String],
      default: 200,
    },
    height: {
      type: [Number, String],
    },
    index: {
      type: [Number, String],
      default: 0,
    },
  },
  computed: {
    parsedWidth() {
      return this.parseUnit(this.width)
    },
    parsedHeight() {
      const height = this.height ? this.height : this.parsedWidth / 2
      return this.parseUnit(height)
    },
    parsedDotColor() {
      if (this.dotColor) return this.dotColor
      if (typeof this.progressColor === 'string') return this.progressColor
      return this.progressColor.colors[this.progressColor.colors.length - 1].color
    },
  },
  watch: {
    percent: {
      immediate: true,
      handler() {
        setTimeout(() => this.drawProgress(), 100)
      },
    },
    progressColor: {
      deep: true,
      handler() {
        setTimeout(() => this.drawProgress(), 100)
      },
    },
  },
  mounted() {
    setTimeout(() => this.drawProgress(), 100)
  },
  methods: {
    createGradient(ctx, width, height) {
      if (typeof this.progressColor === 'string') return this.progressColor

      const config = this.progressColor
      const start = config.start || [0, '50%']
      const end = config.end || ['100%', '50%']
      let gradient
      const type = config.type || 'linear'
      // 创建线性渐变
      if (type === 'linear') {
        const [x0, y0] = this.parseGradientPoint(start, width, height)
        const [x1, y1] = this.parseGradientPoint(end, width, height)
        gradient = ctx.createLinearGradient(x0, y0, x1, y1)
      }
      // 创建径向渐变
      else if (type === 'radial') {
        const [x1, y1] = this.parseGradientPoint(end, width, height)
        const centerX = x1 / 2
        const centerY = y1
        const radius = config.radius || width / 2
        gradient = ctx.createCircularGradient(centerX, centerY, radius)
      }

      // 添加色标
      config.colors.forEach((stop) => {
        gradient.addColorStop(stop.offset, stop.color)
      })

      return gradient
    },
    parseGradientPoint(point, width, height) {
      // 处理百分比坐标
      const parseValue = (val, max) => {
        if (typeof val === 'string' && val.endsWith('%')) {
          return (parseFloat(val) / 100) * max
        }
        return Number(val)
      }

      return [parseValue(point[0], width), parseValue(point[1], height)]
    },
    parseUnit(value) {
      if (typeof value === 'string') {
        const rpxMatch = value.match(/^(-?\d+(\.\d+)?)rpx$/)
        if (rpxMatch) {
          return uni.upx2px(parseFloat(rpxMatch[1]))
        }
        const pxMatch = value.match(/^(-?\d+(\.\d+)?)px$/)
        if (pxMatch) {
          return parseFloat(pxMatch[1])
        }
        return parseFloat(value)
      }
      return value
    },
    drawProgress() {
      const ctx = uni.createCanvasContext(`progressCanvas${this.index}`, this)
      const width = this.parsedWidth
      const height = this.parsedHeight
      const radius = width / 2 - this.strokeWidth
      const centerX = width / 2
      const centerY = height - this.strokeWidth / 2 // 调整圆心Y坐标

      // 清空画布
      ctx.clearRect(0, 0, width, height)

      // 绘制背景环
      ctx.beginPath()
      ctx.arc(centerX, centerY, radius, Math.PI, 0)
      ctx.setLineWidth(this.strokeWidth)
      ctx.setStrokeStyle(this.bgColor)
      ctx.stroke()

      // 创建渐变或使用纯色
      const progressStyle = this.createGradient(ctx, width, height)
      // 绘制进度环
      const progressAngle = Math.PI * (this.percent / 100)
      ctx.beginPath()
      ctx.arc(centerX, centerY, radius, Math.PI, Math.PI + progressAngle)
      ctx.setLineWidth(this.strokeWidth)
      ctx.setStrokeStyle(progressStyle)
      ctx.setLineCap('round')
      ctx.stroke()

      // 绘制末端小圆点
      const dotX = centerX + radius * Math.cos(Math.PI + progressAngle)
      const dotY = centerY + radius * Math.sin(Math.PI + progressAngle)
      // 先画白色描边
      ctx.beginPath()
      ctx.arc(dotX, dotY, this.strokeWidth / 2 + 1, 0, 2 * Math.PI) // 半径+1扩大描边区域
      ctx.setStrokeStyle('#ffffff') // 白色描边
      ctx.setLineWidth(2) // 描边宽度
      ctx.stroke()

      ctx.beginPath()
      ctx.arc(dotX, dotY, this.strokeWidth / 2, 0, 2 * Math.PI)
      ctx.setFillStyle(this.parsedDotColor)
      ctx.fill()

      ctx.draw()
    },
  },
}
</script>

<style scoped>
.progress-container {
  position: relative;
  width: v-bind(`${parsedWidth}px`);
}
.progress-canvas {
  display: block;
}
.progress-content {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  text-align: center;
}
</style>
