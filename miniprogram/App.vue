<script>
// import { autoLogin } from '@/utils/auto-login'
// import { autoLoginConfig } from '@/config/dev'
import { useUserStore } from '@/stores/user'

const THEME_STORAGE_KEY = 'app-theme'
const DEFAULT_THEME = 'light'

export default {
	async onLaunch() {
		console.log('=== 应用启动 ===')

		// 应用主题
		const storedTheme = uni.getStorageSync(THEME_STORAGE_KEY) || DEFAULT_THEME
		this.applyTheme(storedTheme)

		// ❌ 开发环境自动登录（已禁用，使用真实微信登录）
		// try {
		// 	const loginSuccess = await autoLogin({
		// 		enabled: autoLoginConfig.enabled,
		// 		username: autoLoginConfig.defaultAccount.username,
		// 		nickname: autoLoginConfig.defaultAccount.nickname,
		// 		showToast: autoLoginConfig.showToast
		// 	})

		// 	if (loginSuccess) {
		// 		console.log('[App] 自动登录成功')
		// 	}
		// } catch (error) {
		// 	console.error('[App] 自动登录失败:', error)
		// }

		// ✅ 提前加载用户信息（不阻塞页面）
		const token = uni.getStorageSync('access_token')
		if (token) {
			const userStore = useUserStore()
			userStore.fetchUserInfo().catch(err => {
				console.error('[App] 加载用户信息失败:', err)
			})
		}

		console.log('=== 应用启动完成 ===')
	},
	onShow() {
		console.log('App Show')

		// ✅ App从后台恢复时，检查缓存是否过期
		const token = uni.getStorageSync('access_token')
		if (token) {
			const userStore = useUserStore()
			userStore.fetchUserInfo()  // 自动判断缓存
		}
	},
	onHide() {
		console.log('App Hide')
	},
	methods: {
		applyTheme(theme) {
			uni.setStorageSync(THEME_STORAGE_KEY, theme)
			if (typeof document !== 'undefined' && document.body) {
				document.body.setAttribute('data-theme', theme)
			}
		}
	}
}
</script>

<style lang="scss">
	/* ============ 导入设计系统 ============ */
	@import '@/styles/utilities.scss';

	/* ============ 全局字体配置 ============ */

	/* 全局默认字体 */
	page {
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
					 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
		font-size: 28rpx;
		line-height: 1.6;
		color: #333333;
		-webkit-font-smoothing: antialiased;
		-moz-osx-font-smoothing: grayscale;
	}

	/* ============ 全局隐藏滚动条 ============ */

	/* 隐藏所有滚动条 */
	::-webkit-scrollbar {
		display: none;
		width: 0;
		height: 0;
		color: transparent;
	}

	/* Firefox - 使用 page 选择器代替通配符 */
	page {
		scrollbar-width: none;
	}

	/* IE 10+ - 使用 page 选择器代替通配符 */
	page {
		-ms-overflow-style: none;
	}

	/* 确保 scroll-view 的滚动条也被隐藏 */
	scroll-view::-webkit-scrollbar {
		display: none;
		width: 0;
		height: 0;
	}

	/* ============ 隐藏 TabBar 上边框 ============ */

	/* 隐藏 TabBar 顶部横线 */
	uni-tabbar .uni-tabbar-border {
		display: none !important;
		height: 0 !important;
		background-color: transparent !important;
	}

	/* 兼容不同平台 */
	.uni-tabbar::before {
		display: none !important;
	}

	uni-tabbar::before {
		display: none !important;
	}

	/* 全局字体大小变量（微信小程序使用 page 代替 :root） */
	page {
		--font-size-xs: 20rpx;
		--font-size-sm: 24rpx;
		--font-size-base: 28rpx;
		--font-size-lg: 32rpx;
		--font-size-xl: 36rpx;
		--font-size-2xl: 40rpx;
		--font-size-3xl: 48rpx;

		--font-weight-light: 300;
		--font-weight-normal: 400;
		--font-weight-medium: 500;
		--font-weight-semibold: 600;
		--font-weight-bold: 700;
	}

	/* 标题字体 */
	view, text {
		font-family: inherit;
	}

	/*每个页面公共css */

	.u-body--locked {
		overflow: hidden;
		height: 100vh;
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		width: 100%;
	}

	/* ============ 练习题选项通用样式 ============ */

	/* 选项列表 */
	.option-list {
		display: flex;
		flex-direction: column;
		gap: 6rpx;
		padding: 0 4rpx;
	}

	/* 选项项 */
	.option-item {
		display: flex;
		align-items: center;
		gap: 12rpx;
		padding: 6rpx 8rpx;
		border-radius: 12rpx;
		border: 2rpx solid transparent;
		transition: background-color 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
	}

	/* 选项指示器（圆形） */
	.option-item__indicator {
		flex-shrink: 0;
		width: 48rpx;
		height: 48rpx;
		border-radius: 50%;
		border: 2rpx solid #cbd5f5;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #ffffff;
		transition: all 0.24s ease;
	}

	/* 选项指示器（方形 - 多选题） */
	.option-item__indicator--square {
		border-radius: 12rpx;
	}

	/* 选项字母 */
	.option-item__letter {
		font-size: 24rpx;
		font-weight: 600;
		color: #64748b;
	}

	/* 选项内容 */
	.option-item__content {
		flex: 1;
		font-size: 26rpx;
		color: var(--color-text-primary);
		line-height: 1.4;
	}

	/* 重置选项内 up-markdown 的间距 */
	.option-item__content :deep(.up-markdown),
	.option-item__content :deep(.markdown),
	.option-item__content :deep(p),
	.option-item__content :deep(div),
	.option-item__content :deep(span) {
		margin: 0 !important;
		padding: 8rpx !important;
		line-height: 1.4;
	}

	/* 选中状态 */
	.option-item--active {
		border-color: #3b82f6;
		background: linear-gradient(135deg, rgba(59, 130, 246, 0.12) 0%, rgba(37, 99, 235, 0.06) 100%);
		box-shadow: 0 2rpx 8rpx rgba(59, 130, 246, 0.15);
	}

	.option-item--active .option-item__indicator {
		border-color: #3b82f6;
		background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
		box-shadow: 0 2rpx 8rpx rgba(59, 130, 246, 0.3);
	}

	.option-item--active .option-item__letter {
		color: #ffffff;
		font-weight: 700;
	}

	.option-item--active .option-item__content {
		color: #1e40af;
		font-weight: 600;
	}

	/* 答对状态 */
	.option-item--correct {
		border-color: var(--color-success);
		background-color: var(--color-success-soft);
	}

	.option-item--correct .option-item__indicator {
		border-color: var(--color-success);
		background: var(--color-success);
	}

	.option-item--correct .option-item__letter {
		color: #ffffff;
	}

	/* 答错状态 */
	.option-item--wrong {
		border-color: var(--color-error);
		background-color: var(--color-error-soft);
	}

	.option-item--wrong .option-item__indicator {
		border-color: var(--color-error);
		background: var(--color-error);
	}

	.option-item--wrong .option-item__letter {
		color: #ffffff;
	}
</style>
