import type { MembershipBrief } from '@fba/api-sdk'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fbaApi } from '@/api/sdk'
import { useTokenStore } from './token'

export const useMembershipStore = defineStore(
  'membership',
  () => {
    const memberships = ref<MembershipBrief[]>([])
    const loading = ref(false)

    /** 当前最高权重的会员记录 */
    const activeMembership = computed(() => {
      const tokenStore = useTokenStore()
      if (!tokenStore.hasLogin) {
        return null
      }

      const now = Date.now()
      return memberships.value
        .filter(m => m.status === 1 && m.valid_to && new Date(m.valid_to.replace(/-/g, '/')).getTime() > now)
        .sort((a, b) => b.tier_weight - a.tier_weight)[0] || null
    })

    /** 是否为 VIP（任意生效会员） */
    const isVip = computed(() => !!activeMembership.value)

    /** 当前最高会员等级权重 */
    const maxTierWeight = computed(() => activeMembership.value?.tier_weight ?? 0)

    /** 当前会员等级名称 */
    const tierName = computed(() => activeMembership.value?.tier_name ?? '')

    /** 会员到期时间 */
    const validTo = computed(() => activeMembership.value?.valid_to ?? null)

    /** 拉取当前用户会员信息 */
    async function fetchMembership() {
      const tokenStore = useTokenStore()
      if (!tokenStore.hasLogin) {
        memberships.value = []
        return
      }

      loading.value = true
      try {
        memberships.value = await fbaApi.membership.getMyMembership()
      }
      catch (error) {
        console.error('获取会员信息失败:', error)
        memberships.value = []
      }
      finally {
        loading.value = false
      }
    }

    /** 清空会员信息 */
    function clearMembership() {
      memberships.value = []
    }

    /**
     * 检查当前用户等级权重是否满足要求
     *
     * :param requiredWeight: 最低等级权重
     * :return:
     */
    function checkLevel(requiredWeight: number): boolean {
      return maxTierWeight.value >= requiredWeight
    }

    return {
      memberships,
      loading,
      activeMembership,
      isVip,
      maxTierWeight,
      tierName,
      validTo,
      fetchMembership,
      clearMembership,
      checkLevel,
    }
  },
  {
    persist: true,
  },
)
