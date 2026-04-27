<script lang="ts" setup>
import type { PageData } from '@fba/api-sdk'
import { computed, getCurrentInstance, nextTick, ref, shallowRef, watch } from 'vue'
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { fbaApi } from '@/api/sdk'
import MembershipModal from '@/components/MembershipModal.vue'
import { useMembershipStore, useTokenStore } from '@/store'
import { echarts } from '@/utils/charts/echarts'
import { buildMembershipGrowthOption } from '@/utils/charts/membershipGrowth'
import { toLoginPage } from '@/utils/toLoginPage'

defineOptions({
  name: 'MembershipCenter',
})

definePage({
  style: {
    navigationStyle: 'custom',
    navigationBarTextStyle: 'white',
    navigationBarTitleText: '会员中心',
    usingComponents: {
      'ec-canvas': '/wxcomponents/ec-canvas/index',
    },
  },
})

const instance = getCurrentInstance()
const tokenStore = useTokenStore()
const membershipStore = useMembershipStore()
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()

interface UserMembershipBrief {
  family_code: string
  tier_id: number
  tier_code: string
  tier_name: string
  tier_grade: number
  tier_weight: number
  exp: number
  available_exp: number
  valid_from: string | null
  valid_to: string | null
  status: number
}

interface MembershipProgress {
  family_code: string
  tier_id: number | null
  tier_grade: number | null
  exp: number
  available_exp: number
  next_exp_required: number | null
}

interface MembershipTierBrief {
  id: number
  family_code: string
  code: string
  name: string
  grade: number
  exp_required: number
  weight: number
  is_default: boolean
}

interface MembershipPlanBrief {
  id: number
  name: string
  tier_id: number
  duration_days: number
  price: number
  original_price: number
  description: string | null
}

interface MembershipRecordBrief {
  family_code: string
  tier_id: number
  plan_id: number | null
  op_type: string
  days: number
  exp_delta: number
  source: string
  source_key: string
  valid_to_after: string | null
  created_time: string
}

const loading = ref(false)
const showMembershipModal = ref(false)
const selectedFamily = ref('')
const memberships = ref<UserMembershipBrief[]>([])
const progressList = ref<MembershipProgress[]>([])
const tiers = ref<MembershipTierBrief[]>([])
const plans = ref<MembershipPlanBrief[]>([])
const records = ref<MembershipRecordBrief[]>([])
const growthChart = shallowRef<any>(null)
const chartReady = ref(false)

const fallbackThresholds = [0, 240, 560, 1040, 1760, 2800, 4300, 6400, 9300, 13200]
const growthEc = {
  disableTouch: false,
  lazyLoad: true,
  onInit: initGrowthChart,
}

