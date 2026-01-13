<template>
	<view class="myui-column-notice" @tap="clickHandler">
		<slot name="icon">
			<view class="myui-column-notice__left-icon" v-if="icon">
				<myuiIcon :name="icon" :color="color" size="38" unit="rpx" />
			</view>
		</slot>
		<swiper
			:disable-touch="disableTouch"
			:vertical="!step"
			circular
			:interval="duration"
			:autoplay="true"
			class="myui-column-notice__swiper"
			@change="noticeChange"
		>
			<swiper-item
				v-for="(item, index) in textList"
				:key="index"
				class="myui-column-notice__swiper__item"
				:style="{ justifyContent: justifyContent }"
			>
				<text
					class="myui-column-notice__swiper__item__text"
					:style="[textStyle]"
				>{{ item }}</text>
			</swiper-item>
		</swiper>
		<view class="myui-column-notice__right-icon" v-if="['link', 'closable'].includes(mode)">
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
	name: 'myui-column-notice',
	components: {
		myuiIcon
	},
	emits: ['click', 'close'],
	props: {
		// 显示内容（数组）
		text: {
			type: Array,
			default: () => []
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
		// 是否步进滚动
		step: {
			type: Boolean,
			default: false
		},
		// 滚动周期(ms)
		duration: {
			type: [String, Number],
			default: 2000
		},
		// 禁止触摸
		disableTouch: {
			type: Boolean,
			default: true
		},
		// 内容对齐方式
		justifyContent: {
			type: String,
			default: 'flex-start'
		}
	},
	data() {
		return {
			index: 0
		}
	},
	computed: {
		textStyle() {
			return {
				color: this.color,
				fontSize: this.addUnit(this.fontSize)
			}
		},
		textList() {
			return Array.isArray(this.text) ? this.text : []
		}
	},
	methods: {
		addUnit(value) {
			if (typeof value === 'string') return value
			return value + 'px'
		},
		noticeChange(e) {
			this.index = e.detail.current
		},
		clickHandler() {
			this.$emit('click', this.index)
		},
		close() {
			this.$emit('close')
		}
	}
}
</script>

<style lang="scss" scoped>
.myui-column-notice {
	display: flex;
	flex-direction: row;
	align-items: center;
	justify-content: space-between;

	&__left-icon {
		display: flex;
		align-items: center;
		margin-right: 10rpx;
	}

	&__right-icon {
		display: flex;
		align-items: center;
		margin-left: 10rpx;
	}

	&__swiper {
		height: 32rpx;
		display: flex;
		align-items: center;
		flex: 1;

		&__item {
			display: flex;
			align-items: center;
			overflow: hidden;

			&__text {
				font-size: 28rpx;
				color: #f9ae3d;
				overflow: hidden;
				text-overflow: ellipsis;
				white-space: nowrap;
			}
		}
	}
}
</style>
