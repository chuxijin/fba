# TabBar 图标准备指南

## 📋 图标规格要求

根据**微信小程序设计规范**和**腾讯 CoDesign 设计规范**：

- **尺寸**：81×81px（推荐）
- **格式**：PNG（带透明通道）
- **文件大小**：< 40KB（每个图标）
- **色彩模式**：RGB
- **数量**：8 个图标（4 个未选中 + 4 个选中）

---

## 🎨 设计要求

### 1. 图标风格
- **线性图标**或**面性图标**（推荐线性，更现代）
- **统一风格**：所有图标必须使用相同的设计风格
- **简洁清晰**：在小尺寸下也能清晰识别
- **语义明确**：图标含义一目了然

### 2. 颜色规范

根据您的设计系统（`styles/design-tokens.scss`）：

**未选中状态**：
- 颜色：`#6b7280`（中性灰）
- 示例：![#6b7280](https://via.placeholder.com/15/6b7280/6b7280.png) `#6b7280`

**选中状态**：
- 颜色：`#22c55e`（品牌绿）
- 示例：![#22c55e](https://via.placeholder.com/15/22c55e/22c55e.png) `#22c55e`

---

## 📁 所需图标清单

需要准备以下 **8 个图标文件**：

| 文件名 | 图标语义 | 状态 | 颜色 | 参考图标 |
|--------|---------|------|------|---------|
| `home.png` | 首页 - 房子 | 未选中 | #6b7280 | 🏠 |
| `home-active.png` | 首页 - 房子 | 选中 | #22c55e | 🏠 |
| `practice.png` | 练习 - 铅笔/题目 | 未选中 | #6b7280 | ✏️ |
| `practice-active.png` | 练习 - 铅笔/题目 | 选中 | #22c55e | ✏️ |
| `study.png` | 学习 - 书本/图表 | 未选中 | #6b7280 | 📚 |
| `study-active.png` | 学习 - 书本/图表 | 选中 | #22c55e | 📚 |
| `mine.png` | 我的 - 用户头像 | 未选中 | #6b7280 | 👤 |
| `mine-active.png` | 我的 - 用户头像 | 选中 | #22c55e | 👤 |

**存放位置**：`miniprogram/static/tabbar/`

---

## 🛠️ 获取图标的三种方式

### **方式 1：使用 Iconfont（推荐）**

Iconfont 是阿里巴巴旗下的图标平台，提供海量免费图标。

**步骤**：

1. 访问 [iconfont.cn](https://www.iconfont.cn/)
2. 搜索关键词：
   - 首页：搜索 "home" 或 "房子"
   - 练习：搜索 "edit" 或 "铅笔"
   - 学习：搜索 "book" 或 "学习"
   - 我的：搜索 "user" 或 "用户"

3. 选择统一风格的图标（推荐选择同一作者的图标集）
4. 下载 PNG 格式（81×81px）
5. 使用图片编辑工具修改颜色：
   - 未选中版本：改为 `#6b7280`
   - 选中版本：改为 `#22c55e`

**推荐图标库**：
- [Ant Design Icons](https://www.iconfont.cn/collections/detail?spm=a313x.7781069.1998910419.d9df05512&cid=9402)
- [Element UI Icons](https://www.iconfont.cn/collections/detail?spm=a313x.7781069.1998910419.d9df05512&cid=11803)

---

### **方式 2：使用 IconPark（字节跳动）**

IconPark 提供高质量的开源图标库。

**步骤**：

1. 访问 [IconPark](https://iconpark.oceanengine.com/official)
2. 搜索并选择图标
3. 下载 PNG 格式（81×81px）
4. 修改颜色（同方式 1）

---

### **方式 3：自行设计（Figma/Sketch）**

如果���有设计能力，可以使用 Figma 或 Sketch 自行设计：

**Figma 快速设计流程**：

1. 创建 81×81px 画布
2. 使用钢笔工具绘制图标（线宽推荐 2px）
3. 应用颜色：
   - 未选中：`#6b7280`
   - 选中：`#22c55e`
4. 导出为 PNG（2x 分辨率）

---

## 🎯 临时方案：使用��色占位图

如果暂时没有准备好图标，可以使用纯色占位图先让 TabBar 运行起来。

**快速生成占位图**：

访问以下链接下载占位图（右键保存）：

1. **首页**：
   - 未选中：[home.png](https://via.placeholder.com/81/6b7280/6b7280.png?text=H)
   - 选中：[home-active.png](https://via.placeholder.com/81/22c55e/22c55e.png?text=H)

2. **练习**：
   - 未选中：[practice.png](https://via.placeholder.com/81/6b7280/6b7280.png?text=P)
   - 选中：[practice-active.png](https://via.placeholder.com/81/22c55e/22c55e.png?text=P)

3. **学习**：
   - 未选中：[study.png](https://via.placeholder.com/81/6b7280/6b7280.png?text=S)
   - 选中：[study-active.png](https://via.placeholder.com/81/22c55e/22c55e.png?text=S)

4. **我的**：
   - 未选中：[mine.png](https://via.placeholder.com/81/6b7280/6b7280.png?text=M)
   - 选���：[mine-active.png](https://via.placeholder.com/81/22c55e/22c55e.png?text=M)

**或者使用在线工具生成**：
- [Placeholder.com](https://placeholder.com/)
- [DummyImage](https://dummyimage.com/)

---

## ✅ 安装图标

将准备好的 8 个图标文件放入：

```
miniprogram/static/tabbar/
├── home.png              (81×81px, #6b7280)
├── home-active.png       (81×81px, #22c55e)
├── practice.png          (81×81px, #6b7280)
├── practice-active.png   (81×81px, #22c55e)
├── study.png             (81×81px, #6b7280)
├── study-active.png      (81×81px, #22c55e)
├── mine.png              (81×81px, #6b7280)
└── mine-active.png       (81×81px, #22c55e)
```

---

## 🧪 测试 TabBar

图标安装完成后，重新编译项目：

```bash
# 如果使用 HBuilderX，点击"运行" → "运行到小程序模拟器"
# 或使用命令行
npm run dev:mp-weixin
```

在微信开发者工具中查看 TabBar 效果：
- ✅ 图标清晰可见
- ✅ 切换页面时图标颜色变化正常
- ✅ 文本颜色符合设计规范（未选中 #6b7280，选中 #22c55e）

---

## 📚 参考资料

- [微信小程序 TabBar 配置文档](https://developers.weixin.qq.com/miniprogram/dev/reference/configuration/app.html#tabBar)
- [腾讯 CoDesign 设计规范](https://codesign.qq.com/hc/article/design-system-mini-program/)
- [Iconfont 使用指南](https://www.iconfont.cn/help/detail?spm=a313x.7781069.1998910419.d8d11a391&helptype=code)
- [IconPark 官方文档](https://iconpark.oceanengine.com/docs/introduction)

---

## 💡 设计建议

### 推荐的图标语义

| Tab | 推荐图标 | 备选图标 |
|-----|---------|---------|
| 首页 | 房子（home）| 星标（star）、仪表盘（dashboard） |
| 练习 | 铅笔（edit）| 试卷（document）、刷题（refresh） |
| 学习 | 书本（book）| 图表（chart）、趋势（trending） |
| 我的 | 用户（user）| 个人（profile）、设置（settings） |

### 设计原则

1. **保持一致**：所有图标使用相��的线宽、圆角、风格
2. **清晰简洁**：避免过于复杂的细节
3. **尺寸适配**：确保在 81×81px 下清晰可辨
4. **颜色对比**：确保与背景有足够对比度

---

**需要帮助？**

如果在准备图标过程中遇到问题，可以：
1. 使用临时占位图先让功能跑起来
2. 后续再替换为精美的图标
3. 咨询设计师协助设计符合品牌调性的图标
