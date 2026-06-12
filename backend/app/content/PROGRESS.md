# 行测知识点内容生产进度

> 最后更新：2026-06-11

## 总览

| 模块 | 分类节点数 | 已有内容 | 今日新增 | 待写 | 状态 |
|------|-----------|---------|---------|------|------|
| 判断推理 > 图形推理 | 31 | 0 | **32** | 0 | ✅ 完成 |
| 判断推理 > 定义判断 | 5 | 0 | **5** | 0 | ✅ 完成 |
| 判断推理 > 类比推理 | 21 | 0 | **21** | 0 | ✅ 完成 |
| 判断推理 > 逻辑推理 | 10 | 0 | **10** | 0 | ✅ 完成 |
| 言语理解与表达 | 22 | 0 | **22** | 0 | ✅ 完成 |
| 数量关系 | 111 | ~350 | **3** | 0 | ✅ 完成 |
| 资料分析 | 24 | 19 | **5** | 0 | ✅ 完成 |
| 常识判断 | 9 | 0 | **9** | 0 | ✅ 完成 |
| 政治理论 | 1 | 0 | **1** | 0 | ✅ 完成 |

## 今日完成（2026-06-11）

### 一、图形推理分类树重构
- [x] 二级分类：5 → 7（新增功能规律、其他规律；空间重构改名立体空间）
- [x] 三级分类：0 → 24（对齐华图/粉笔行业标准）
- [x] sys_category 新增节点：id 1403-1428

### 二、图形推理内容（32 篇 SQL seed）

#### L1 总览（1 篇）✅
- [x] `kp_xc_tutui_overview.sql` — 图形推理总览（知识体系、三秒识别法、解题流程）

#### L2 概述（7 篇）✅
- [x] `kp_xc_tutui_pos_overview.sql` — 位置规律概述
- [x] `kp_xc_tutui_style_overview.sql` — 样式规律概述
- [x] `kp_xc_tutui_qty_overview.sql` — 数量规律概述
- [x] `kp_xc_tutui_prop_overview.sql` — 属性规律概述
- [x] `kp_xc_tutui_spatial_overview.sql` — 立体空间概述
- [x] `kp_xc_tutui_func_overview.sql` — 功能规律概述
- [x] `kp_xc_tutui_other_overview.sql` — 其他规律概述

#### L3 知识点详解（24 篇）✅

**数量规律（6 篇）**
- [x] `kp_xc_tutui_qty_point.sql` — 点（交点、曲直交点、内外交点）
- [x] `kp_xc_tutui_qty_line.sql` — 线（直线、曲线、笔画数/奇点法）
- [x] `kp_xc_tutui_qty_angle.sql` — 角（锐角、直角、钝角）
- [x] `kp_xc_tutui_qty_face.sql` — 面（封闭区域、阴影面积）
- [x] `kp_xc_tutui_qty_element.sql` — 素（元素个数、种类、部分数）
- [x] `kp_xc_tutui_qty_calc.sql` — 数量运算（点线面素加减乘除）

**位置规律（2 篇）**
- [x] `kp_xc_tutui_pos_dynamic.sql` — 动态位置（平移、旋转、翻转）
- [x] `kp_xc_tutui_pos_static.sql` — 静态位置（结构、排列、连接）

**样式规律（2 篇）**
- [x] `kp_xc_tutui_style_op.sql` — 运算（加减同异、黑白运算）
- [x] `kp_xc_tutui_style_traverse.sql` — 遍历（缺啥补啥）

**属性规律（3 篇）**
- [x] `kp_xc_tutui_prop_symmetry.sql` — 对称性（轴对称、中心对称）
- [x] `kp_xc_tutui_prop_curve.sql` — 曲直性（全直、全曲）
- [x] `kp_xc_tutui_prop_open_close.sql` — 开闭性（开放、封闭）

