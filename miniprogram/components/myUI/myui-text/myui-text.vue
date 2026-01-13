<template>
	<view class="myui-text__wrap"
		:class="[block?'myui-text__block':'myui-text__inline','myui-text__'+align,highlight && !disable?'myui-text__active':'']"
		:style="{textAlign:align,paddingTop:padding[0] || 0,paddingRight:padding[1] || 0,paddingBottom:padding[2] || padding[0] || 0,paddingLeft:padding[3] || padding[1] || 0}"
		@tap="handleTap">
		<slot></slot>
		<!-- #ifndef APP-NVUE -->
		<text class="myui-text__content"
			:style="{color:getColor,fontSize:getSize,lineHeight:lineHeight?getSize:'auto',textAlign:align,textDecoration:decoration,fontWeight:fontWeight}"
			:class="[color?'':'myui-text__'+type,unShrink?'myui-text__unshrink':'']" :selectable="selectable"
			:userSelect="userSelect" :decode="decode">{{getText(text, textType, format)}}</text>
		<!-- #endif -->
		<!-- #ifdef APP-NVUE -->
		<view class="myui-text__nvue">
			<text class="myui-text__content"
				:style="{color:getColor,fontSize:getSize,lineHeight:lineHeight?getSize:'auto',textAlign:align,textDecoration:decoration,fontWeight:fontWeight}"
				:class="[color?'':'myui-text__'+type,unShrink?'myui-text__unshrink':'']" :userSelect="userSelect"
				:decode="decode">{{getText(text, textType, format)}}</text>
		</view>
		<!-- #endif -->
		<slot name="right"></slot>
	</view>
</template>

<script>
	export default {
		name: "myui-text",
		emits: ['click'],
		props: {
			//样式类型：primary，success， warning，danger，purple，gray，black
			type: {
				type: String,
				default: 'black'
			},
			text: {
				type: [Number, String],
				default: ''
			},
			size: {
				type: [Number, String],
				default: 0
			},
			unit: {
				type: String,
				default: ''
			},
			color: {
				type: String,
				default: ''
			},
			fontWeight: {
				type: [Number, String],
				default: 400
			},
			//left、center、right
			align: {
				type: String,
				default: 'left'
			},
			//none、 underline、line-through 
			decoration: {
				type: String,
				default: 'none'
			},
			//是否将行高设置与字体大小一致
			lineHeight: {
				type: Boolean,
				default: false
			},
			padding: {
				type: Array,
				default () {
					return ['0', '0']
				}
			},
			block: {
				type: Boolean,
				default: false
			},
			//文本类型：text、mobile、amount、name
			textType: {
				type: String,
				default: 'text'
			},
			//是否格式化，仅mobile、amount时有效
			format: {
				type: Boolean,
				default: false
			},
			call: {
				type: Boolean,
				default: false
			},
			//文本是否可选：nvue不支持，加此属性导致事件无法冒泡
			selectable: {
				type: Boolean,
				default: false
			},
			//文本是否可选：微信小程序
			userSelect: {
				type: Boolean,
				default: false
			},
			//是否解码：App、H5、微信小程序
			decode: {
				type: Boolean,
				default: false
			},
			//是否有点击效果
			highlight: {
				type: Boolean,
				default: false
			},
			disable: {
				type: Boolean,
				default: false
			},
			unShrink: {
				type: Boolean,
				default: false
			},
			param: {
				type: [Number, String],
				default: ''
			}
		},
		computed: {
			getSize() {
				const size = (uni && uni.$fui && uni.$fui.fuiText && uni.$fui.fuiText.size) || 32
				const unit = (uni && uni.$fui && uni.$fui.fuiText && uni.$fui.fuiText.unit) || 'rpx'
				return (this.size || size) + (this.unit || unit)
			},
			getColor() {
				let color = this.color || ''
				// #ifdef APP-NVUE
				if (!color && this.type) {
					const app = uni && uni.$fui && uni.$fui.color;
					const text = uni && uni.$fui && uni.$fui.fuiText;
					color = {
						primary: (app && app.primary) || '#465CFF',
						success: (app && app.success) || '#09BE4F',
						warning: (app && app.warning) || '#FFB703',
						danger: (app && app.danger) || '#FF2B2B',
						purple: (app && app.purple) || '#6831FF',
						gray: '#B2B2B2',
						black: (text && text.color) || '#181818'
					} [this.type]
				}
				// #endif
				return color
			}
		},
		methods: {
			getText(text, textType, format) {
				let _text = text
				if (format) {
					if (textType === 'mobile') {
						_text = this.numberFormatter(text)
					} else if (textType === 'amount') {
						_text = this.moneyFormatter(text)
					} else if (textType === 'name') {
						_text = this.nameFormatter(text)
					}
				}
				return _text
			},
			numberFormatter(num) {
				return num.length === 11 ? num.replace(/^(\d{3})\d{4}(\d{4})$/, '$1****$2') : num;
			},
			moneyFormatter(money) {
				return parseFloat(money).toFixed(2).toString().split('').reverse().join('').replace(/(\d{3})/g, '$1,')
					.replace(
						/\,$/, '').split('').reverse().join('');
			},
			trimAll(value) {
				return value.toString().replace(/\s+/g, "")
			},
			nameFormatter(name) {
				let _name = this.trimAll(name || '')
				if (_name && _name.length >= 2) {
					const arr = _name.split('')
					_name = arr[0] + '*'
					if (arr.length > 2) {
						_name = _name + arr[arr.length - 1]
					}
				}
				return _name
			},
			handleTap() {
				if (this.disable) return;
				this.$emit('click', {
					text: this.text,
					param: this.param
				})
				if (this.call) {
					uni.makePhoneCall({
						phoneNumber: this.text,
						success: function() {},
						fail: function() {}
					})
				}
			}
		}
	}
</script>

<style scoped>
	.myui-text__wrap {
		align-items: center;
		flex-direction: row;
	}

	/* #ifdef H5 */
	.myui-text__active {
		cursor: pointer;
	}

	/* #endif */

	.myui-text__active:active {
		opacity: .5;
	}

	/* #ifndef APP-NVUE */
	.myui-text__inline {
		display: inline-flex;
	}

	.myui-text__block {
		display: flex;
	}

	.myui-text__unshrink {
		flex-shrink: 0;
	}

	.myui-text__content {
		word-break: break-all;
	}

	/* #endif */

	/* #ifdef APP-NVUE */
	.myui-text__nvue {
		flex: 1;
	}

	/* #endif */

	.myui-text__center {
		justify-content: center;
	}

	.myui-text__right {
		justify-content: flex-end;
	}

	/* #ifndef APP-NVUE */
	.myui-text__primary {
		color: var(--myui-color-primary, #465CFF) !important;
	}

	.myui-text__success {
		color: var(--myui-color-success, #09BE4F) !important;
	}

	.myui-text__warning {
		color: var(--myui-color-warning, #FFB703) !important;
	}

	.myui-text__danger {
		color: var(--myui-color-danger, #FF2B2B) !important;
	}

	.myui-text__purple {
		color: var(--myui-color-purple, #6831FF) !important;
	}

	.myui-text__gray {
		color: var(--myui-color-label, #B2B2B2) !important;
	}

	.myui-text__black {
		color: var(--myui-color-title, #181818) !important;
	}

	/* #endif */
</style>