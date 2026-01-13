<template>
	<!-- #ifndef APP-NVUE -->
	<text :style="{ color:getColor, fontSize: getSize, fontWeight: fontWeight}" class="myui-icon"
		:class="[!getColor && !primary?'myui-icon__color':'',primary && (!color || color===true)?'myui-icon__active-color':'',disabled?'myui-icon__not-allowed':'',customPrefix && customPrefix!==true?customPrefix:'',customPrefix && customPrefix!==true?name:'']"
		@click="handleClick">{{ icons[name] || '' }}</text>
	<!-- #endif -->
	<!-- #ifdef APP-NVUE -->
	<text
		:style="{ color: primary && (!color || color===true)?primaryColor:getColor, fontSize: getSize,lineHeight:getSize, fontWeight: fontWeight}"
		class="myui-icon" :class="[customPrefix && customPrefix!==true?customPrefix:'']"
		@click="handleClick">{{ customPrefix  && customPrefix!==true?name:icons[name] }}</text>
	<!-- #endif -->
</template>

<script>
	import icons from './myui-icon.js';
	// #ifdef APP-NVUE
	var domModule = weex.requireModule('dom');
	import fuiicons from './myui-icon.ttf'
	domModule.addRule('fontFace', {
		'fontFamily': 'fuiFont',
		'src': "url('" + fuiicons + "')"
	});
	// #endif

	export default {
		name: "myui-icon",
		emits: ['click'],
		// #ifdef MP-WEIXIN
		options: {
			addGlobalClass: true
		},
		// #endif
		props: {
			name: {
				type: String,
				default: ''
			},
			size: {
				type: [Number, String],
				default: 0
			},
			//rpx | px
			unit: {
				type: String,
				default: ''
			},
			color: {
				type: String,
				default: ''
			},
			//字重
			fontWeight: {
				type: [Number, String],
				default: 'normal'
			},
			//是否禁用点击
			disabled: {
				type: Boolean,
				default: false
			},
			params: {
				type: [Number, String],
				default: 0
			},
			customPrefix: {
				type: String,
				default: ''
			},
			//是否显示为主色调，color为空时有效。【内部使用】
			primary: {
				type: Boolean,
				default: false
			}
		},
		computed: {
			getSize() {
				// 使用直接默认值，不依赖全局配置
				const defaultSize = 64
				const defaultUnit = 'rpx'
				return (this.size || defaultSize) + (this.unit || defaultUnit)
			},
			primaryColor() {
				return '#465CFF'
			},
			getColor() {
				let color = this.color
				// 如果没有传入颜色，使用默认颜色
				if (!color || color === true) {
					color = '#333333'
				}
				return color
			}
		},
		data() {
			return {
				icons: icons
			};
		},
		methods: {
			handleClick() {
				if (this.disabled) return;
				this.$emit('click', {
					params: this.params
				});
			}
		}
	}
</script>

<style scoped>
	.myui-icon {
		font-family: fuiFont;
		text-decoration: none;
		text-align: center;
		/* #ifdef H5 */
		cursor: pointer;
		/* #endif */
	}

	/* #ifndef APP-NVUE */
	.myui-icon__color {
		color: var(--myui-color-section, #333333) !important;
	}

	.myui-icon__active-color {
		color: var(--myui-color-primary, #465CFF) !important;
	}

	/* #endif */

	.myui-icon__not-allowed {
		/* #ifdef H5 */
		cursor: not-allowed !important;
		/* #endif */
	}
</style>

<!-- 字体声明必须放在非 scoped 样式中，否则小程序无法加载 -->
<style>
	/* #ifndef APP-NVUE */
	@font-face {
		font-family: fuiFont;
		src: url("./myui-icon.ttf") format("truetype");
	}
	/* #endif */
</style>