**立体空间（6 篇）**
- [x] `kp_xc_tutui_spatial_cube.sql` — 六面体（折纸盒、公共边法）
- [x] `kp_xc_tutui_spatial_tetra.sql` — 四面体（展开图）
- [x] `kp_xc_tutui_spatial_section.sql` — 截面图（正方体/圆柱截面）
- [x] `kp_xc_tutui_spatial_projection.sql` — 三视图（主/俯/侧）
- [x] `kp_xc_tutui_spatial_assemble.sql` — 立体拼合
- [x] `kp_xc_tutui_spatial_planar.sql` — 平面拼合

**功能规律（3 篇）**
- [x] `kp_xc_tutui_func_point.sql` — 功能点（标记位置）
- [x] `kp_xc_tutui_func_line.sql` — 功能线（头尾方向）
- [x] `kp_xc_tutui_func_arrow.sql` — 功能箭头（指向方向）

**其他规律（2 篇）**
- [x] `kp_xc_tutui_other_pattern.sql` — 其他图形规律（汉字、字母）
- [x] `kp_xc_tutui_other_entity.sql` — 实体信息（文字属性）

### 三、定义判断分类树重构
- [x] 删除 8 个 L6 节点（单定义下的解题方法节点 + 多定义下的"并列定义"）
- [x] 改名 2 个节点（包含定义 → 区别型，匹配类定义 → 匹配型）
- [x] 从 13 个节点精简到 5 个节点

### 四、定义判断内容（5 篇 SQL seed）
- [x] `kp_xc_definition_overview.sql` — 定义判断总览（知识体系、关键词拆解法）
- [x] `kp_xc_definition_single.sql` — 单定义判断（关键词拆解、逐一对照、排除法）
- [x] `kp_xc_definition_multi_overview.sql` — 多定义判断概述（区别型与匹配型）
- [x] `kp_xc_definition_multi_distinguish.sql` — 区别型（锁定目标定义、忽略干扰）
- [x] `kp_xc_definition_multi_matching.sql` — 匹配型（特征词提取、对号入座）

## 待办

### 四、类比推理分类树重构
- [x] 改名 2 个 L5（逻辑关系→外延关系，对应关系→内涵关系）
- [x] 移动 2 个 L6（属性关系、条件关系从外延关系→内涵关系）
- [x] 改名 1 个 L6（种属关系→包容关系）
- [x] 删除 10 个节点（组成关系 + 对应关系下 9 个 L6）
- [x] 新增 2 个节点（全异关系、构词）
- [x] 从 29 个节点精简到 21 个节点

### 五、类比推理内容（21 篇 SQL seed）
- [x] L1 总览：类比推理总览（知识体系、解题三步法、造句法）
- [x] L2 概述×4：外延关系、内涵关系、语义关系、语法关系
- [x] L3 详解×16：全同、并列、交叉、包容、全异、属性、条件、近义、反义、比喻义、象征义、主谓、动宾、主宾、偏正、构词

### 六、逻辑推理分类树重构
- [x] 删除 16 个 L6 + 35 个 L7 = 51 个节点（解题方法混入的旧节点）
- [x] 新增 7 个 L6 节点：翻译推理、真假推理、集合推理、分析推理、论证、日常推理、平行结构
- [x] 从 54 个节点精简到 10 个节点
- [x] 保留 2 个 L5：形式逻辑、论证推理

### 七、逻辑推理内容（10 篇 SQL seed）

#### L1 总览（1 篇）✅
- [x] `kp_xc_logic_overview.sql` — 逻辑推理总览（知识体系、三秒识别法、解题流程）

#### L2 概述（2 篇）✅
- [x] `kp_xc_logic_formal_overview.sql` — 形式逻辑概述（翻译推理、真假推理、集合推理、分析推理）
- [x] `kp_xc_logic_argumentation_overview.sql` — 论证推理概述（论证、日常推理、平行结构）

#### L3 知识点详解（7 篇）✅

