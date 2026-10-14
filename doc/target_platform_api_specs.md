# 目标题库平台接口结构与试卷数据模型规范

> **文档版本**：v1.0.0  
> **适用范围**：【公考内容排版】浏览器插件、适配器层（Adapters）、后端排版引擎（Render Engine）  
> **核心目标**：统一各大公考题库平台（粉笔、华图等）的试卷/错题接口调用方式与数据解析规范，建立中立标准的试卷模型。

---

## 目录
1. [架构全景与采集链路](#1-架构全景与采集链路)
2. [粉笔题库 (Fenbi) 接口结构深度解析](#2-粉笔题库-fenbi-接口结构深度解析)
   - [2.1 静态试卷包接口 (`/combine/static/exercise`)](#21-静态试卷包接口-combinestaticexercise)
   - [2.2 动态练习与做题接口 (`/combine/exercise/getExercise`)](#22-动态练习与做题接口-combineexercisegetexercise)
   - [2.3 错题重做与专项练习包](#23-错题重做与专项练习包)
   - [2.4 粉笔原始 JSON 数据模型定义](#24-粉笔原始-json-数据模型定义)
3. [中立归一化标准数据模型 (`UnifiedPaper`)](#3-中立归一化标准数据模型-unifiedpaper)
   - [3.1 数据字段映射对照表](#31-数据字段映射对照表)
   - [3.2 资料分析材料与题目的父子挂载算法](#32-资料分析材料与题目的父子挂载算法)
4. [后续平台扩展预研 (华图在线 / 中公教育)](#4-后续平台扩展预研-华图在线--中公教育)
5. [屏幕 DOM 通用兜底规范](#5-屏幕-dom-通用兜底规范)

---

## 1. 架构全景与采集链路

插件在目标题库网页上的运行机制为**双模自适应感知**：

```
[ 用户在粉笔/华图做题/查看错题 ]
               │
       ┌───────┴────────────────────────┐
       ▼                                ▼
【模式 1：网络层嗅探 (主)】        【模式 2：屏幕 DOM 提取 (兜底)】
  • Hook 原生 fetch / XHR           • 页面无完整接口请求时
  • 捕获粉笔原始 JSON 试卷包         • 提取屏幕已渲染的题干、选项、材料
       └───────┬────────────────────────┘
               ▼
     【平台适配器 Adapter 层】
  • adaptFenbiPaper() 数据清洗
  • 关联材料 (materials) 与题目 (questions)
  • 设问反向陷阱词智能加粗
               ▼
   【中立模型 UnifiedPaper】
               ▼
  【提交后端排版引擎或本地导出】
```

---

## 2. 粉笔题库 (Fenbi) 接口结构深度解析

粉笔网（`fenbi.com`）是国内公考行测/申论最大的在线做题平台。其试题系统基于单页应用（SPA）架构构建，试卷与做题数据主要通过以下两个核心接口下发：

### 2.1 静态试卷包接口 (`/combine/static/exercise`)

该接口用于下发真题试卷、万人模考、成套练习等大容量题目的静态预压缩数据包。

- **请求 URL**：`https://tiku.fenbi.com/combine/static/exercise?key={key}`
  - （或 CDN 形式：`//fb.fbstatic.cn/...`）
- **请求方式**：`GET`
- **请求头要求**：
  ```http
  Accept: application/json, text/plain, */*
  Referer: https://spa.fenbi.com/
  ```
- **鉴权模式**：通常为公开静态资源，无需强校验登录态，但需携带有效 `key` 参数。
- **返回特点**：包含整套试卷 100~135 道题的完整结构，速度快，CDN 缓存命中率高。

### 2.2 动态练习与做题接口 (`/combine/exercise/getExercise`)

该接口用于用户实时做题、智能组卷、专项刷题、消灭错题练习。

- **请求 URL**：`https://tiku.fenbi.com/combine/exercise/getExercise`
- **Query 参数**：
  - `key`：试卷或练习唯一标识（例如：`3_1_ju5`、`1_1_3s9bigl`）
  - `format`：固定为 `html`（使题干与选项返回带格式的富文本）
  - `routecs`：学科前缀，公考行测固定为 `xingce`，申论为 `shenlun`
- **请求方式**：`GET`
- **请求头要求**：
  ```http
  Accept: application/json, text/plain, */*
  Cookie: sid=...; userid=...; persistent=... (必须携带当前粉笔登录凭证)
  ```
- **返回特点**：实时动态生成，包含用户该次练习的作答进度、答题卡、错题标识。

### 2.3 错题本与错题解析真实接口体系 (实测最新)

粉笔错题本（`spa.fenbi.com/ti/error/...`）采用了**二级联动拉取架构**：

#### 接口 A：错题考点树接口 (`/api/xingce/errors/keypoint-tree`)
- **请求 URL**：`https://tiku.fenbi.com/api/xingce/errors/keypoint-tree`
- **Query 参数**：
  - `timeRange=0`：时间范围（全部错题）
  - `order=desc`：排序
  - `app=web&version=3.0.0.0`：客户端版本标识
- **请求方式**：`GET`（携带登录 Cookie）
- **核心作用**：下发用户的错题知识点树（常识、言语、数量等各考点下的错题数量），并在每个考点节点中包含该考点下的**错题 ID 列表 (`questionIds: [2776110, 2776104, ...]`)**。

#### 接口 B：错题批量解析与题目详情接口 (`/api/xingce/universal/auth/solutions`)
- **请求 URL**：`https://tiku.fenbi.com/api/xingce/universal/auth/solutions`
- **Query 参数**：
  - `type=1`：做题/解析类型
  - `questionIds`：逗号分隔的题目 ID 列表，例如：
    `questionIds=2776110,2776104,2776086,4874538,4874494,4742143,4740630,4740624,4740621,4654320`
  - `app=web&version=3.0.0.0`
- **请求方式**：`GET`（携带登录 Cookie）
- **核心作用**：**直接返回这批题目的完整数据**（题干富文本、选项 `accessories`、正确答案 `correctAnswer`、名师解析 `solution`、长篇材料 `material`）。

#### 业务破局点 1：错题全量聚合引擎（免翻页、免点击）
- **用户痛点**：粉笔网页端错题本每页仅展示 10 道题，考生若有 50 道错题需要翻页 5 次逐个查看，极难批量导出。
- **自动化突破机制**：
  1. 插件在错题目录页拦截 `keypoint-tree` 响应，递归提取全部错题 ID 数组（如获取到 45 个 `questionIds`）；
  2. 插件无需等待用户翻页，直接在后台按 15~20 题一组自动分片，携带 Cookie 并发请求 `/solutions?questionIds=...`；
  3. 将所有批次合并为一套完整的《粉笔个人错题专项集 (共45题)》；
  4. 达成**“用户停在错题首页，一键导出全量错题”**的颠覆性极简体验！

#### 业务破局点 2：试卷参考答案与解析反查补全引擎
- **用户痛点**：粉笔成套真题与模考卷（如 `/combine/static/exercise`）为了防作弊，默认只有题干和选项，不包含正确答案和解析。
- **自动化突破机制**：
  1. 提取试卷所有题目的全局整数 `question_id`；
  2. 利用用户当前登录凭据，主动调用 `/api/xingce/universal/auth/solutions?type=1&questionIds=...` 批量反查；
  3. 若试题已结卷或属于公课题库公开解析，接口将直接返回 `correctAnswer`（如 `"A"`）与 `solution` 富文本解析；
  4. 插件将答案无缝回填至试卷中，实现**“原本无答案的网页卷，一键排版输出附带标准答案卡与详细解析册”**！

#### 避坑要点：400 Bad Request 归因 (`key=error`)
- 历史版本中主动嗅探正则直接提取 URL 中的 `/error/` 作为 `key`，导致请求了 `getExercise?key=error`，引发粉笔服务端返回 `400 Bad Request`。
- **解决规范**：排除 `error`、`home`、`list` 等路径保留字，针对错题页面统一走 `keypoint-tree` / `solutions` 链路。

---

### 2.4 粉笔原始 JSON 数据模型定义

粉笔返回的数据包核心结构由四个顶层字段组成：`name`、`card`、`questions`、`materials`。

```json
{
  "name": "2026年国家公务员录用考试《行测》题（行政执法卷网友回忆版）",
  "materials": [
    {
      "id": 5367969,
      "globalId": "4_1_53q51",
      "tikuPrefix": "xingce",
      "content": "<p>为倡导团结合作精神，某单位举办了若干项目的双打比赛...</p>",
      "accessories": []
    }
  ],
  "questions": [
    {
      "id": 19526238,
      "globalId": "3_1_ijsiu",
      "tikuPrefix": "xingce",
      "content": "<p>习近平总书记强调，必须坚持自信自立...下列表述正确的有几项？</p>",
      "type": 1,
      "accessories": [
        {
          "type": 101,
          "options": [
            "1项",
            "2项",
            "3项",
            "4项"
          ]
        }
      ]
    }
  ],
  "card": {
    "nodeType": 0,
    "type": 2,
    "children": [
      {
        "nodeType": 1,
        "name": "常识判断",
        "desc": "根据题目要求，在四个选项中选出一个最恰当的答案。",
        "questionCount": 20,
        "children": [
          {
            "nodeType": 2,
            "key": "3_1_ijsiu",
            "materialKeys": []
          }
        ]
      },
      {
        "nodeType": 1,
        "name": "资料分析",
        "desc": "所给出的图、表、文字或综合性资料均有若干个问题要你回答...",
        "questionCount": 20,
        "children": [
          {
            "nodeType": 2,
            "key": "3_1_ijsi5",
            "materialKeys": [
              "4_1_50dqa"
            ]
          }
        ]
      }
    ]
  }
}
```

#### 关键字段释义：

| 字段路径 | 类型 | 说明与注意事项 |
| :--- | :--- | :--- |
| `name` | `string` | 试卷名称。错题时可能是 `公务员行测-浙江省考错题下载1题`。 |
| `card.children[]` | `array` | **大题模块清单**（如常识判断、言语理解、数量关系、判断推理、资料分析）。 |
| `card.children[].name` | `string` | 模块名称。若为错题本可能为 `null`，前端需兜底为 `专项模块`。 |
| `card.children[].desc` | `string` | 考场大题作答说明（考场卷重要组成部分）。 |
| `card.children[].children[]` | `array` | 该大题下的**小题索引节点**。 |
| `qNode.key` | `string` | 题目的唯一关联键（对应 `questions[].globalId` 或 `id`）。 |
| `qNode.materialKeys` | `array` | **长篇材料的关联键**（对应 `materials[].globalId`）。**资料分析 1 篇材料带 5 题即在此处绑定！** |
| `questions[]` | `array` | 试题列表。 |
| `questions[].content` | `string` | **题干富文本 HTML**（可能包含 `<p>`、`<img>`、`<span>` 等）。 |
| `questions[].type` | `number` | 题型：`1` 为单选题。 |
| `questions[].accessories[0].options` | `array<string>` | **选项文本数组**（长度通常为 4，分别对应 A、B、C、D）。 |
| `materials[]` | `array` | 资料分析/言语长文材料列表。`content` 包含长段落、统计图表等。 |

#### 图片 CDN 域名与协议补全说明：
粉笔图片通常采用无协议相对路径：
- `//fb.fbstatic.cn/api/tarzan/images/19ad3aadf19a22a.png?width=700`
- `//fb.fenbike.cn/...`
- **注意**：后端图片下载引擎必须自动补全 `https:` 协议前缀，否则会报网络下载协议错误。

---

## 3. 中立归一化标准数据模型 (`UnifiedPaper`)

为保证系统支持多题库（粉笔、华图、中公），前端适配器层将原始 JSON 清洗归一化为标准的 TypeScript / Python 模型：

```typescript
export interface UnifiedPaper {
  title: string               // 试卷名称 (如: 2026年国考行测真题)
  source_platform: 'fenbi' | 'huatu' | 'universal' // 来源平台
  total_questions: number     // 试题总数
  sections: UnifiedSection[]  // 模块结构
  metadata?: Record<string, any>
}

export interface UnifiedSection {
  name: string                // 模块名 (常识判断 / 言语理解等)
  description?: string        // 考场做题指引
  questions: UnifiedQuestion[]
}

export interface UnifiedQuestion {
  id: string | number         // 题目编号 / 唯一标识
  order_num: number           // 全卷统一题号 (1 ~ 135)
  type: 'single_choice' | 'multi_choice' | 'essay'
  stem: string                // 题干富文本 (已清洗)
  options: string[]           // 选项列表 ["选项A", "选项B", "选项C", "选项D"]
  answer?: string             // 参考答案 (做题卷留空)
  analysis?: string           // 解析 (做题卷留空)
  material?: string           // 绑定的背景材料 (资料分析/长篇阅读)
}
```

### 3.1 数据字段映射对照表

| 粉笔原始字段 | 转换清洗逻辑 | 标准中立字段 (`UnifiedQuestion`) |
| :--- | :--- | :--- |
| `raw.name` / `raw.title` | 去除特殊字符与多余空格 | `UnifiedPaper.title` |
| `raw.card.children[i].name` | 默认取值，若为空填补为 `专项模块` | `UnifiedSection.name` |
| `raw.card.children[i].desc` | 考场大题引导语 | `UnifiedSection.description` |
| 全局计数器 `globalOrder++` | 从 1 开始按考场顺序编号 | `UnifiedQuestion.order_num` |
| `rawQ.content` | 设问陷阱词（`不正确`/`属于`）反向加粗 | `UnifiedQuestion.stem` |
| `rawQ.accessories[0].options` | 提取数组清洗空格 | `UnifiedQuestion.options` |
| `materialMap.get(materialKey)` | 根据 `qNode.materialKeys` 匹配材料 | `UnifiedQuestion.material` |

---

## 4. 后续平台扩展预研 (华图在线 / 中公教育)

### 4.1 华图在线 (`v.huatu.com` / `huatu.com`)

- **典型做题接口**：
  - `GET https://v.huatu.com/api/v1/netschool/exercises/{id}`
  - `POST https://v.huatu.com/api/v1/tiku/paper/detail`
- **数据结构差异**：
  - 华图的选项通常封装在 `choices: [{"key": "A", "value": "..."}, ...]` 对象数组中；
  - 模块层级通常命名为 `categories` 或 `modules`；
  - 题干中公式常用 LaTeX 字符串或 MathJax 渲染；
- **适配方案**：
  - 在 `extension/src/adapters/huatu.ts` 中实现 `adaptHuatuPaper()`，只需输出标准 `UnifiedPaper`，后端排版引擎完全复用，无需重写排版。

---

## 5. 屏幕 DOM 通用兜底规范

当任何第三方网站修改了接口签名、开启了动态混淆加密时，插件启用**视口 DOM 智能提取引擎**作为最底层的通用保障：

- **题目容器选择器**：
  - `.exercise-item, .question-item, .ti-item, .wrong-item, .error-item, [data-question-id]`
- **题干选择器**：
  - `.stem, .question-content, .content, .desc, .question-stem`
- **选项选择器**：
  - `.options li, .option-item, .choice-item, .fb-option, .options .item`
- **材料选择器**：
  - `.material, .material-content, .material-box, .article-content`

**原则**：无论题库接口怎么防抓取，只要考生在屏幕上能看到做题内容，DOM 引擎就能 100% 提取并生成标准的考场 PDF 试卷！
