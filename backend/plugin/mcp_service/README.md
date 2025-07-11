# MCP服务插件

## 功能描述

MCP（Model Context Protocol）服务插件是一个基于FastAPI的智能搜索服务，直接搜索yp_resource表中的资源数据。支持中文分词、权重评分等高级搜索特性。

## 主要特性

- **🔍 智能分词搜索**: 使用jieba分词技术，支持中文智能分词
- **⚖️ 权重评分系统**: 不同字段具有不同的搜索权重，确保搜索结果的相关性
- **🎯 精准过滤**: 基于yp_resource表的智能过滤搜索
- **📊 相关度排序**: 按相关度评分和浏览量进行智能排序
- **💡 搜索建议**: 提供基于领域、科目、资源类型的智能建议
- **🔥 热门推荐**: 根据浏览量推荐热门资源
- **🏷️ 领域分类**: 支持按领域获取相关资源
- **📈 搜索统计**: 完整的搜索日志记录和统计分析
- **🚀 RESTful API**: 提供完整的RESTful API接口

## 搜索字段权重配置

| 字段 | 权重 | 说明 |
|------|------|------|
| main_name (主要名字) | 10 | 最高权重，精确匹配优先 |
| title (标题) | 8 | 高权重，标题匹配重要 |
| remark (备注) | 7 | 高权重，包含重要资源标识 |
| description (描述) | 6 | 中高权重，详细描述 |
| resource_intro (资源介绍) | 5 | 中等权重，资源介绍 |
| resource_type (资源类型) | 4 | 中等权重，类型匹配 |
| content (内容) | 3 | 较低权重，内容匹配 |
| domain (领域) | 2 | 较低权重，用户较少直接输入 |
| subject (科目) | 2 | 较低权重，用户较少直接输入 |

## API 接口

### 1. Quark Drive智能搜索接口

#### 智能搜索
- **URL**: `POST /mcp/v1/quark`
- **描述**: 基于分词+权重评分的智能搜索
- **需要认证**: 否
- **请求参数**:
```json
{
    "query": "Python编程教程",
    "url_type": "Quark_Drive",
    "domain": "编程",
    "subject": "Python",
    "resource_type": "教程",
    "limit": 10,
    "include_content": false
}
```

#### 快速搜索
- **URL**: `GET /mcp/v1/quark/quick?q=关键词&limit=5`
- **描述**: 简化的快速搜索接口
- **需要认证**: 否

#### 搜索建议
- **URL**: `GET /mcp/v1/quark/suggestions?q=关键词`
- **描述**: 获取搜索建议
- **需要认证**: 否

#### 热门资源
- **URL**: `GET /mcp/v1/quark/popular?limit=10`
- **描述**: 获取热门Quark Drive资源
- **需要认证**: 否

#### 按领域搜索
- **URL**: `GET /mcp/v1/quark/domain/{领域}?limit=10`
- **描述**: 根据领域获取相关资源
- **需要认证**: 否

#### 记录查看
- **URL**: `POST /mcp/v1/quark/view/{资源ID}`
- **描述**: 记录资源查看次数
- **需要认证**: 否

### 2. MCP核心搜索接口

#### 智能搜索接口
- `POST /mcp/v1/resources?key=mcp_search_2025` - SSE流式搜索yp_resource表资源

## 数据模型

### 搜索请求模型 (ResourceSearchParam)

```python
{
    "query": str,                 # 搜索查询（必填）
    "url_type": str,              # 链接类型，默认"Quark_Drive"
    "domain": str,                # 领域过滤（可选）
    "subject": str,               # 科目过滤（可选）
    "resource_type": str,         # 资源类型过滤（可选）
    "limit": int,                 # 返回数量限制，默认10
    "include_content": bool       # 是否包含详细内容，默认false
}
```

### 搜索响应模型 (ResourceSearchResponse)