**形式逻辑（4 篇）**
- [x] `kp_xc_logic_formal_translation.sql` — 翻译推理（如果…那么…、逆否命题）
- [x] `kp_xc_logic_formal_truth.sql` — 真假推理（矛盾关系、一真一假）
- [x] `kp_xc_logic_formal_set.sql` — 集合推理（所有/有些、欧拉图）
- [x] `kp_xc_logic_formal_analytical.sql` — 分析推理（排除法、假设法、列表法）

**论证推理（3 篇）**
- [x] `kp_xc_logic_argumentation_main.sql` — 论证（削弱/加强/前提、力度比较）
- [x] `kp_xc_logic_argumentation_daily.sql` — 日常推理（日常逻辑推断）
- [x] `kp_xc_logic_argumentation_parallel.sql` — 平行结构（论证方式匹配）

### 判断推理完成
- [x] 图形推理（32 篇）✅
- [x] 定义判断（5 篇）✅
- [x] 类比推理（21 篇）✅
- [x] 逻辑推理（10 篇）✅

### 八、数据库清理
- [x] 删除 18 条旧 sys_content 记录（关联到已删除的分类节点）
- [x] 删除 34 个旧 sys_category 节点：定义判断 8 个、类比推理 10 个、逻辑推理 16 个

### 九、言语理解分类树重构
- [x] 删除 58 个 L6 节点（辨析角度/解题技巧混入的旧节点）
- [x] 从 80 个节点精简到 22 个节点（-72%）
- [x] 保留 4 个 L4 + 18 个 L5

### 十、言语理解内容（22 篇 SQL seed）

#### L4 概述（4 篇）✅
- [x] `kp_xc_lang_cloze_overview.sql` — 逻辑填空概述
- [x] `kp_xc_lang_passage_overview.sql` — 篇章阅读概述
- [x] `kp_xc_lang_sentence_overview.sql` — 语句表达概述
- [x] `kp_xc_lang_reading_overview.sql` — 片段阅读概述

#### L5 详解（18 篇）✅

**逻辑填空（4 篇）**
- [x] `kp_xc_lang_cloze_real_word.sql` — 实词辨析
- [x] `kp_xc_lang_cloze_idiom.sql` — 成语辨析
- [x] `kp_xc_lang_cloze_function_word.sql` — 虚词辨析
- [x] `kp_xc_lang_cloze_comprehensive.sql` — 综合辨析

**篇章阅读（5 篇）**
- [x] `kp_xc_lang_passage_main_idea.sql` — 主旨题
- [x] `kp_xc_lang_passage_detail.sql` — 细节题
- [x] `kp_xc_lang_passage_word_sentence.sql` — 词句题
- [x] `kp_xc_lang_passage_cohesion.sql` — 衔接题
- [x] `kp_xc_lang_passage_comprehension.sql` — 综合理解

**语句表达（3 篇）**
- [x] `kp_xc_lang_sentence_reorder.sql` — 语句排序
- [x] `kp_xc_lang_sentence_fill.sql` — 语句填空
- [x] `kp_xc_lang_sentence_next_infer.sql` — 下文推断

**片段阅读（6 篇）**
- [x] `kp_xc_lang_reading_main_idea.sql` — 主旨概括
- [x] `kp_xc_lang_reading_intent.sql` — 意图判断
- [x] `kp_xc_lang_reading_detail.sql` — 细节理解
- [x] `kp_xc_lang_reading_title.sql` — 标题选择
- [x] `kp_xc_lang_reading_attitude.sql` — 态度观点
- [x] `kp_xc_lang_reading_word_sentence.sql` — 词句理解

### 十一、资料分析概述内容（5 篇 SQL seed）
- [x] `kp_xc_data_overview.sql` — 资料分析总览（四大概念、速算技巧）
- [x] `kp_xc_data_growth_overview.sql` — 增长率概述
- [x] `kp_xc_data_proportion_overview.sql` — 比重概述
- [x] `kp_xc_data_average_overview.sql` — 平均数概述
- [x] `kp_xc_data_multiple_overview.sql` — 倍数概述

