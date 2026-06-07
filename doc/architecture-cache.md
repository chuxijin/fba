# 缓存架构指南

## 一、全栈缓存金字塔

一个 Web 应用通常存在 9 层缓存，按延迟由近到远：

| 层级 | 介质 | 延迟 | 是否能控 | FBA 现状 |
|---|---|---|---|---|
| ① 浏览器缓存（HTTP Cache-Control / ETag） | 客户端 | 10-100ms | 可控 | ❌ 未启用 |
| ② CDN / 反向代理 | 边缘节点 | 5-30ms | 可控 | ❌ 未启用 |
| ③ `functools.lru_cache` | 进程内 | 1μs | 可控 | 🟢 局部 |
| ④ `cachebox.TTLCache` | 进程内 | 5-10μs | 可控 | 🟢 通过 `@cached` |
| ⑤ Pydantic schema cache | 进程内 | 1-10μs | 自动 | 🟢 默认 |
| ⑥ asyncio single-flight | 进程内 | 1-50ms | 可控 | 🟢 内置于 `RedisCache.get_or_set` |
| ⑦ Redis | 进程外 | 0.5-5ms | 可控 | 🟢 主力 |
| ⑧ SQLAlchemy session identity map | DB 层 | <1ms | 自动 | 🟢 默认 |
| ⑨ PostgreSQL shared_buffers | DB 层 | 1-10ms | 间接 | 🟢 自动 |

本项目重点治理 ④⑥⑦ 三层，对应"装饰器 / 单飞 / Redis"。

---

## 二、双层缓存抽象

FBA 在应用层提供两套并列、各司其职的缓存抽象：

```
                ┌──────────────────┐    ┌────────────────────┐
应用层          │  @cached         │    │ RedisCache         │
                │ 字典 / 配置       │    │ 业务 / 短 TTL      │
                │ 长 TTL 共享数据   │    │ 私有 + 复合 key    │
                └────────┬─────────┘    └──────────┬─────────┘
                         │                         │
                         └────────────┬────────────┘
                                      ▼
基建层          ┌────────────────────────────────────────────┐
                │ local.py (cachebox.TTLCache)               │
                │ pubsub.py (Redis Pub/Sub)                  │
                │ redis_client (redis.asyncio)               │
                └────────────────────────────────────────────┘
```

- **`@cached`**：字典型数据的最佳实践，全局 TTL，全用户共享，自动 L1。
- **`RedisCache`**：业务型数据的最佳实践，per-cache TTL，复合 key，可选 L1，内置 single-flight。

两者**共享底层基建**，不重复造轮子。

---

## 三、`@cached` 装饰器

### 3.1 适用场景

- 数据字典 / 系统配置（管理员低频更新）
- 读多写极少
- 全用户共享，无个性化字段
- 数据规模小（百级条数）
- 单 ORM Model 或基本类型（无 relationship 访问）

### 3.2 用法

```python
from backend.common.cache.decorator import cached, cache_invalidate
from backend.core.conf import settings

class DictDataService:
    @staticmethod
    @cached(settings.CACHE_DICT_REDIS_PREFIX, key='pk')
    async def get(*, db: AsyncSession, pk: int) -> DictData: ...

    @staticmethod
    @cache_invalidate(settings.CACHE_DICT_REDIS_PREFIX)
    async def update(...) -> int: ...
```

### 3.3 限制

- TTL 全局固定（`CACHE_REDIS_TTL=7200s`），不支持 per-cache
- 命中后返回 `dict`，不还原 ORM relationship
- key 模式仅支持 `key='param'` / `key='obj.field'` / `key_builder=lambda`

→ 不满足这些条件时，使用 `RedisCache`。

---

## 四、`RedisCache` 业务缓存

### 4.1 适用场景

- 用户私有数据（带 `user_id`）
- 短 TTL（30s ~ 30min）
- 复合 key（多维度组合）
- 自定义序列化（Pydantic / Dataclass）
- 跨实体失效拓扑（更新 chapter 时需清 bank 缓存）