```python
{
    "query": str,                 # 搜索查询
    "total": int,                 # 总结果数
    "results": [                  # 搜索结果列表
        {
            "id": int,            # 资源ID
            "domain": str,        # 领域
            "subject": str,       # 科目
            "main_name": str,     # 主要名字
            "title": str,         # 标题
            "resource_type": str, # 资源类型
            "url_type": str,      # 链接类型
            "url": str,           # Quark Drive链接
            "description": str,   # 描述
            "share_id": str,      # 分享ID
            "extract_code": str,  # 提取码
            "view_count": int,    # 浏览量
            "relevance_score": float, # 相关度评分
            "created_time": datetime, # 创建时间
            "expired_at": datetime    # 过期时间
        }
    ],
    "response_time": int,         # 响应时间（毫秒）
    "search_strategy": str,       # 搜索策略
    "keywords": [str]             # 分词结果
}
```

## 使用示例

### 1. 智能搜索

```bash
curl -X POST "http://localhost:8000/mcp/v1/quark" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python机器学习教程",
    "limit": 5,
    "include_content": false
  }'
```

### 2. 快速搜索

```bash
curl -X GET "http://localhost:8000/mcp/v1/quark/quick?q=数据库设计&limit=3"
```

### 3. 获取搜索建议

```bash
curl -X GET "http://localhost:8000/mcp/v1/quark/suggestions?q=编程"
```

### 4. 获取热门资源

```bash
curl -X GET "http://localhost:8000/mcp/v1/quark/popular?limit=10"
```

### 5. 按领域搜索

```bash
curl -X GET "http://localhost:8000/mcp/v1/quark/domain/编程?limit=10"
```

## 搜索算法详解

### 1. 分词处理
- 使用jieba进行中文分词
- 过滤停用词和单字符
- 支持同义词扩展

### 2. 权重评分
- 每个字段有不同的权重值
- 计算关键词在各字段的匹配度
- 综合评分并归一化到0-1之间

### 3. 排序策略
- 首先按相关度评分排序
- 相同评分按浏览量排序
- 保证热门且相关的资源优先显示

## 部署说明

1. **安装依赖**:
   ```bash
   pip install jieba>=0.42.1
   ```

2. **数据库配置**: 
   - 确保yp_resource表存在
   - 确保mcp_search_log表存在（用于日志记录）

3. **启动服务**:
   ```bash
   python start.py
   ```

4. **测试功能**:
   ```bash
   python test_quark_search.py
   ```

## 性能优化建议

1. **数据库索引**: 为搜索字段创建适当的索引
   ```sql
   CREATE INDEX idx_yp_resource_main_name ON yp_resource(main_name);
   CREATE INDEX idx_yp_resource_title ON yp_resource(title);
   CREATE INDEX idx_yp_resource_domain ON yp_resource(domain);
   CREATE INDEX idx_yp_resource_subject ON yp_resource(subject);
   ```

2. **缓存优化**: 
   - 缓存热门搜索词的结果
   - 缓存分词结果
   - 使用Redis缓存搜索建议

3. **搜索优化**:
   - 限制搜索结果数量
   - 实现搜索结果分页
   - 添加搜索频率限制

## 扩展功能

### 1. 搜索历史
可以记录用户搜索历史，提供个性化推荐。

### 2. 高级过滤
支持更多过滤条件，如价格范围、文件大小等。

### 3. 语义搜索
集成sentence-transformers实现语义搜索。

### 4. 搜索分析
提供详细的搜索行为分析和统计报告。

## 技术栈

- **后端框架**: FastAPI
- **数据库**: MySQL/PostgreSQL (基于现有yp_resource表)
- **分词技术**: jieba
- **ORM**: SQLAlchemy 2.0
- **数据验证**: Pydantic v2
- **文档**: 自动生成Swagger/ReDoc文档

## 版本信息

- **版本**: 1.0.0
- **作者**: null
- **更新时间**: 2024年
- **专门优化**: Quark Drive资源搜索 