### 十二、常识判断内容（9 篇 SQL seed）
- [x] `kp_xc_cs_politics.sql` — 政治常识
- [x] `kp_xc_cs_law.sql` — 法律常识
- [x] `kp_xc_cs_economy.sql` — 经济常识
- [x] `kp_xc_cs_scitech.sql` — 科技常识
- [x] `kp_xc_cs_history_culture.sql` — 历史人文
- [x] `kp_xc_cs_geography.sql` — 地理国情
- [x] `kp_xc_cs_management.sql` — 管理常识
- [x] `kp_xc_cs_official_doc.sql` — 公文常识
- [x] `kp_xc_cs_current_affairs.sql` — 时事政治

### 十三、政治理论内容（1 篇 SQL seed）
- [x] `kp_xc_politics_overview.sql` — 政治理论概述

### 十四、数量关系分类树清理
- [x] 删除 22 个 L6 节点（解法维度 + 综合应用 + 比较类）
- [x] L6 从 128 个精简到 106 个

### 十五、数量关系概述内容（3 篇 SQL seed）
- [x] `kp_xc_quantity_overview.sql` — 数量关系总览
- [x] `kp_xc_math_overview.sql` — 数学运算概述
- [x] `kp_xc_number_reasoning_overview.sql` — 数字推理概述

## 全部完成
- [x] 判断推理（68 篇）✅
- [x] 言语理解（22 篇）✅
- [x] 资料分析（5 篇新增 + 19 篇已有）✅
- [x] 常识判断（9 篇）✅
- [x] 政治理论（1 篇）✅
- [x] 数量关系（3 篇概述 + ~350 篇已有）✅

## 内容结构模板

### L1 总览模板
```
H1: 模块名称总览
💡 highlightBlock: 核心方法论
H2: 一、知识体系（orderedList: 七大类别及考频）
H2: 二、三秒识别法（columns: 看什么 | 对应规律）
H2: 三、标准解题流程（textDiagram: Mermaid 流程图）
H2: 四、做题顺序建议（orderedList）
H2: 五、易错点（highlightBlock ⚠️）
📊 highlightBlock: 刷题建议
```

### L2 概述模板
```
H1: 分类名称概述
💡 highlightBlock: 识别特征
H2: 一、包含的子类（columns: 子类 | 考频）
H2: 二、核心判断逻辑（textDiagram: Mermaid 流程图）
H2: 三、与其他类别的区分（bulletList）
📊 highlightBlock: 学习建议
```

### L3 知识点详解模板
```
H1: 知识点名称
💡 highlightBlock: 核心结论
H2: 一、题型识别（columns: 图形特征 | 考查方向）
H2: 二、核心规律（orderedList）
H2: 三、解题步骤（textDiagram: Mermaid 流程图）
H2: 四、真题精讲（orderedList: 推导过程）
H2: 五、易错点（highlightBlock ⚠️）
📊 highlightBlock: 刷题建议
```

## 命名规范

- slug: `kp-xc-tutui-{category_code后缀}`
- tags: `["图形推理", "二级分类", "三级分类", ...]`
- extra: `{"content_type": "knowledge_point", "category_code": "对应sys_category.code", "source": "fba_content_engine"}`
- app_code: `gongkao`

## 关键发现

1. **study_question.knowledge_point 是扁平标签数组**，不是树形层级（最深 14 层 = 14 个标签平铺）
2. **sys_category 和题目标签是两个独立维度**：sys_category 管分类导航，题目标签管多维标注
3. **知识点 vs 解题方法**是两个正交维度，不应混在同一棵树里
4. **每个层级节点都应有内容**：L1 总览、L2 概述、L3 详解
