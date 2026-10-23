import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileSource } from './helpers/typescript.mjs'
import { computed, effectScope, nextTick, ref, watch } from 'vue'

const component = await readFile(new URL('../../web/app/components/layout/SiteHeader.vue', import.meta.url), 'utf8')
const source = component.split('<script setup lang="ts">')[1].split('</script>')[0]
  .replace("import { features, modules } from '~/data/home'", '')
const code = compileSource(`${source}\nglobalThis.headerState = { nickname, userInfo, userMenuOpen, fetchUserInfo }`)

test('退出通知早于 Cookie 同步时，导航栏仍及时移除旧昵称和账号菜单', async (t) => {
  const token = ref('old-token')
  const window = new EventTarget()
  const mounted = []
  const scope = effectScope()
  t.after(() => scope.stop())
  let valid = true
  const context = {
    window, ref, computed, watch, siteInfo: {},
    useCookie: (key) => key === 'web_token' ? token : ref(null),
    useRoute: () => ({ fullPath: '/' }), useHead() {},
    onMounted: (fn) => mounted.push(fn), onUnmounted() {},
    $fetch: async () => {
      if (!valid) throw new Error('unauthorized')
      return { code: 200, data: { nickname: '旧昵称' } }
    },
  }
  scope.run(() => vm.runInNewContext(code, context))
  for (const callback of mounted) callback()
  await context.headerState.fetchUserInfo()
  assert.equal(context.headerState.nickname.value, '旧昵称')
  context.headerState.userMenuOpen.value = true

  valid = false
  // 桥接先发通知，此时导航栏的 useCookie 还是旧值；随后 Nuxt 才同步 Cookie。
  window.dispatchEvent(new Event('auth:session-changed'))
  await nextTick()
  token.value = null
  await nextTick()
  assert.equal(context.headerState.nickname.value, '')
  assert.equal(context.headerState.userInfo.value, null)
  assert.equal(context.headerState.userMenuOpen.value, false)
})