const hasLogin = computed(() => tokenStore.hasLogin)
const availableFamilies = computed(() => {
  const familyCodes = tiers.value
    .map(item => item.family_code)
    .filter(item => item && item !== 'FREE')
  const uniqueCodes = Array.from(new Set(familyCodes))
  if (uniqueCodes.length > 0) {
    return uniqueCodes
  }
  return ['VIP']
})
const familyLabel = computed(() => getFamilyLabel(currentFamily.value))
const currentFamily = computed(() => selectedFamily.value || availableFamilies.value[0] || 'VIP')
const isSvipFamily = computed(() => currentFamily.value.toUpperCase() === 'SVIP')
const canSwitchFamily = computed(() => availableFamilies.value.length > 1)
const memberTheme = computed(() => {
  if (isSvipFamily.value) {
    return {
      pageClass: 'from-[#1E1B4B] via-[#111827] to-[#030712]',
      glowPrimary: 'bg-[#FDE68A]/24',
      glowSecondary: 'bg-[#818CF8]/18',
      heroClass: 'border-[#FDE68A]/20 from-[#1E1B4B] via-[#111827] to-[#030712]',
      badgeClass: 'bg-[#1E1B4B] text-[#FDE68A] border border-[#FDE68A]/25',
      primaryButtonClass: 'bg-[#FDE68A] text-[#1E1B4B]',
      secondaryButtonClass: 'border border-[#FDE68A]/30 bg-[#FDE68A]/15 text-[#1E1B4B]',
      progressClass: 'from-[#FDE68A] to-[#A78BFA]',
      cardClass: 'border border-[#FDE68A]/12 bg-[#FBF7EA]',
      panelClass: 'from-white to-[#FFF7ED]',
      iconClass: 'bg-[#1E1B4B] text-[#FDE68A]',
      accentTextClass: 'text-[#B45309]',
      positiveTextClass: 'text-[#B45309]',
      chart: {
        primary: '#D97706',
        primarySoft: 'rgba(253, 230, 138, 0.42)',
        accent: '#1E1B4B',
        axis: '#EAD7A5',
        muted: '#D6C9A5',
      },
    }
  }

  return {
    pageClass: 'from-[#0F3B82] via-[#1E3A8A] to-[#0B1220]',
    glowPrimary: 'bg-[#DBEAFE]/22',
    glowSecondary: 'bg-[#FDE68A]/16',
    heroClass: 'border-[#DBEAFE]/18 from-[#0F3B82] via-[#172554] to-[#030712]',
    badgeClass: 'bg-[#0F3B82] text-[#DBEAFE] border border-[#DBEAFE]/25',
    primaryButtonClass: 'bg-[#DBEAFE] text-[#0F3B82]',
    secondaryButtonClass: 'border border-[#DBEAFE]/30 bg-[#DBEAFE]/15 text-[#0F3B82]',
    progressClass: 'from-[#DBEAFE] to-[#FDE68A]',
    cardClass: 'border border-[#DBEAFE]/14 bg-[#F8FBFF]',
    panelClass: 'from-white to-[#EFF6FF]',
    iconClass: 'bg-[#0F3B82] text-[#DBEAFE]',
    accentTextClass: 'text-[#1D4ED8]',
    positiveTextClass: 'text-[#0F3B82]',
    chart: {
      primary: '#1D4ED8',
      primarySoft: 'rgba(219, 234, 254, 0.46)',
      accent: '#B45309',
      axis: '#DBEAFE',
      muted: '#CBD5E1',
    },
  }
})
const familyTiers = computed(() => {
  const matchedTiers = tiers.value
    .filter(item => item.family_code === currentFamily.value)
    .sort((first, second) => first.grade - second.grade)

  if (matchedTiers.length > 0) {
    return matchedTiers
  }

  return fallbackThresholds.map((expRequired, index) => ({
    id: index + 1,
    family_code: currentFamily.value,
    code: `${currentFamily.value}_${index + 1}`,
    name: `${getFamilyLabel(currentFamily.value)} Lv.${index + 1}`,
    grade: index + 1,
    exp_required: expRequired,
    weight: index + 1,
    is_default: index === 0,
  }))
})
const activeMembership = computed(() => {
  const now = Date.now()
  return memberships.value.find((item) => {
    if (item.family_code !== currentFamily.value || item.status !== 1) {
      return false
    }
    if (!item.valid_to) {
      return true
    }
    return parseDate(item.valid_to) > now
  }) || null
})
const activeProgress = computed(() => {
  return progressList.value.find(item => item.family_code === currentFamily.value) || null
})
const totalExp = computed(() => activeProgress.value?.exp ?? activeMembership.value?.exp ?? 0)
const availableExp = computed(() => activeProgress.value?.available_exp ?? activeMembership.value?.available_exp ?? 0)
const currentTier = computed(() => {
  let matchedTier = familyTiers.value[0] || null
  for (const tier of familyTiers.value) {
    if (totalExp.value >= tier.exp_required) {
      matchedTier = tier
    }
  }
  return matchedTier
})
const nextTier = computed(() => {
  return familyTiers.value.find(item => item.exp_required > totalExp.value) || null
})
const currentLevelStartExp = computed(() => currentTier.value?.exp_required ?? 0)
const nextLevelExp = computed(() => nextTier.value?.exp_required ?? currentLevelStartExp.value)
const levelProgressPercent = computed(() => {
  const range = nextLevelExp.value - currentLevelStartExp.value
  if (range <= 0) {
    return 100
  }

  const current = totalExp.value - currentLevelStartExp.value
  return Math.min(100, Math.max(0, Math.round((current / range) * 100)))
})
const expireLabel = computed(() => formatDate(activeMembership.value?.valid_to))
const statusText = computed(() => {
  if (!activeMembership.value) {
    return '暂未开通'
  }
  if (!activeMembership.value.valid_to) {
    return '长期有效'
  }
  return `有效期至 ${expireLabel.value}`
})
const planRows = computed(() => {
  return plans.value
    .filter(item => item.duration_days > 0)
    .slice(0, 3)
})
const benefitRows = computed(() => [
  { icon: 'i-carbon-ai-status', title: 'AI 智能批改', desc: '主观题评分、解析和练习总结优先开放' },
  { icon: 'i-carbon-book', title: '高阶题库权益', desc: '适合后续扩展专属题库、资料和题本导出' },
  { icon: 'i-carbon-growth', title: '经验成长体系', desc: '签到、做题积累经验，等级越高可兑换空间越大' },
  { icon: 'i-carbon-headset', title: '专属服务入口', desc: '售后、权益激活和问题反馈更集中' },
])
const growthChartPoints = computed(() => {
  return familyTiers.value.map((tier) => {
    return {
      name: tier.name,
      grade: tier.grade,
      exp_required: tier.exp_required,
      reached: isTierReached(tier),
      active: currentTier.value?.id === tier.id,
    }
  })
})
const growthChartOption = computed(() => {
  return buildMembershipGrowthOption(growthChartPoints.value, totalExp.value, memberTheme.value.chart)
})