### 4.2 核心 API

```python
class RedisCache[T]:
    def __init__(
        self,
        prefix: str,                  # 命名空间，如 'qbank:favorite:statistics'
        ttl: int,                     # 必填，强制业务方明确缓存时效
        serializer: Serializer[T],    # 必填，决定命中后的对象形态
        *,
        local: bool = False,          # L1 opt-in（共享数据建议开）
        invalidate_pubsub: bool = False,  # 跨进程 L1 一致性
        single_flight: bool = True,   # 单飞防雪崩，默认开启
    ): ...

    async def get(self, *key_parts) -> T | None: ...
    async def set(self, *key_parts, value: T) -> None: ...
    async def get_or_set(self, *key_parts, factory: Callable[[], Awaitable[T | None]]) -> T | None: ...
    async def invalidate(self, *key_parts) -> None: ...
    async def invalidate_prefix(self, *prefix_parts) -> None: ...
```

### 4.3 序列化器

| 序列化器 | 适用 | 说明 |
|---|---|---|
| `JsonSerializer` | dict / list / 标量 | msgspec 实现，比 stdlib json 快 5x |
| `PydanticSerializer(cls)` | Pydantic 模型 | 命中走 `model_validate_json`，比"解 dict + 校验"快 2-3x |
| `DataclassSerializer(cls, to_dict=, from_dict=)` | Dataclass | 默认 `dataclasses.asdict`，可自定义编解码 |
| `RawSerializer` | bytes / str | 直通，已预序列化时使用 |

### 4.4 用法示例

#### 用户私有 + 短 TTL + Pydantic

```python
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import PydanticSerializer

favorite_stats_cache = RedisCache(
    prefix='qbank:favorite:statistics',
    ttl=30,
    serializer=PydanticSerializer(FavoriteStatistics),
)

# 查询
stats = await favorite_stats_cache.get_or_set(
    user_id, cat_id, kp_cat_id,
    factory=lambda: compute_favorite_stats(...),
)

# 用户做了任何写操作 → 清掉该用户所有维度
await favorite_stats_cache.invalidate_prefix(user_id)
```

#### 全用户共享 + L1 + Pub/Sub

```python
group_tree_cache = RedisCache(
    prefix='qbank:group_tree:kp_categories',
    ttl=300,
    serializer=JsonSerializer(),
    local=True,                 # 共享数据开 L1, 命中率高
    invalidate_pubsub=True,     # 跨 worker 一致
)
```

### 4.5 single-flight 防雪崩

`get_or_set` 默认启用单飞：同一进程内对同一 key 的 N 个并发 miss 只触发 1 次 factory，其余等待者复用结果。

```python
# 1000 个并发请求, 缓存刚过期
results = await asyncio.gather(*(
    cache.get_or_set(user_id, factory=heavy_query) for _ in range(1000)
))
# heavy_query 只跑 1 次, 不会变成 1000 次 SQL 雪崩
```

需要每次重算时显式关闭：`single_flight=False`。

### 4.6 失效语义

- **`atomic`**：失败永不抛错，仅 `log.warning`。缓存挂了不影响业务。
- **写后失效**：先执行业务写入，成功后清缓存。
- **失效拓扑显式**：service 层显式调用 `await xxx_cache.invalidate(...)`，不引入隐式声明式 graph。

---

## 五、何时选哪个

| 场景 | 推荐 |
|---|---|
| 数据字典 | `@cached` |
| 系统配置 | `@cached` |
| 题库 / 篇章元数据 | `RedisCache` + L1 + PubSub（共享数据） |
| 用户权益快照 | `RedisCache` + 短 TTL（私有数据） |
| 答题统计 | `RedisCache` + 短 TTL（私有数据） |
| 题目静态解析 | `RedisCache` + 强缓存 |
| 验证码 / 一次性 token | 直接 `redis_client`（不是缓存） |
| Token / OAuth state | 直接 `redis_client`（状态存储） |
| 限流 / 雪花 / Pub/Sub | 不要用缓存抽象（基础设施性质） |

