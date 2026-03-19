<template>
	<view class="myui-swiper" :style="{ borderRadius: radius + 'rpx' }">
		<wd-swiper
			:list="list"
			:indicator="indicator"
			:indicatorActiveColor="indicatorActiveColor"
			:indicatorInactiveColor="indicatorInactiveColor"
			:indicatorStyle="indicatorStyle"
			:indicatorMode="indicatorMode"
			:autoplay="autoplay"
			:current="current"
			:interval="interval"
			:duration="duration"
			:circular="circular"
			:previousMargin="previousMargin"
			:nextMargin="nextMargin"
			:height="height"
			:bgColor="bgColor"
			:radius="radius"
			:loading="loading"
			:keyName="keyName"
			:imgMode="imgMode"
			:showTitle="showTitle"
			@click="handleClick"
			@change="handleChange"
		>
			<template #default="{ item, index }">
				<slot :item="item" :index="index"></slot>
			</template>
			<template #indicator>
				<slot name="indicator"></slot>
			</template>
		</wd-swiper>
	</view>
</template>

<script>
/**
 * myui-swiper 轮播图
 * @description 基于 wot-design-uni 封装的轮播图组件，保持 FirstUI 风格
 * @property {Array} list 轮播图数据
 * @property {Boolean} indicator 是否显示指示器 (默认 true)
 * @property {String} indicatorActiveColor 指示器激活颜色 (默认 '#FFFFFF')
 * @property {String} indicatorInactiveColor 指示器非激活颜色 (默认 'rgba(255, 255, 255, 0.5)')
 * @property {String} indicatorMode 指示器模式 line/dot (默认 'line')
 * @property {Boolean} autoplay 是否自动播放 (默认 true)
 * @property {Number} current 当前索引 (默认 0)
 * @property {Number} interval 自动切换间隔 (默认 3000)
 * @property {Number} duration 切换动画时长 (默认 500)
 * @property {Boolean} circular 是否循环播放 (默认 true)
 * @property {Number} height 高度 (默认 300)
 * @property {Number} radius 圆角 (默认 16)
 * @property {String} bgColor 背景色 (默认 '#f3f4f6')
 * @property {String} keyName 图片字段名 (默认 'url')
 * @property {String} imgMode 图片裁剪模式 (默认 'aspectFill')
 * @event {Function} click 点击事件
 * @event {Function} change 切换事件
 */
export default {
	name: 'myui-swiper',
	emits: ['click', 'change', 'update:current'],
	props: {
		// 轮播数据
		list: {
			type: Array,
			default: () => []
		},
		// 是否显示指示器
		indicator: {
			type: Boolean,
			default: true
		},
		// 指示器激活颜色
		indicatorActiveColor: {
			type: String,
			default: '#FFFFFF'
		},
		// 指示器非激活颜色
		indicatorInactiveColor: {
			type: String,
			default: 'rgba(255, 255, 255, 0.5)'
		},
		// 指示器样式
		indicatorStyle: {
			type: [String, Object],
			default: ''
		},
		// 指示器模式 line/dot
		indicatorMode: {
			type: String,
			default: 'line'
		},
		// 是否自动播放
		autoplay: {
			type: Boolean,
			default: true
		},
		// 当前索引
		current: {
			type: Number,
			default: 0
		},
		// 自动切换间隔(ms)
		interval: {
			type: Number,
			default: 3000
		},
		// 切换动画时长(ms)
		duration: {
			type: Number,
			default: 500
		},
		// 是否循环播放
		circular: {
			type: Boolean,
			default: true
		},
		// 前边距
		previousMargin: {
			type: [String, Number],
			default: 0
		},
		// 后边距
		nextMargin: {
			type: [String, Number],
			default: 0
		},
		// 高度(rpx)
		height: {
			type: [String, Number],
			default: 300
		},
		// 背景色
		bgColor: {
			type: String,
			default: '#f3f4f6'
		},
		// 圆角(rpx)
		radius: {
			type: [String, Number],
			default: 16
		},
		// 是否加载中
		loading: {
			type: Boolean,
			default: false
		},
		// 图片字段名
		keyName: {
			type: String,
			default: 'url'
		},
		// 图片裁剪模式
		imgMode: {
			type: String,
			default: 'aspectFill'
		},
		// 是否显示标题
		showTitle: {
			type: Boolean,
			default: false
		}
	},
	methods: {
		handleClick(index) {
			this.$emit('click', index)
		},
		handleChange(e) {
			this.$emit('update:current', e.current)
			this.$emit('change', e)
		}
	}
}
</script>

<style scoped>
.myui-swiper {
	width: 100%;
	overflow: hidden;
}
</style>
