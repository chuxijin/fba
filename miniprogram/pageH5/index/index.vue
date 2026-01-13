<template>
  <div class="h5-home-page">
    <!-- H5 自定义导航栏 -->
    <div class="h5-navbar">
      <div class="navbar-content">
        <h1 class="app-title">刷题助手</h1>
        <div class="navbar-actions">
          <button v-if="!isLoggedIn" class="btn-login" @click="handleLogin">登录</button>
          <div v-else class="user-info" @click="goToProfile">
            <span>{{ userNickname }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- H5 轮播图 - 使用标准 HTML 结构 -->
    <div v-if="bannerImages.length > 0" class="h5-banner-section">
      <div class="banner-container">
        <div class="banner-slider" :style="{ transform: `translateX(-${currentBannerIndex * 100}%)` }">
          <div
            v-for="(banner, index) in bannerImages"
            :key="index"
            class="banner-item"
            @click="handleBannerClick(index)"
          >
            <img :src="banner" alt="Banner" />
          </div>
        </div>
        <div class="banner-indicators">
          <span
            v-for="(_, index) in bannerImages"
            :key="index"
            class="indicator"
            :class="{ active: currentBannerIndex === index }"
            @click="currentBannerIndex = index"
          ></span>
        </div>
      </div>
    </div>

    <!-- H5 通知栏 -->
    <div v-if="noticeText" class="h5-notice-section">
      <div class="notice-content">
        <span class="notice-icon">📢</span>
        <div class="notice-text-wrapper">
          <p class="notice-text">{{ noticeText }}</p>
        </div>
      </div>
    </div>

    <!-- H5 功能导航 - 卡片式布局 -->
    <div class="h5-function-grid">
      <div
        v-for="func in functionItems"
        :key="func.id"
        class="function-card"
        @click="handleFunctionClick(func)"
      >
        <div class="card-icon" :style="{ background: func.bgColor }">
          <span>{{ func.icon }}</span>
        </div>
        <h3 class="card-title">{{ func.label }}</h3>
      </div>
    </div>

    <!-- H5 数据统计卡片 -->
    <div v-if="isLoggedIn" class="h5-stats-section">
      <h2 class="section-title">学习统计</h2>
      <div class="stats-grid">
        <div v-for="stat in statsData" :key="stat.id" class="stat-card">
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
      </div>
    </div>

    <!-- H5 推荐题库 -->
    <div class="h5-recommend-section">
      <h2 class="section-title">推荐题库</h2>
      <div class="recommend-grid">
        <div
          v-for="bank in recommendBanks"
          :key="bank.id"
          class="recommend-card"
          @click="goToBankDetail(bank.id)"
        >
          <div class="card-header">
            <h3 class="bank-name">{{ bank.name }}</h3>
            <span class="bank-category">{{ bank.category }}</span>
          </div>
          <div class="card-body">
            <p class="bank-desc">{{ bank.description }}</p>
            <div class="bank-stats">
              <span>📝 {{ bank.questionCount }} 题</span>
              <span>👥 {{ formatCount(bank.practiceCount) }} 人练习</span>
            </div>
          </div>
          <div class="card-footer">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${bank.progress}%` }"></div>
            </div>
            <span class="progress-text">{{ bank.progress }}% 完成</span>
          </div>
        </div>
      </div>
    </div>

    <!-- H5 底部信息 -->
    <div class="h5-footer">
      <p>© 2024 刷题助手 All Rights Reserved</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

// 类型定义
interface FunctionItem {
  id: string
  icon: string
  label: string
  bgColor: string
  route?: string
}

interface ProgressBank {
  id: number
  name: string
  category: string
  description: string
  questionCount: number
  practiceCount: number
  progress: number
}

// 响应式数据
const isLoggedIn = ref(false)
const userNickname = ref('用户')
const noticeText = ref('欢迎使用刷题助手 H5 版本！')
const currentBannerIndex = ref(0)

const bannerImages = ref([
  'https://via.placeholder.com/1200x400/4ade80/ffffff?text=Banner+1',
  'https://via.placeholder.com/1200x400/22c55e/ffffff?text=Banner+2',
  'https://via.placeholder.com/1200x400/16a34a/ffffff?text=Banner+3'
])

const functionItems = ref<FunctionItem[]>([
  {
    id: 'activate',
    icon: '⚡',
    label: '快速激活',
    bgColor: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)'
  },
  {
    id: 'intro',
    icon: '📚',
    label: '题库介绍',
    bgColor: 'linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)'
  },
  {
    id: 'steps',
    icon: '📋',
    label: '激活步骤',
    bgColor: 'linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%)'
  },
  {
    id: 'all-banks',
    icon: '📖',
    label: '全部题库',
    bgColor: 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)',
    route: '/pageH5/practice/index'
  }
])

const statsData = ref([
  { id: 'total', value: '1,234', label: '累计刷题' },
  { id: 'week', value: '156', label: '本周刷题' },
  { id: 'correct', value: '89%', label: '正确率' },
  { id: 'rank', value: '23%', label: '击败用户' }
])

const recommendBanks = ref<ProgressBank[]>([
  {
    id: 1,
    name: '计算机二级 Python',
    category: '计算机考试',
    description: '全国计算机等级考试二级 Python 语言程序设计题库',
    questionCount: 500,
    practiceCount: 12345,
    progress: 45
  },
  {
    id: 2,
    name: '初级会计职称',
    category: '会计考试',
    description: '初级会计专业技术资格考试题库，包含经济法基础和会计实务',
    questionCount: 800,
    practiceCount: 8765,
    progress: 20
  }
])

// 轮播图自动播放
let bannerTimer: number | null = null

onMounted(() => {
  startBannerAutoPlay()
})

const startBannerAutoPlay = () => {
  bannerTimer = window.setInterval(() => {
    currentBannerIndex.value = (currentBannerIndex.value + 1) % bannerImages.value.length
  }, 3000)
}

const handleLogin = () => {
  console.log('H5 登录')
}

const goToProfile = () => {
  console.log('H5 个人中心')
}

const handleBannerClick = (index: number) => {
  console.log('H5 Banner 点击', index)
}

const handleFunctionClick = (func: FunctionItem) => {
  if (func.route) {
    console.log('H5 跳转', func.route)
  } else {
    console.log('H5 功能', func.id)
  }
}

const goToBankDetail = (bankId: number) => {
  console.log('H5 题库详情', bankId)
}

const formatCount = (count: number): string => {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万`
  }
  return count.toString()
}
</script>