判断口诀：

> **DB 是真理之源 + 缓存可以丢 → 选 `@cached` 或 `RedisCache`**
> **Redis 是真理之源 + 数据丢了不能恢复 → 直接 `redis_client`**

---

## 六、共享数据缓存的扇出（fan-out）效应

全用户共享数据进入缓存后，**一份缓存惠及所有调用方**：

```
缓存前：bank_dao.get(42) 被 N 个接口各自调用 → N × 3ms = 24ms (N=8)
缓存后（Redis 命中）：→ N × 0.5ms = 4ms (-83%)
缓存后（L1 命中）：    → N × 10μs = 0.08ms (-99.7%)
```

题库系统的高 fan-out 数据清单（按价值排）：

| 数据 | fan-out 接口数 | 推荐 TTL | 是否开 L1 |
|---|---|---|---|
| bank 元数据 | 20+ | 600s | ✅ |
| chapter 元数据 | 15+ | 600s | ✅ |
| question 静态部分 | 10+ | 1800s | ✅ |
| knowledge_point 字典 | 8+ | 3600s | ✅ |
| category 分类树 | 6+ | 3600s | ✅ |

接入共享缓存后整体提升预估 25-50%，比单接口 perf sprint 投入产出比更高。

---

## 七、设计决策记录

### 为什么 `serializer` 必填？

避免业务方"不假思索接入"，结果命中返回 dict / 未命中返回 ORM，下游访问 `.relation` 爆炸。强制必填等于强制思考缓存形态。

### 为什么 `ttl` 必填？

`@cached` 全局 TTL 是字典场景的合理默认，但放到业务场景就抓瞎。强制每个 cache 实例显式声明 TTL，避免"接入即生产事故"。

### 为什么 single-flight 默认开？

防雪崩没副作用，业界默认（Caffeine / Go singleflight）。除非业务方明说"我要每次重算"，否则单飞是免费的安全垫。

### 为什么 L1 默认关？

L1 命中率 = 共享度 / 进程数。全用户共享数据 L1 接近 100%，私有数据 L1 接近 0% 反而占内存。默认关闭 + 业务方按需 opt-in 是更安全的默认。

### 为什么 key 用元组而非字符串？

复合 key 拼接是错误温床（顺序错乱、分隔符冲突、类型不一致）。元组式 API + 内部统一 `:` 拼接，类型化更安全，IDE 补全更友好。

### 为什么失败永不抛错？

缓存是性能优化，不是数据本体。Redis 挂了应该降级到 DB，而不是 500。所有缓存路径用 try/except + log.warning 包裹，业务无感。

---

## 八、迁移现有手写 Redis 缓存的检查清单

接入 `RedisCache` 时按以下清单核对：

- [ ] TTL 是否与现有手写一致？
- [ ] key 维度顺序是否保留？
- [ ] 序列化器选择是否最优？（dict 用 Json，Pydantic 用 PydanticSerializer 保留 `model_validate_json` 性能）
- [ ] 失效路径是否完备？（写操作后是否清了所有相关 prefix？）
- [ ] 是否需要 L1？（全用户共享 → 开；用户私有 → 关）
- [ ] 是否需要 Pub/Sub？（仅在 L1 开启 + 需要跨 worker 一致时开）
- [ ] 跨实体失效拓扑是否显式？（service 层有无遗漏的 invalidate 调用）

---

## 九、单元测试

`backend/common/tests/cache/test_redis_cache.py` 覆盖：

- 基础读写（miss / set / get / set None 跳过 / 复合 key 顺序敏感）
- 三种序列化器 round-trip（Json / Pydantic / Dataclass）
- `get_or_set` 命中复用
- single-flight 50 并发 → 1 次 factory
- factory 异常路径 _in_flight 清理
- 单 key / prefix 失效
- Redis 故障降级（get/set 抛错业务无感）

13 个用例，纯 stdlib 不依赖 pytest-asyncio，任何环境可跑。
