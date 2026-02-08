import sys
import os
import asyncio
from unittest.mock import MagicMock

# 1. 设置路径，确保能导入 backend 包
sys.path.append(os.getcwd())

# 2. Mock 依赖项，避免加载真实的配置和数据库连接
# 必须在导入 permission 模块之前 Mock，因为它在文件头引用了这些模块
sys.modules['backend.core.conf'] = MagicMock()
sys.modules['backend.common.context'] = MagicMock()

# Mock dynamic_import
mock_dyn_import = MagicMock()
sys.modules['backend.utils.dynamic_import'] = mock_dyn_import

# 3. 导入待测试的函数
# 这里需要小心处理 import，因为 verify_permission 内部 import 也是从 sys.modules 取的
try:
    from backend.common.security.permission import verify_permission
except ImportError as e:
    print(f"导入失败，尝试直接加载文件... {e}")
    # 如果直接导入失败，我们可以手动 Mock 整个 verify_permission 环境
    # 但为了演示真实逻辑，我们尽量复用代码。
    pass

# 4. 定义 Mock 的 RoleService
# 这是模拟数据库查询结果
mock_role_service = MagicMock()

async def mock_get_user_permissions(user_id):
    """模拟根据用户ID查库返回的权限列表"""
    print(f"   [DB查询] 正在获取用户 {user_id} 的权限...")
    
    if user_id == 100: # 模拟: 26届政治VIP用户
        return [
            'practice:2026:politics',      # 精确权限
            'practice:public:free',        # 公共免费权限
            'video:2026:politics:*'        # 通配符权限
        ]
    elif user_id == 200: # 模拟: 普通用户
        return [
            'practice:public:free'
        ]
    elif user_id == 999: # 模拟: 超级管理员 (虽然后面 logic 会直接跳过，但这里还是 mock 一下)
        return ['*:*:*']
        
    return []

# 将 Mock 方法挂载到 mock_role_service
mock_role_service.role_service.get_user_permissions = mock_get_user_permissions

# 5. 配置 import_module_cached 的返回值
# 当 verify_permission 内部调用 import_module_cached('backend.app.admin.service.role_service') 时
# 让它返回我们定义好的 mock_role_service
def side_effect_import(name):
    if name == 'backend.app.admin.service.role_service':
        return mock_role_service
    return MagicMock()

mock_dyn_import.import_module_cached.side_effect = side_effect_import

# ==========================================
# 开始测试
# ==========================================
async def run_test():
    print("\n========== 开始测试动态权限校验 ==========\n")

    # --- 场景 1: VIP 用户访问拥有的权限 ---
    req_vip = MagicMock()
    req_vip.user.is_superuser = False
    req_vip.user.id = 100
    req_vip.user.username = "张三(VIP)"

    target_perm = "practice:2026:politics"
    print(f"测试 1: 用户[{req_vip.user.username}] 访问 [{target_perm}]")
    is_allowed = await verify_permission(req_vip, target_perm)
    print(f"👉 结果: {'✅ 通过' if is_allowed else '❌ 拒绝'}\n")

    # --- 场景 2: VIP 用户访问未拥有的权限 ---
    target_perm_2 = "practice:2027:math" # 他只买对应的 26届政治
    print(f"测试 2: 用户[{req_vip.user.username}] 访问 [{target_perm_2}]")
    is_allowed = await verify_permission(req_vip, target_perm_2)
    print(f"👉 结果: {'✅ 通过' if is_allowed else '❌ 拒绝'} (预期应拒绝)\n")

    # --- 场景 3: 通配符测试 ---
    # 用户拥有 'video:2026:politics:*'
    target_perm_3 = "video:2026:politics:chapter1"
    print(f"测试 3: 用户[{req_vip.user.username}] 访问 [{target_perm_3}] (通配符匹配)")
    is_allowed = await verify_permission(req_vip, target_perm_3)
    print(f"👉 结果: {'✅ 通过' if is_allowed else '❌ 拒绝'}\n")

    # --- 场景 4: 普通用户 ---
    req_normal = MagicMock()
    req_normal.user.is_superuser = False
    req_normal.user.id = 200
    req_normal.user.username = "李四(普通)"
    
    print(f"测试 4: 用户[{req_normal.user.username}] 访问 [practice:2026:politics]")
    is_allowed = await verify_permission(req_normal, "practice:2026:politics")
    print(f"👉 结果: {'✅ 通过' if is_allowed else '❌ 拒绝'} (预期应拒绝)\n")

    # --- 场景 5: 超级管理员 ---
    req_admin = MagicMock()
    req_admin.user.is_superuser = True
    req_admin.user.id = 999
    req_admin.user.username = "王五(Admin)"
    
    print(f"测试 5: 用户[{req_admin.user.username}] 访问 [practice:2026:politics]")
    is_allowed = await verify_permission(req_admin, "practice:2026:politics")
    print(f"👉 结果: {'✅ 通过' if is_allowed else '❌ 拒绝'} (Admin自带特权)\n")

if __name__ == "__main__":
    asyncio.run(run_test())