<style scoped lang="scss">
.h5-home-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 60px;
}

/* ============ H5 导航栏 ============ */
.h5-navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

  .navbar-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .app-title {
      font-size: 24px;
      font-weight: 700;
      color: #22c55e;
      margin: 0;
    }

    .navbar-actions {
      .btn-login {
        padding: 8px 24px;
        background: #22c55e;
        color: #fff;
        border: none;
        border-radius: 20px;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.3s;

        &:hover {
          background: #16a34a;
        }
      }

      .user-info {
        padding: 8px 16px;
        background: #f0fdf4;
        border-radius: 20px;
        color: #22c55e;
        font-size: 14px;
        cursor: pointer;
      }
    }
  }
}

/* ============ H5 轮播图 ============ */
.h5-banner-section {
  max-width: 1200px;
  margin: 24px auto;
  padding: 0 24px;

  .banner-container {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 6;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);

    .banner-slider {
      display: flex;
      height: 100%;
      transition: transform 0.5s ease;

      .banner-item {
        min-width: 100%;
        cursor: pointer;

        img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
      }
    }

    .banner-indicators {
      position: absolute;
      bottom: 16px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      gap: 8px;

      .indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.5);
        cursor: pointer;
        transition: all 0.3s;

        &.active {
          background: #22c55e;
          width: 24px;
          border-radius: 4px;
        }
      }
    }
  }
}

/* ============ H5 通知栏 ============ */
.h5-notice-section {
  max-width: 1200px;
  margin: 0 auto 24px;
  padding: 0 24px;

  .notice-content {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #fef3c7;
    border-radius: 8px;

    .notice-icon {
      font-size: 20px;
    }

    .notice-text-wrapper {
      flex: 1;
      overflow: hidden;

      .notice-text {
        margin: 0;
        font-size: 14px;
        color: #92400e;
        white-space: nowrap;
        animation: scroll-text 15s linear infinite;
      }
    }
  }
}

/* ============ H5 功能导航 ============ */
.h5-function-grid {
  max-width: 1200px;
  margin: 0 auto 32px;
  padding: 0 24px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;

  .function-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    cursor: pointer;
    transition: all 0.3s;

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    }

    .card-icon {
      width: 64px;
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 16px;
      font-size: 32px;
      margin-bottom: 12px;
    }

    .card-title {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
      color: #374151;
    }
  }
}

/* ============ H5 统计卡片 ============ */
.h5-stats-section {
  max-width: 1200px;
  margin: 0 auto 32px;
  padding: 0 24px;

  .section-title {
    font-size: 20px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 16px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;

    .stat-card {
      padding: 24px;
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      text-align: center;

      .stat-value {
        font-size: 32px;
        font-weight: 700;
        color: #22c55e;
        margin-bottom: 8px;
      }

      .stat-label {
        font-size: 14px;
        color: #6b7280;
      }
    }
  }
}

/* ============ H5 推荐题库 ============ */
.h5-recommend-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;

  .section-title {
    font-size: 20px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 16px;
  }

  .recommend-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 20px;

    .recommend-card {
      padding: 20px;
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      cursor: pointer;
      transition: all 0.3s;

      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;

        .bank-name {
          font-size: 18px;
          font-weight: 600;
          color: #1f2937;
          margin: 0;
        }

        .bank-category {
          padding: 4px 12px;
          background: #dbeafe;
          color: #1e40af;
          font-size: 12px;
          border-radius: 12px;
        }
      }

      .card-body {
        margin-bottom: 16px;

        .bank-desc {
          font-size: 14px;
          color: #6b7280;
          line-height: 1.6;
          margin-bottom: 12px;
        }

        .bank-stats {
          display: flex;
          gap: 16px;
          font-size: 13px;
          color: #9ca3af;

          span {
            display: flex;
            align-items: center;
            gap: 4px;
          }
        }
      }

      .card-footer {
        display: flex;
        align-items: center;
        gap: 12px;

        .progress-bar {
          flex: 1;
          height: 6px;
          background: #f3f4f6;
          border-radius: 3px;
          overflow: hidden;

          .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
            border-radius: 3px;
            transition: width 0.3s;
          }
        }

        .progress-text {
          font-size: 12px;
          color: #22c55e;
          font-weight: 500;
          white-space: nowrap;
        }
      }
    }
  }
}

/* ============ H5 底部 ============ */
.h5-footer {
  max-width: 1200px;
  margin: 48px auto 0;
  padding: 24px;
  text-align: center;

  p {
    margin: 0;
    font-size: 14px;
    color: #9ca3af;
  }
}

/* ============ 动画 ============ */
@keyframes scroll-text {
  0% {
    transform: translateX(100%);
  }
  100% {
    transform: translateX(-100%);
  }
}

/* ============ 响应式 ============ */
@media (max-width: 768px) {
  .h5-function-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .h5-recommend-section .recommend-grid {
    grid-template-columns: 1fr;
  }

  .h5-stats-section .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
