import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/sdk'
import { useMembershipStore } from './membership'

// 初始化状态
const userInfoState: any = {
  id: -1,
  userId: -1,
  username: '',
  nickname: '',
  avatar: '/static/images/default-avatar.png',
}

export const useUserStore = defineStore(
  'user',
  () => {
    // 定义用户信息
    const userInfo = ref<any>({ ...userInfoState })
    // 设置用户信息
    const setUserInfo = (val: any) => {
      console.log('设置用户信息', val)
      // 若头像为空 则使用默认头像
      const normalizedUserId = Number(val?.id || val?.userId || -1)
      userInfo.value = {
        ...val,
        id: normalizedUserId > 0 ? normalizedUserId : -1,
        userId: normalizedUserId > 0 ? normalizedUserId : -1,
        avatar: val?.avatar || userInfoState.avatar,
      }
    }
    const setUserAvatar = (avatar: string) => {
      userInfo.value.avatar = avatar
      console.log('设置用户头像', avatar)
      console.log('userInfo', userInfo.value)
    }
    // 删除用户信息
    const clearUserInfo = () => {
      userInfo.value = { ...userInfoState }
      uni.removeStorageSync('user')
      // 同步清空会员信息
      const membershipStore = useMembershipStore()
      membershipStore.clearMembership()
    }

    /**
     * 获取用户信息
     */
    const fetchUserInfo = async () => {
      const { data: res } = await api.getCurrentUserInfo() as any
      setUserInfo(res)
      // 同步拉取会员信息
      const membershipStore = useMembershipStore()
      void membershipStore.fetchMembership()
      return res
    }

    return {
      userInfo,
      clearUserInfo,
      fetchUserInfo,
      setUserInfo,
      setUserAvatar,
    }
  },
  {
    persist: true,
  },
)