function initGrowthChart(canvas: any, width: number, height: number, dpr: number) {
  const chart = echarts.init(canvas, undefined, {
    width,
    height,
    devicePixelRatio: dpr,
    renderer: 'canvas',
  })
  canvas.setChart(chart)
  growthChart.value = chart
  chart.setOption({
    ...growthChartOption.value,
    animationDuration: 800,
    animationEasing: 'cubicOut',
  })
  return chart
}

function triggerGrowthChart() {
  if (chartReady.value) {
    return
  }
  chartReady.value = true

  // 等页面转场动画结束后再初始化图表
  setTimeout(() => {
    const proxy = instance?.proxy as any
    const ecComponent = proxy?.$scope?.selectComponent?.('#membership-growth-chart')
    if (ecComponent && typeof ecComponent.init === 'function') {
      ecComponent.init()
    }
  }, 350)
}

watch(growthChartOption, (option) => {
  if (!growthChart.value) {
    return
  }
  growthChart.value.setOption(option, true)
})

watch(showMembershipModal, (visible) => {
  if (!visible) {
    // 弹窗关闭后重新触发图表
    chartReady.value = false
    nextTick(() => triggerGrowthChart())
    return
  }
  growthChart.value = null
})

function ensureLogin() {
  tokenStore.updateNowTime()
  if (hasLogin.value) {
    return true
  }

  uni.showToast({ title: '请先登录后查看会员中心', icon: 'none' })
  setTimeout(() => {
    toLoginPage()
  }, 300)
  return false
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/mine/index' })
}

function parseDate(value?: string | null) {
  if (!value) {
    return 0
  }
  return new Date(value.replace(/-/g, '/')).getTime()
}

function formatDate(value?: string | null) {
  if (!value) {
    return '长期有效'
  }

  const date = new Date(value.replace(/-/g, '/'))
  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 10)
  }

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatPrice(value: number) {
  const price = Number(value || 0)
  if (price <= 0) {
    return '兑换激活'
  }

  return `¥${(price / 100).toFixed(2)}`
}

function hasPlanDiscount(plan: MembershipPlanBrief) {
  return Number(plan.original_price || 0) > Number(plan.price || 0) && Number(plan.price || 0) > 0
}

function getPlanDiscountLabel(plan: MembershipPlanBrief) {
  if (!hasPlanDiscount(plan)) {
    return ''
  }

  const discount = Math.round((Number(plan.price) / Number(plan.original_price)) * 10)
  return `${discount} 折`
}

function getPlanTag(plan: MembershipPlanBrief) {
  if (Number(plan.price || 0) <= 0) {
    return '兑换码'
  }
  if (hasPlanDiscount(plan)) {
    return getPlanDiscountLabel(plan)
  }
  return '参考价'
}

function getPlanDesc(plan: MembershipPlanBrief) {
  if (plan.description) {
    return plan.description
  }
  return `${plan.duration_days} 天会员权益，购买后使用订单号激活`
}

function getFamilyLabel(value: string) {
  const labelMap: Record<string, string> = {
    VIP: 'VIP',
    SVIP: 'SVIP',
    FREE: '普通会员',
  }
  return labelMap[value] || value
}

