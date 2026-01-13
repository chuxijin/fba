<template>
	<view
		class="myui-notice-bar"
		v-if="show"
		:style="{ backgroundColor: bgColor }"
	>
		<template v-if="direction === 'column' || (direction === 'row' && step)">
			<myuiColumnNotice
				:color="color"
				:bgColor="bgColor"
				:text="textArray"
				:mode="mode"
				:step="step"
				:icon="icon"
				:disable-touch="disableTouch"
				:fontSize="fontSize"
				:duration="duration"
				:justifyContent="justifyContent"
				@close="close"
				@click="click"
			/>
		</template>
		<template v-else>
			<myuiRowNotice
				:color="color"
				:bgColor="bgColor"
				:text="textString"
				:mode="mode"
				:fontSize="fontSize"
				:speed="speed"
				:icon="icon"
				@close="close"
				@click="click"
			/>
		</template>
	</view>
</template>

<script>
import myuiRowNotice from '../myui-row-notice/myui-row-notice.vue'
import myuiColumnNotice from '../myui-column-notice/myui-column-notice.vue'

export default {
	name: 'myui-notice-bar',
	components: {
		myuiRowNotice,
		myuiColumnNotice
	},
	emits: ['click', 'close'],
	props: {
		// 显示内容（字符串或数组）
		text: {
			type: [Array, String],
			default: ''
		},
		// 滚动方向：row-横向，column-竖向
		direction: {
			type: String,
			default: 'row'
		},
		// 是否步进滚动
		step: {
			type: Boolean,
			default: false
		},
		// 左侧图标
		icon: {
			type: String,
			default: 'voice'
		},
		// 模式：link-右箭头，closable-关闭图标
		mode: {
			type: String,
			default: ''
		},
		// 文字颜色
		color: {
			type: String,
			default: '#f9ae3d'
		},
		// 背景颜色
		bgColor: {
			type: String,
			default: '#fdf6ec'
		},
		// 滚动速度 px/s（横向滚动时有效）
		speed: {
			type: [String, Number],
			default: 80
		},
		// 字体大小(px)
		fontSize: {
			type: [String, Number],
			default: 14
		},
		// 滚动周期 ms（竖向滚动时有效）
		duration: {
			type: [String, Number],
			default: 2000
		},
		// 禁止触摸滑动
		disableTouch: {
			type: Boolean,
			default: true
		},
		// 内容对齐方式
		justifyContent: {
			type: String,
			default: 'flex-start'
		},
		// 跳转链接
		url: {
			type: String,
			default: ''
		},
		// 跳转类型
		linkType: {
			type: String,
			default: 'navigateTo'
		}
	},
	data() {
		return {
			show: true
		}
	},
	computed: {
		// 确保 column 模式下是数组
		textArray() {
			if (Array.isArray(this.text)) return this.text
			return this.text ? [this.text] : []
		},
		// 确保 row 模式下是字符串
		textString() {
			if (typeof this.text === 'string') return this.text
			return Array.isArray(this.text) ? this.text.join(' ') : ''
		}
	},
	methods: {
		click(index) {
			this.$emit('click', index)
			if (this.url && this.linkType) {
				this.openPage()
			}
		},
		close() {
			this.show = false
			this.$emit('close')
		},
		openPage() {
			const url = this.url
			if (!url) return

			switch (this.linkType) {
				case 'navigateTo':
					uni.navigateTo({ url })
					break
				case 'redirectTo':
					uni.redirectTo({ url })
					break
				case 'switchTab':
					uni.switchTab({ url })
					break
				case 'reLaunch':
					uni.reLaunch({ url })
					break
				default:
					uni.navigateTo({ url })
			}
		}
	}
}
</script>

<style lang="scss" scoped>
.myui-notice-bar {
	display: flex;
	flex-direction: row;
	overflow: hidden;
	padding: 18rpx 24rpx;
	flex: 1;
	min-height: 60rpx;
	border-radius: 12rpx;
}
</style>
