# ProgressCircle 圆形进度条组件

基于 Canvas 实现的动态圆形进度条组件，支持渐变色、自定义尺寸及末端圆点样式。

## 特性

- 🎨 支持线性/径向渐变色进度条
- ⚙️ 自定义进度条宽度、颜色、尺寸
- 🔵 智能端点颜色适配
- 📱 自适应 rpx/px 单位
- 🖥 跨平台兼容（支持 UniApp 环境）

## 使用方法

```html
<!-- 1. 基础使用 -->
<l-progress-circle :percent="18" bg-color="#D2DBE1" progress-color="#f93d2f" width="134rpx" height="67rpx" />
<!-- 2. 线性渐变 -->
<l-progress-circle
  index="1"
  :strokeWidth="6"
  :percent="28"
  bg-color="#D2DBE1"
  :progress-color="{
      type: 'linear', // 可省略
      colors: [
        { offset: 0, color: '#ee7da2' },
        { offset: 1, color: '#a60525' }
      ]
    }"
  width="180rpx"
/>
<!-- 3. 径向渐变 -->
<l-progress-circle
  index="2"
  :strokeWidth="6"
  :percent="50"
  bg-color="#D2DBE1"
  :progress-color="{
       type: 'radial',
       colors: [
         { offset: 0, color: '#8847ff' },
         { offset: 1, color: '#6f7ca8' }
       ]
     }"
  width="180rpx"
/>
<!-- 4. 自定义内容 -->
<l-progress-circle index="3" :strokeWidth="8" :percent="88" progress-color="#3ba422" width="280rpx">
  <view class="text">
    <view>88/100</view>
    <view>合格数/总数</view>
  </view>
</l-progress-circle>
```

## Props 配置项

| 参数名        | 类型           | 默认值    | 必填 | 说明                                                                              | 验证规则                |
| ------------- | -------------- | --------- | ---- | --------------------------------------------------------------------------------- | ----------------------- |
| percent       | Number, String | 0         | 是   | 进度百分比（0-100）                                                               | 必须 ≥0 且 ≤100         |
| strokeWidth   | Number         | 4         | 否   | 进度条宽度（单位：px）                                                            | 无                      |
| bgColor       | String         | '#eeeeee' | 否   | 背景轨道颜色                                                                      | 必须是有效颜色值        |
| progressColor | String, Object | '#19be6b' | 否   | 进度条颜色（支持线性/径向渐变）                                                   | 渐变需传入对象,详见下表 |
| dotColor      | String         | -         | 否   | 末端圆点颜色（默认取 progressColor，如果是渐变默认取 progressColor 最后一个色值） | 无                      |
| width         | Number, String | 200       | 否   | 画布宽度（支持 rpx/px/无单位数值）                                                | 支持 CSS 单位转换       |
| height        | Number, String | width/2   | 否   | 画布高度（默认取宽度的一半）                                                      | 同 width 单位规则       |
| index         | Number, String | 0         | 否   | 画布唯一标识后缀（用于同一页面多个实例）                                          |

### progressColor 渐变对象

| 参数名 | 类型   | 默认值          | 必填 | 说明                                              |
| ------ | ------ | --------------- | ---- | ------------------------------------------------- |
| type   | String | linear          | 否   | 渐变类型（linear/radial）                         |
| start  | Array  | [0, '50%']      | 否   | 渐变起始坐标（[ x 坐标, y 坐标 ]）                |
| end    | Array  | ['100%', '50%'] | 否   | 渐变结束坐标（[ x 坐标, y 坐标 ]）                |
| colors | Array  | -               | 是   | 渐变颜色节点对象 {offset, color} offset 为 0 到 1 |
| radius | Number | width/2         | 否   | 径向渐变的半径长度                                |