function getRecordTitle(item: MembershipRecordBrief) {
  const sourceMap: Record<string, string> = {
    check_in: '签到奖励',
    practice_correct: '刷题奖励',
  }
  if (sourceMap[item.source])
    return sourceMap[item.source]

  const titleMap: Record<string, string> = {
    open: '开通会员',
    add_days: '增加会员时长',
    reward_days: '奖励会员时长',
    exp_add: '获得经验',
    exp_consume: '消耗经验',
  }
  return titleMap[item.op_type] || '会员变动'
}

function getRecordDelta(item: MembershipRecordBrief) {
  if (item.exp_delta) {
    const prefix = item.exp_delta > 0 ? '+' : ''
    return `${prefix}${item.exp_delta} 经验`
  }
  if (item.days) {
    const prefix = item.days > 0 ? '+' : ''
    return `${prefix}${item.days} 天`
  }
  return '已记录'
}

function isTierReached(tier: MembershipTierBrief) {
  return totalExp.value >= tier.exp_required
}

function isMembershipActive(item: UserMembershipBrief) {
  if (item.status !== 1) {
    return false
  }
  if (!item.valid_to) {
    return true
  }
  return parseDate(item.valid_to) > Date.now()
}

function chooseFamily(familyCode: string) {
  if (selectedFamily.value === familyCode) {
    return
  }
  selectedFamily.value = familyCode
  void loadRecords()
}

function switchFamily() {
  if (!canSwitchFamily.value) {
    return
  }

  const currentIndex = availableFamilies.value.indexOf(currentFamily.value)
  const nextIndex = currentIndex >= 0 ? currentIndex + 1 : 0
  const nextFamily = availableFamilies.value[nextIndex % availableFamilies.value.length]
  chooseFamily(nextFamily)
}

async function loadRecords() {
  if (!hasLogin.value) {
    records.value = []
    return
  }

  try {
    const data = await fbaApi.membership.request.get<PageData<MembershipRecordBrief>>('/membership/me/records', {
      params: {
        page: 1,
        size: 8,
        family_code: currentFamily.value,
      },
    })
    records.value = data?.items || []
  }
  catch (error) {
    console.error('加载会员流水失败:', error)
    records.value = []
  }
}

async function loadData() {
  if (!ensureLogin()) {
    return
  }

  loading.value = true
  try {
    const [membershipData, progressData, tierData, planData] = await Promise.all([
      fbaApi.membership.request.get<UserMembershipBrief[]>('/membership/me'),
      fbaApi.membership.request.get<MembershipProgress[]>('/membership/me/progress'),
      fbaApi.membership.request.get<MembershipTierBrief[]>('/membership/tiers/active'),
      fbaApi.membership.request.get<MembershipPlanBrief[]>('/membership/plans/available'),
    ])

    memberships.value = membershipData || []
    progressList.value = progressData || []
    tiers.value = tierData || []
    plans.value = planData || []

    if (!selectedFamily.value || !availableFamilies.value.includes(selectedFamily.value)) {
      const paidMembership = memberships.value.find((item) => {
        return item.family_code !== 'FREE'
          && availableFamilies.value.includes(item.family_code)
          && isMembershipActive(item)
      })
      selectedFamily.value = paidMembership?.family_code || availableFamilies.value[0] || 'VIP'
    }

    await membershipStore.fetchMembership()
    await loadRecords()

    // 数据就绪后触发成长曲线动画
    triggerGrowthChart()
  }
  catch (error) {
    console.error('加载会员中心失败:', error)
    uni.showToast({ title: '会员信息加载失败', icon: 'none' })
  }
  finally {
    loading.value = false
  }
}

function openActivateModal() {
  if (!ensureLogin()) {
    return
  }
  showMembershipModal.value = true
}

onShow(() => {
  void loadData()
})

onPullDownRefresh(async () => {
  await loadData()
  uni.stopPullDownRefresh()
})
</script>

