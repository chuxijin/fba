import fontBase64 from './myui-icon-base64.js'

let loaded = false

/**
 * 加载 myui 图标字体
 */
export function loadMyuiFont() {
	if (loaded) return

	// #ifdef MP-WEIXIN || MP-ALIPAY || H5
	uni.loadFontFace({
		global: true,
		family: 'fuiFont',
		source: `url("${fontBase64}")`,
		success() {
			loaded = true
			console.log('[myui-icon] 字体加载成功')
		},
		fail(err) {
			console.error('[myui-icon] 字体加载失败:', err)
		}
	})
	// #endif

	// #ifdef APP-NVUE
	const domModule = weex.requireModule('dom')
	domModule.addRule('fontFace', {
		fontFamily: 'fuiFont',
		src: `url('${fontBase64}')`
	})
	loaded = true
	// #endif
}

export default {
	loaded,
	loadMyuiFont
}
