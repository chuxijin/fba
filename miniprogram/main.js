import App from './App'

// #ifndef VUE3
import Vue from 'vue'
import './uni.promisify.adaptor'
Vue.config.productionTip = false
App.mpType = 'app'
const app = new Vue({
  ...App
})
app.$mount()
// #endif

// #ifdef VUE3
import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import uviewPlus from 'uview-plus'

export function createApp() {
  const app = createSSRApp(App)
  const pinia = createPinia()

  app.use(pinia)

  // ✅ 配置 UView Plus
  app.use(uviewPlus, () => {
    return {
      options: {
        config: {
          // 图标字体只加载一次（减少网络请求）
          loadFontOnce: true
        }
      }
    }
  })

  return {
    app
  }
}
// #endif