<template>
  <view class="relative min-h-screen overflow-hidden bg-gradient-to-b text-[#F8FAFC]" :class="memberTheme.pageClass">
    <view class="pointer-events-none absolute h-[360px] w-[360px] rounded-full blur-[60px] -right-24 -top-24" :class="memberTheme.glowPrimary" />
    <view class="pointer-events-none absolute top-44 h-[260px] w-[260px] rounded-full blur-[60px] -left-24" :class="memberTheme.glowSecondary" />

    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center rounded-full bg-white/10 active:opacity-70" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl" />
        </view>
        <text class="text-lg font-bold tracking-widest">
          会员中心
        </text>
        <view class="absolute right-4 text-[12px] text-[#FDE68A] font-bold" @click="openActivateModal">
          激活
        </view>
      </view>
    </view>

    <view class="relative z-10 px-4 pb-24 pt-4">
      <view class="relative overflow-hidden rounded-[30px] bg-gradient-to-br p-5 shadow-[0_18px_60px_-28px_rgba(0,0,0,0.8)]" :class="memberTheme.heroClass">
        <view class="absolute right-[-50px] top-[-70px] h-48 w-48 rounded-full bg-[#FDE68A]/15 blur-[8px]" />
        <view class="absolute bottom-[-80px] left-[-60px] h-44 w-44 rounded-full bg-[#38BDF8]/10 blur-[10px]" />
        <view class="relative">
          <view class="mb-5 flex items-start justify-between gap-4">
            <view>
              <view
                class="mb-2 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-bold tracking-[1px] active:scale-95"
                :class="memberTheme.badgeClass"
                @click="switchFamily"
              >
                <view class="i-carbon-trophy text-[13px]" />
                <text>{{ familyLabel }} 成长账户</text>
                <text v-if="canSwitchFamily" class="opacity-70">切换</text>
              </view>
              <view class="text-3xl font-black leading-tight" :class="isSvipFamily ? 'italic' : ''">
                {{ currentTier?.name || activeMembership?.tier_name || '未开通' }}
              </view>
              <view class="mt-1.5 text-[12px] text-[#CBD5E1]">
                {{ statusText }}
              </view>
            </view>
            <view class="shrink-0 text-right">
              <view class="text-[11px] text-[#94A3B8]">
                可用经验
              </view>
              <view class="mt-1 text-2xl font-black" :class="[memberTheme.accentTextClass, isSvipFamily ? 'italic' : '']">
                {{ availableExp }}
              </view>
            </view>
          </view>

          <view class="mt-4">
            <view class="mb-2 flex items-center justify-between text-[12px] text-[#CBD5E1]">
              <text>累计 {{ totalExp }} 经验</text>
              <text>{{ nextTier ? `距离 ${nextTier.name} 还差 ${Math.max(0, nextTier.exp_required - totalExp)} 经验` : '已达到最高等级' }}</text>
            </view>
            <view class="h-2.5 overflow-hidden rounded-full bg-white/10">
              <view
                class="h-full rounded-full bg-gradient-to-r transition-all duration-300"
                :class="memberTheme.progressClass"
                :style="{ width: `${levelProgressPercent}%` }"
              />
            </view>
          </view>

          <view class="mt-5 flex gap-3">
            <view class="h-11 flex flex-1 items-center justify-center rounded-2xl text-[13px] font-black active:scale-95" :class="memberTheme.primaryButtonClass" @click="openActivateModal">
              激活 / 续期会员
            </view>
            <view class="h-11 flex flex-1 items-center justify-center rounded-2xl text-[13px] font-bold" :class="memberTheme.secondaryButtonClass">
              {{ activeMembership ? '权益已生效' : '暂未开通权益' }}
            </view>
          </view>
        </view>
      </view>

      <view class="mt-4 rounded-[26px] p-4 text-[#0F172A]" :class="memberTheme.cardClass">
        <view class="mb-4 flex items-center justify-between">
          <view>
            <view class="text-lg font-black">
              成长曲线
            </view>
            <view class="mt-1 text-[12px] text-[#64748B]">
              非线性经验，越往后等级越稀缺
            </view>
          </view>
          <view class="rounded-full px-3 py-1 text-[11px] font-bold" :class="[memberTheme.badgeClass, isSvipFamily ? 'italic' : '']">
            {{ familyLabel }}
          </view>
        </view>

        <view class="overflow-hidden rounded-3xl bg-gradient-to-br px-2 pb-2 pt-3" :class="memberTheme.panelClass">
          <ec-canvas
            v-if="!showMembershipModal"
            id="membership-growth-chart"
            canvas-id="membership-growth-chart"
            class="block h-[220px] w-full"
            :echarts="echarts"
            :ec="growthEc"
          />
          <view
            v-else
            class="h-[220px] flex items-center justify-center rounded-3xl text-[12px] text-[#94A3B8] font-bold"
          >
            会员弹窗打开中
          </view>
        </view>
      </view>

      <view class="mt-4 rounded-[26px] p-4 text-[#0F172A]" :class="memberTheme.cardClass">
        <view class="mb-3 flex items-center justify-between">
          <view>
            <view class="text-lg font-black">
              核心权益
            </view>
            <view class="mt-1 text-[12px] text-[#64748B]">
              保持简单：会员只区分有无，权益统一维护
            </view>
          </view>
        </view>
        <view class="flex flex-col gap-2">
          <view
            v-for="benefit in benefitRows"
            :key="benefit.title"
            class="flex items-center gap-3 rounded-2xl bg-white/70 px-3 py-3"
          >
            <view class="h-9 w-9 shrink-0 flex items-center justify-center rounded-xl" :class="memberTheme.iconClass">
              <view :class="benefit.icon" class="text-[20px]" />
            </view>
            <view class="min-w-0 flex-1">
              <view class="text-[13px] font-black">
                {{ benefit.title }}
              </view>
              <view class="mt-0.5 truncate text-[11px] text-[#64748B]">
                {{ benefit.desc }}
              </view>
            </view>
          </view>
        </view>
      </view>

      <view class="mt-4 rounded-[26px] p-4 text-[#0F172A]" :class="memberTheme.cardClass">
        <view class="mb-4 flex items-end justify-between">
          <view>
            <view class="text-lg font-black">
              开通与记录
            </view>
            <view class="mt-1 text-[12px] text-[#64748B]">
              套餐用于展示参考，实际仍通过订单号激活
            </view>
          </view>
          <view class="rounded-full bg-white/70 px-3 py-1 text-[11px] font-bold" :class="memberTheme.accentTextClass">
            非直接支付
          </view>
        </view>

        <view v-if="planRows.length > 0" class="mb-4 flex flex-col gap-2">
          <view
            v-for="plan in planRows"
            :key="plan.id"
            class="flex items-center justify-between rounded-2xl border border-white/70 bg-white/75 px-3 py-3 active:scale-[0.99]"
            @click="openActivateModal"
          >
            <view class="min-w-0 flex-1">
              <view class="flex items-center gap-2">
                <view class="truncate text-[14px] font-black">
                  {{ plan.name }}
                </view>
                <view class="shrink-0 rounded-full bg-white px-2 py-0.5 text-[10px] text-[#92400E] font-bold">
                  {{ getPlanTag(plan) }}
                </view>
              </view>
              <view class="mt-1 truncate text-[11px] text-[#64748B]">
                {{ plan.duration_days }} 天权益 · {{ getPlanDesc(plan) }}
              </view>
            </view>
            <view class="ml-3 text-right">
              <view class="text-[16px] font-black" :class="memberTheme.accentTextClass">
                {{ formatPrice(plan.price) }}
              </view>
              <view v-if="hasPlanDiscount(plan)" class="mt-0.5 text-[10px] text-[#94A3B8] line-through">
                {{ formatPrice(plan.original_price) }}
              </view>
            </view>
          </view>
        </view>

        <view class="mb-3 flex items-center justify-between border-t border-[#F1F5F9] pt-4">
          <view class="text-[14px] font-black">
            最近变动
          </view>
          <view class="text-[12px] text-[#64748B]">
            {{ records.length }} 条
          </view>
        </view>

        <view v-if="records.length === 0" class="rounded-2xl bg-white/70 py-7 text-center text-[13px] text-[#94A3B8]">
          暂无会员流水，签到或激活后会显示在这里
        </view>
        <view v-else class="flex flex-col gap-2">
          <view
            v-for="record in records.slice(0, 5)"
            :key="`${record.source}-${record.source_key}-${record.created_time}`"
            class="flex items-center justify-between rounded-2xl bg-white/70 px-3 py-2.5"
          >
            <view>
              <view class="text-[13px] font-black">
                {{ getRecordTitle(record) }}
              </view>
              <view class="mt-0.5 text-[11px] text-[#64748B]">
                {{ formatDate(record.created_time) }}
              </view>
            </view>
            <view class="text-[13px] font-black" :class="memberTheme.positiveTextClass">
              {{ getRecordDelta(record) }}
            </view>
          </view>
        </view>
      </view>
    </view>

    <view v-if="loading" class="fixed inset-0 z-40 flex items-center justify-center bg-black/20">
      <view class="rounded-2xl bg-white px-5 py-3 text-[13px] text-[#0F172A] font-bold">
        加载会员信息...
      </view>
    </view>

    <MembershipModal v-model="showMembershipModal" @success="loadData" />
  </view>
</template>
