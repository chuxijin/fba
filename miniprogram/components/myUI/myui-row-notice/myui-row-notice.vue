<template>
	<view class="myui-row-notice" @tap="clickHandler">
		<slot name="icon">
			<view class="myui-row-notice__left-icon" v-if="icon">
				<myuiIcon :name="icon" :color="color" size="38" unit="rpx" />
			</view>
		</slot>
		<view class="myui-row-notice__content" ref="myui-row-notice__content">
			<view
				ref="myui-row-notice__content__text"
				class="myui-row-notice__content__text"
				:style="[animationStyle]"
			>
				<text
					v-for="(item, index) in innerText"
					:key="index"
					:style="[textStyle]"
				>{{ item }}</text>
			</view>
		</view>
		<view class="myui-row-notice__right-icon" v-if="['link', 'closable'].includes(mode)">
			<myuiIcon
				v-if="mode === 'link'"
				name="right"
				size="34"
				unit="rpx"
				:color="color"
			/>
			<myuiIcon
				v-if="mode === 'closable'"
				name="close"
				size="32"
				unit="rpx"
				:color="color"
				@click="close"
			/>
		</view>
	</view>
</template>

<script>
import myuiIcon from '../myui-icon/myui-icon.vue'

export default {
	name: 'myui-row-notice',
	components: {
		myuiIcon
	},
	emits: ['click', 'close'],
	props: {
		// 显示的内容
		text: {
			type: String,
			default: ''
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
		// 字体大小(px)
		fontSize: {
			type: [String, Number],
			default: 14
		},
		// 滚动速度(px/s)
		speed: {
			type: [String, Number],
			default: 80
		}
	},
	data() {
		return {
			animationDuration: '0',
			animationPlayState: 'paused',
			stopAnimation: false
		}
	},
	computed: {
		textStyle() {
			return {
				whiteSpace: 'nowrap !important',
				color: this.color,
				fontSize: this.addUnit(this.fontSize)
			}
		},
		animationStyle() {
			return {
				animationDuration: this.animationDuration,
				animationPlayState: this.animationPlayState
			}
		},
		// 将长文本分割成多个 text 标签，解决低端安卓机动画抖动问题
		innerText() {
			if (!this.text || typeof this.text !== 'string') {
				return []
			}
			let result = []
			const len = 20
			const textArr = this.text.split('')
			for (let i = 0; i < textArr.length; i += len) {
				result.push(textArr.slice(i, i + len).join(''))
			}
			return result
		}
	},
	watch: {
		text: {
			immediate: true,
			handler() {
				this.initAnimation()
			}
		},
		fontSize() {
			this.initAnimation()
		},
		speed() {
			this.initAnimation()
		}
	},
	mounted() {
		this.initAnimation()
	},
	beforeUnmount() {
		this.stopAnimation = true
	},
	methods: {
		// 添加单位
		addUnit(value) {
			if (typeof value === 'string') return value
			return value + 'px'
		},
		// 获取元素尺寸
		getRect(selector) {
			return new Promise((resolve) => {
				uni.createSelectorQuery()
					.in(this)
					.select(selector)
					.boundingClientRect((rect) => {
						resolve(rect || { width: 0, height: 0 })
					})
					.exec()
			})
		},
		// 延时函数
		sleep(ms = 30) {
			return new Promise((resolve) => setTimeout(resolve, ms))
		},
		// 初始化动画
		async initAnimation() {
			await this.sleep(50)

			const textRect = await this.getRect('.myui-row-notice__content__text')
			const boxRect = await this.getRect('.myui-row-notice__content')

			if (!textRect || !boxRect) return

			const textWidth = textRect.width || 0
			const speed = Number(this.speed) || 80

			// 时间 = 路程 / 速度
			// padding-left: 100% 已经包含了盒子宽度，所以只需要计算文字宽度
			this.animationDuration = `${textWidth / speed}s`

			// 先暂停再播放，确保动画重新开始
			this.animationPlayState = 'paused'
			setTimeout(() => {
				this.animationPlayState = 'running'
			}, 10)
		},
		// 点击事件
		clickHandler() {
			this.$emit('click')
		},
		// 关闭事件
		close() {
			this.$emit('close')
		}
	}
}
</script>

<style lang="scss" scoped>
.myui-row-notice {
	display: flex;
	align-items: center;
	flex-direction: row;
	width: 100%;

	&__left-icon {
		display: flex;
		align-items: center;
		margin-right: 10rpx;
		flex-shrink: 0;
	}

	&__right-icon {
		display: flex;
		align-items: center;
		margin-left: 10rpx;
		flex-shrink: 0;
	}

	&__content {
		flex: 1;
		display: flex;
		flex-wrap: nowrap;
		overflow: hidden;

		&__text {
			font-size: 28rpx;
			color: #f9ae3d;
			padding-left: 100%;
			word-break: keep-all;
			white-space: nowrap;
			animation: myui-loop-animation 10s linear infinite both;
			display: flex;
			flex-direction: row;
		}
	}
}
</style>

<style lang="scss">
@keyframes myui-loop-animation {
	0% {
		transform: translate3d(0, 0, 0);
	}
	100% {
		transform: translate3d(-100%, 0, 0);
	}
}
</style>
