#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入核心模块
from backend.app.coulddrive.service.baidu.api import BaiduApi
from backend.app.coulddrive.service.baidu.client import BaiduClient
from backend.app.coulddrive.schema.enum import RecursionSpeed

# 测试用的 cookies 字符串
cookies_str = "BAIDUID=D68A05E330BEFA4556BC6F2FF9488922:FG=1; BDUSS=0ZtMFhnd1d4YXJjUENPdHJ5Sk1HaHY4QVdqZWlyU2o1LUhNU1pXVWhuTFFwZmhuRVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANAY0WfQGNFnM; BDUSS_BFESS=0ZtMFhnd1d4YXJjUENPdHJ5Sk1HaHY4QVdqZWlyU2o1LUhNU1pXVWhuTFFwZmhuRVFBQUFBJCQAAAAAAAAAAAEAAABbzI2fvfCz~urYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANAY0WfQGNFnM; PANWEB=1; Hm_lvt_0ba7bcf57b5e55fbfbab9a2750acdf3e=1741830844,1741845158,1741847535,1741847597; MAWEBCUID=web_srSuKTfVWheszQBeCuNRpfkJvvmRbaCtBtMHhFVXHzufjhhQRb; BIDUPSID=D68A05E330BEFA4556BC6F2FF9488922; PSTM=1743476525; Hm_lvt_95fc87a381fad8fcb37d76ac51fefcea=1743575659,1744859077; BAIDUID_BFESS=D68A05E330BEFA4556BC6F2FF9488922:FG=1; H_PS_PSSID=60276_61027_61673_62327_62833_62866_62891_62969_63043_63046_63147_63079_63156_63173_63074_63194; ZFY=q2:Asx83WfcVKV4jL3lAy0n:BrmuUIWuo1AWDUXpqDUmk:C; STOKEN=7e82f475423e5c1a35e63a972b9cb67f0c2ce6418468fdccc002d695aadcc032; BDCLND=syKLP5NnQrISd74ehANryKDITf9fBhuM5UMST8vg9uQ%3D; ZD_ENTRY=bing; BCLID=8477968414979132403; BCLID_BFESS=8477968414979132403; BDSFRCVID=LaPOJeC62xMjl15s-5EkrNtkh2K-B2OTH6_n3eEkJog2718wCfimEG0Pdx8g0Ku-S2-cogKKKgOTHIDF_2uxOjjg8UtVJeC6EG0Ptf8g0x5; BDSFRCVID_BFESS=LaPOJeC62xMjl15s-5EkrNtkh2K-B2OTH6_n3eEkJog2718wCfimEG0Pdx8g0Ku-S2-cogKKKgOTHIDF_2uxOjjg8UtVJeC6EG0Ptf8g0x5; H_BDCLCKID_SF=tRAOoC85fIvjDb7GbKTD-tFO5eT22-usBI6T2hcH0KLKJh6Fh5LhKIr0QfRHWJ3W2nrisl_-BMb1Mx7kDPopMUIebNKfJ6vf0Kc0Wl5TtUJfJKnTDMRhqqJXqfbyKMniWKv9-pnY3pQrh459XP68bTkA5bjZKxtq3mkjbPbDfn02JKKu-n5jHjoQDG_O3j; H_BDCLCKID_SF_BFESS=tRAOoC85fIvjDb7GbKTD-tFO5eT22-usBI6T2hcH0KLKJh6Fh5LhKIr0QfRHWJ3W2nrisl_-BMb1Mx7kDPopMUIebNKfJ6vf0Kc0Wl5TtUJfJKnTDMRhqqJXqfbyKMniWKv9-pnY3pQrh459XP68bTkA5bjZKxtq3mkjbPbDfn02JKKu-n5jHjoQDG_O3j; __bid_n=196fbf5464c23042ce409a; csrfToken=6OugyebXwt1ZUYwm5W2g9lqC; PANPSC=9480241873451417150%3AAuI6D6iGxssPruTfFI0vcFcS2d9ns3O5PneheCNDBBMoK5JNovHgnB353onjfJd5COfgdHnp149R1E%2B0ZQkPA6F0C9p6ruYZFl7owtXleijihEIzmOtMnX%2FtTTe09VrxYqZdy9zZ13lsfZ87u8WyL8e5FP%2BN79BDnn5PLdbbKScat4Sct8Bqe2xJ6274ljdFcg9HXxsESniOhXbRLWybyEfxDwaq5Ss%2BpVgrCRW4E7IkqtDb6%2BO1U5KxVlqrIDxM; Hm_lvt_182d6d59474cf78db37e0b2248640ea5=1747454299,1747488687,1747883369,1748233783; Hm_lpvt_182d6d59474cf78db37e0b2248640ea5=1748233783; ndut_fmt=A680195A1E16D9C46077BD7B142452D76028D7A75495FC665DB41764654C78B3"

# 全局变量存储客户端实例
baidu_api = None
baidu_client = None

def print_menu():
    """显示主菜单"""
    print("\n" + "="*60)
    print("🚀 百度网盘测试工具 - 交互式菜单")
    print("="*60)
    print("【BaiduApi 测试】")
    print("  1. 初始化 BaiduApi")
    print("  2. 获取用户信息")
    print("  3. 获取配额信息")
    print("  4. 列出根目录")
    print("  5. 列出指定目录")
    print("  6. 检查文件/目录是否存在")
    print("  7. 获取文件元数据")
    print()
    print("【BaiduClient 测试】")
    print("  11. 初始化 BaiduClient")
    print("  12. 获取用户信息 (Client)")
    print("  13. 获取磁盘文件列表")
    print("  14. 获取磁盘文件列表 (递归)")
    print("  15. 创建目录")
    print("  16. 删除文件/目录")
    print("  17. 重命名文件/目录")
    print("  18. 获取关系列表 (好友/群组)")
    print("  19. 获取分享列表")
    print("  20. 获取分享详情")
    print("  21. 获取分享文件列表")
    print("  22. 转存文件")
    print()
    print("【综合测试】")
    print("  91. 运行所有 BaiduApi 测试")
    print("  92. 运行所有 BaiduClient 测试")
    print()
    print("  0. 退出程序")
    print("="*60)

async def init_baidu_api():
    """初始化 BaiduApi"""
    global baidu_api
    try:
        baidu_api = BaiduApi(cookies=cookies_str)
        print("✅ BaiduApi 初始化成功!")
        print(f"   BDUSS: {baidu_api._bduss[:20]}...")
        print(f"   STOKEN: {baidu_api._stoken[:20] if baidu_api._stoken else 'None'}...")
        return True
    except Exception as e:
        print(f"❌ BaiduApi 初始化失败: {e}")
        return False

async def init_baidu_client():
    """初始化 BaiduClient"""
    global baidu_client
    
    cookies_str = input("请输入 cookies 字符串 (格式: BDUSS=xxx; STOKEN=xxx; PTOKEN=xxx): ").strip()
    if not cookies_str:
        print("❌ Cookies 不能为空")
        return False
    
    try:
        baidu_client = BaiduClient(cookies=cookies_str)
        
        # 尝试获取用户信息验证登录
        try:
            user_info = await baidu_client.get_user_info()
            print("✅ BaiduClient 初始化成功!")
            print(f"   登录状态: 成功")
            print(f"   驱动类型: {baidu_client.drive_type}")
            print(f"   用户名: {user_info.username}")
            print(f"   用户ID: {user_info.user_id}")
            print(f"   BDUSS: {baidu_client.bduss[:20] if baidu_client.bduss else 'None'}...")
            print(f"   STOKEN: {baidu_client.stoken[:20] if baidu_client.stoken else 'None'}...")
            return True
        except Exception as e:
            print(f"⚠️  BaiduClient 初始化成功，但获取用户信息失败: {e}")
            print("   这可能会影响某些分享功能的使用")
            print(f"   驱动类型: {baidu_client.drive_type}")
            print(f"   BDUSS: {baidu_client.bduss[:20] if baidu_client.bduss else 'None'}...")
            print(f"   STOKEN: {baidu_client.stoken[:20] if baidu_client.stoken else 'None'}...")
            return True
            
    except Exception as e:
        print(f"❌ BaiduClient 初始化失败: {e}")
        return False

async def test_client_user_info():
    """测试获取用户信息 (Client)"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    try:
        user_info = await baidu_client.get_user_info()
        print("✅ 用户信息获取成功:")
        print(f"   用户ID: {user_info.user_id}")
        print(f"   用户名: {user_info.username}")
        print(f"   头像URL: {user_info.avatar_url}")
        print(f"   总空间: {user_info.quota / (1024**3):.2f} GB" if user_info.quota else "   总空间: 未知")
        print(f"   已使用: {user_info.used / (1024**3):.2f} GB" if user_info.used else "   已使用: 未知")
        print(f"   是否VIP: {'是' if user_info.is_vip else '否'}")
        print(f"   是否超级VIP: {'是' if user_info.is_supervip else '否'}")
    except Exception as e:
        print(f"❌ 获取用户信息失败: {e}")

async def test_client_disk_list():
    """测试获取磁盘文件列表 (Client)"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    path = input("请输入要列出的目录路径 (默认: /): ").strip()
    if not path:
        path = "/"
    
    try:
        file_list = await baidu_client.get_disk_list(
            file_path=path,
            file_id="",  # 根目录使用空字符串
            recursive=False
        )
        print(f"✅ 目录 {path} 列表获取成功:")
        print(f"   文件数量: {len(file_list)}")
        for i, file_info in enumerate(file_list[:10]):  # 只显示前10个
            type_str = '文件夹' if file_info.is_folder else f'文件 ({file_info.file_size} 字节)'
            print(f"   {i+1}. {file_info.file_name} ({type_str})")
            print(f"       路径: {file_info.file_path}")
            print(f"       ID: {file_info.file_id}")
        if len(file_list) > 10:
            print(f"   ... 还有 {len(file_list) - 10} 个项目")
    except Exception as e:
        print(f"❌ 获取目录列表失败: {e}")

async def test_client_disk_list_recursive():
    """测试获取磁盘文件列表 (递归)"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    path = input("请输入要递归列出的目录路径 (默认: /): ").strip()
    if not path:
        path = "/"
    
    speed_input = input("请选择递归速度 (1=SLOW, 2=NORMAL, 3=FAST, 默认=2): ").strip()
    speed_map = {"1": RecursionSpeed.SLOW, "2": RecursionSpeed.NORMAL, "3": RecursionSpeed.FAST}
    speed = speed_map.get(speed_input, RecursionSpeed.NORMAL)
    
    try:
        print(f"🔄 开始递归获取目录 {path} (速度: {speed.value})...")
        file_list = await baidu_client.get_disk_list(
            file_path=path,
            file_id="",  # 根目录使用空字符串
            recursive=True,
            recursion_speed=speed
        )
        print(f"✅ 递归目录 {path} 列表获取成功:")
        print(f"   总文件数量: {len(file_list)}")
        
        # 按类型统计
        folders = [f for f in file_list if f.is_folder]
        files = [f for f in file_list if not f.is_folder]
        print(f"   文件夹数量: {len(folders)}")
        print(f"   文件数量: {len(files)}")
        
        # 显示前10个项目
        for i, file_info in enumerate(file_list[:10]):
            type_str = '文件夹' if file_info.is_folder else f'文件 ({file_info.file_size} 字节)'
            print(f"   {i+1}. {file_info.file_name} ({type_str})")
            print(f"       路径: {file_info.file_path}")
            print(f"       父ID: {file_info.parent_id}")
        if len(file_list) > 10:
            print(f"   ... 还有 {len(file_list) - 10} 个项目")
    except Exception as e:
        print(f"❌ 递归获取目录列表失败: {e}")

async def test_client_mkdir():
    """测试创建目录 (Client)"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    path = input("请输入要创建的目录路径 (例如: /测试目录): ").strip()
    if not path:
        print("❌ 目录路径不能为空")
        return
    
    try:
        result = await baidu_client.mkdir(file_path=path)
        print("✅ 目录创建成功:")
        print(f"   目录名: {result.file_name}")
        print(f"   路径: {result.file_path}")
        print(f"   ID: {result.file_id}")
        print(f"   父ID: {result.parent_id}")
    except Exception as e:
        print(f"❌ 创建目录失败: {e}")

async def test_client_remove():
    """测试删除文件/目录 (Client)"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    path = input("请输入要删除的文件/目录路径: ").strip()
    if not path:
        print("❌ 路径不能为空")
        return
    
    confirm = input(f"⚠️  确认要删除 '{path}' 吗? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ 操作已取消")
        return
    
    try:
        result = await baidu_client.remove(file_paths=path)
        if result:
            print("✅ 删除成功")
        else:
            print("❌ 删除失败")
    except Exception as e:
        print(f"❌ 删除失败: {e}")

async def test_client_rename():
    """测试重命名文件/目录 (Client)"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    source = input("请输入源文件/目录路径: ").strip()
    dest = input("请输入目标文件/目录路径: ").strip()
    
    if not source or not dest:
        print("❌ 源路径和目标路径都不能为空")
        return
    
    try:
        result = await baidu_client.rename(source, dest)
        print("✅ 重命名成功:")
        print(f"   从: {result.from_}")
        print(f"   到: {result.to_}")
    except Exception as e:
        print(f"❌ 重命名失败: {e}")

async def test_client_relationship_list():
    """测试获取关系列表 (好友/群组)"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    rel_type = input("请选择类型 (1=好友, 2=群组): ").strip()
    if rel_type == "1":
        relationship_type = "friend"
    elif rel_type == "2":
        relationship_type = "group"
    else:
        print("❌ 无效选择")
        return
    
    try:
        result = await baidu_client.get_relationship_list(relationship_type)
        print(f"✅ {relationship_type} 列表获取成功:")
        print(f"   数量: {len(result)}")
        
        for i, item in enumerate(result[:10]):  # 只显示前10个
            if relationship_type == "friend":
                print(f"   {i+1}. {item.nick_name} (UK: {item.uk})")
                print(f"       用户名: {item.uname}")
                print(f"       关系状态: {item.is_friend}")
            else:  # group
                print(f"   {i+1}. {item.name} (GID: {item.gid})")
                print(f"       群号: {item.gnum}")
                print(f"       类型: {item.type}")
                print(f"       状态: {item.status}")
        
        if len(result) > 10:
            print(f"   ... 还有 {len(result) - 10} 个项目")
    except Exception as e:
        print(f"❌ 获取关系列表失败: {e}")

async def test_client_share_list():
    """测试获取分享列表"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    rel_type = input("请选择类型 (1=好友, 2=群组): ").strip()
    if rel_type == "1":
        relationship_type = "friend"
        identifier = input("请输入好友UK: ").strip()
    elif rel_type == "2":
        relationship_type = "group"
        identifier = input("请输入群组ID: ").strip()
    else:
        print("❌ 无效选择")
        return
    
    if not identifier:
        print("❌ 标识符不能为空")
        return
    
    try:
        result = await baidu_client.get_relationship_share_list(
            relationship_type=relationship_type,
            identifier=identifier
        )
        print(f"✅ {relationship_type} 分享列表获取成功:")
        print(f"   错误码: {result.get('errno', 'Unknown')}")
        
        records = result.get('records', {})
        if relationship_type == "friend":
            share_list = records.get('list', [])
        else:
            share_list = records.get('msg_list', [])
        
        print(f"   分享数量: {len(share_list)}")
        
        for i, share in enumerate(share_list[:5]):  # 只显示前5个
            print(f"   {i+1}. 消息ID: {share.get('msg_id', 'Unknown')}")
            if relationship_type == "friend":
                print(f"       分享者: {share.get('from_uk', 'Unknown')}")
                filelist = share.get('filelist', {}).get('list', [])
                if filelist:
                    print(f"       文件: {filelist[0].get('server_filename', 'Unknown')}")
            else:
                print(f"       分享者: {share.get('uk', 'Unknown')}")
                file_list = share.get('file_list', [])
                if file_list:
                    print(f"       文件: {file_list[0].get('server_filename', 'Unknown')}")
        
        if len(share_list) > 5:
            print(f"   ... 还有 {len(share_list) - 5} 个分享")
    except Exception as e:
        print(f"❌ 获取分享列表失败: {e}")

async def test_client_share_detail():
    """测试获取分享详情"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    rel_type = input("请选择类型 (1=好友, 2=群组): ").strip()
    if rel_type == "1":
        relationship_type = "friend"
        print("注意：好友分享详情中，identifier 应该是接收者（当前用户）的UK")
        identifier = input("请输入接收者UK（当前用户UK）: ").strip()
    elif rel_type == "2":
        relationship_type = "group"
        identifier = input("请输入群组ID: ").strip()
    else:
        print("❌ 无效选择")
        return
    
    from_uk = input("请输入分享者UK: ").strip()
    msg_id = input("请输入消息ID: ").strip()
    fs_id = input("请输入文件ID: ").strip()
    
    if not all([identifier, from_uk, msg_id, fs_id]):
        print("❌ 所有参数都不能为空")
        return
    
    try:
        result = await baidu_client.get_relationship_share_detail(
            relationship_type=relationship_type,
            identifier=identifier,
            from_uk=from_uk,
            msg_id=msg_id,
            fs_id=fs_id
        )
        print(f"✅ {relationship_type} 分享详情获取成功:")
        print(f"   错误码: {result.get('errno', 'Unknown')}")
        
        records = result.get("records", [])
        print(f"   记录数量: {len(records)}")
        
        for i, record in enumerate(records[:5]):  # 只显示前5个
            print(f"   {i+1}. 文件名: {record.get('server_filename', 'Unknown')}")
            print(f"       大小: {record.get('size', 0)} 字节")
            print(f"       是否目录: {'是' if record.get('isdir') else '否'}")
            print(f"       fs_id: {record.get('fs_id', 'Unknown')}")
        
        if len(records) > 5:
            print(f"   ... 还有 {len(records) - 5} 个记录")
    except Exception as e:
        print(f"❌ 获取分享详情失败: {e}")

async def test_client_get_share_list():
    """测试获取分享文件列表"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    rel_type = input("请选择类型 (1=好友, 2=群组): ").strip()
    if rel_type == "1":
        source_type = "friend"
        source_id = input("请输入好友UK: ").strip()
    elif rel_type == "2":
        source_type = "group"
        source_id = input("请输入群组ID: ").strip()
    else:
        print("❌ 无效选择")
        return
    
    file_path = input("请输入分享内的文件路径 (例如: /共享文件夹): ").strip()
    if not file_path:
        print("❌ 文件路径不能为空")
        return
    
    recursive = input("是否递归获取? (y/N): ").strip().lower() == 'y'
    
    try:
        # 导入必要的模块
        from backend.app.coulddrive.schema.file import ListShareFilesParam
        from backend.app.coulddrive.schema.enum import RecursionSpeed
        
        # 创建参数对象
        params = ListShareFilesParam(
            drive_type="BaiduDrive",  # 百度网盘
            source_type=source_type,
            source_id=source_id,
            file_path=file_path,
            recursive=recursive,
            recursion_speed=RecursionSpeed.NORMAL
        )
        
        result = await baidu_client.get_share_list(params)
        print(f"✅ 分享文件列表获取成功:")
        print(f"   文件数量: {len(result)}")
        
        for i, file_info in enumerate(result[:10]):  # 只显示前10个
            type_str = '文件夹' if file_info.is_folder else f'文件 ({file_info.file_size} 字节)'
            print(f"   {i+1}. {file_info.file_name} ({type_str})")
            print(f"       路径: {file_info.file_path}")
            print(f"       ID: {file_info.file_id}")
        
        if len(result) > 10:
            print(f"   ... 还有 {len(result) - 10} 个项目")
    except Exception as e:
        print(f"❌ 获取分享文件列表失败: {e}")

async def test_client_transfer():
    """测试转存文件"""
    if not baidu_client:
        print("❌ 请先初始化 BaiduClient (选项 11)")
        return
    
    rel_type = input("请选择类型 (1=好友, 2=群组): ").strip()
    if rel_type == "1":
        source_type = "friend"
        source_id = input("请输入好友UK: ").strip()
    elif rel_type == "2":
        source_type = "group"
        source_id = input("请输入群组ID: ").strip()
    else:
        print("❌ 无效选择")
        return
    
    target_path = input("请输入目标保存路径 (例如: /我的资源): ").strip()
    if not target_path:
        target_path = "/我的资源"
    
    file_ids_input = input("请输入文件ID列表 (用逗号分隔): ").strip()
    if not file_ids_input:
        print("❌ 文件ID不能为空")
        return
    
    file_ids = [fid.strip() for fid in file_ids_input.split(',')]
    
    msg_id = input("请输入消息ID: ").strip()
    if not msg_id:
        print("❌ 消息ID不能为空")
        return
    
    kwargs = {"msg_id": msg_id}
    if source_type == "group":
        from_uk = input("请输入分享者UK: ").strip()
        if not from_uk:
            print("❌ 群组分享需要提供分享者UK")
            return
        kwargs["from_uk"] = from_uk
    
    try:
        result = await baidu_client.transfer(
            source_type=source_type,
            source_id=source_id,
            source_path="",  # 百度网盘不使用此参数
            target_path=target_path,
            file_ids=file_ids,
            **kwargs
        )
        print(f"✅ 转存操作结果: {'成功' if result else '失败'}")
    except Exception as e:
        print(f"❌ 转存失败: {e}")

async def test_api_user_info():
    """测试获取用户信息 (API)"""
    if not baidu_api:
        print("❌ 请先初始化 BaiduApi (选项 1)")
        return
    
    try:
        user_info = await baidu_api.get_user_info()
        print("✅ 用户信息获取成功:")
        if 'user_info' in user_info:
            ui = user_info['user_info']
            print(f"   用户名: {ui.get('username', 'Unknown')}")
            print(f"   用户ID: {ui.get('uk', 'Unknown')}")
            print(f"   是否VIP: {'是' if ui.get('is_vip') else '否'}")
            print(f"   是否超级VIP: {'是' if ui.get('is_svip') else '否'}")
            print(f"   手机号: {ui.get('phone', 'Unknown')}")
        else:
            print(f"   原始数据: {user_info}")
    except Exception as e:
        print(f"❌ 获取用户信息失败: {e}")

async def test_api_quota():
    """测试获取配额信息 (API)"""
    if not baidu_api:
        print("❌ 请先初始化 BaiduApi (选项 1)")
        return
    
    try:
        quota_info = await baidu_api.get_quota()
        print("✅ 配额信息获取成功:")
        total = quota_info.get('total', 0)
        used = quota_info.get('used', 0)
        print(f"   总空间: {total / (1024**3):.2f} GB")
        print(f"   已使用: {used / (1024**3):.2f} GB")
        print(f"   剩余空间: {(total - used) / (1024**3):.2f} GB")
        print(f"   使用率: {(used / total * 100):.1f}%")
    except Exception as e:
        print(f"❌ 获取配额信息失败: {e}")

async def test_api_list_root():
    """测试列出根目录 (API)"""
    if not baidu_api:
        print("❌ 请先初始化 BaiduApi (选项 1)")
        return
    
    try:
        root_list = await baidu_api.list("/")
        print("✅ 根目录列表获取成功:")
        file_list = root_list.get('list', [])
        print(f"   文件数量: {len(file_list)}")
        for i, item in enumerate(file_list[:10]):  # 只显示前10个
            name = item.get('server_filename', 'Unknown')
            is_dir = item.get('isdir', 0)
            size = item.get('size', 0)
            type_str = '文件夹' if is_dir else f'文件 ({size} 字节)'
            print(f"   {i+1}. {name} ({type_str})")
        if len(file_list) > 10:
            print(f"   ... 还有 {len(file_list) - 10} 个项目")
    except Exception as e:
        print(f"❌ 列出根目录失败: {e}")

async def test_api_list_custom():
    """测试列出指定目录 (API)"""
    if not baidu_api:
        print("❌ 请先初始化 BaiduApi (选项 1)")
        return
    
    path = input("请输入要列出的目录路径 (例如: /课程目录系统内容展示): ").strip()
    if not path:
        path = "/课程目录系统内容展示"
    
    try:
        exists = await baidu_api.exists(path)
        if not exists:
            print(f"❌ 目录 {path} 不存在")
            return
        
        dir_list = await baidu_api.list(path)
        print(f"✅ 目录 {path} 列表获取成功:")
        file_list = dir_list.get('list', [])
        print(f"   文件数量: {len(file_list)}")
        for i, item in enumerate(file_list[:10]):  # 只显示前10个
            name = item.get('server_filename', 'Unknown')
            is_dir = item.get('isdir', 0)
            size = item.get('size', 0)
            type_str = '文件夹' if is_dir else f'文件 ({size} 字节)'
            print(f"   {i+1}. {name} ({type_str})")
        if len(file_list) > 10:
            print(f"   ... 还有 {len(file_list) - 10} 个项目")
    except Exception as e:
        print(f"❌ 列出目录 {path} 失败: {e}")

async def test_api_exists():
    """测试文件/目录存在性检查 (API)"""
    if not baidu_api:
        print("❌ 请先初始化 BaiduApi (选项 1)")
        return
    
    path = input("请输入要检查的路径 (例如: /课程目录系统内容展示): ").strip()
    if not path:
        path = "/课程目录系统内容展示"
    
    try:
        exists = await baidu_api.exists(path)
        print(f"✅ 路径检查完成:")
        print(f"   路径: {path}")
        print(f"   存在: {'是' if exists else '否'}")
    except Exception as e:
        print(f"❌ 检查路径 {path} 失败: {e}")

async def test_api_meta():
    """测试获取文件元数据 (API)"""
    if not baidu_api:
        print("❌ 请先初始化 BaiduApi (选项 1)")
        return
    
    path = input("请输入文件/目录路径 (例如: /课程目录系统内容展示): ").strip()
    if not path:
        path = "/课程目录系统内容展示"
    
    try:
        meta_info = await baidu_api.meta(path)
        print(f"✅ 元数据获取成功:")
        if 'list' in meta_info:
            for i, item in enumerate(meta_info['list']):
                print(f"   项目 {i+1}:")
                print(f"     文件名: {item.get('server_filename', 'Unknown')}")
                print(f"     路径: {item.get('path', 'Unknown')}")
                print(f"     大小: {item.get('size', 0)} 字节")
                print(f"     是否目录: {'是' if item.get('isdir') else '否'}")
                print(f"     fs_id: {item.get('fs_id', 'Unknown')}")
                print(f"     修改时间: {item.get('server_mtime', 'Unknown')}")
        else:
            print(f"   原始数据: {meta_info}")
    except Exception as e:
        print(f"❌ 获取元数据失败: {e}")

async def run_all_api_tests():
    """运行所有 BaiduApi 测试"""
    print("\n🚀 开始运行所有 BaiduApi 测试...")
    
    if not await init_baidu_api():
        return
    
    await test_api_user_info()
    print("\n" + "-"*40)
    await test_api_quota()
    print("\n" + "-"*40)
    await test_api_list_root()
    
    print("\n✅ 所有 BaiduApi 测试完成!")

async def run_all_client_tests():
    """运行所有 BaiduClient 测试"""
    print("\n🚀 开始运行所有 BaiduClient 测试...")
    
    if not await init_baidu_client():
        return
    
    await test_client_user_info()
    print("\n" + "-"*40)
    await test_client_disk_list()
    print("\n" + "-"*40)
    await test_client_relationship_list()
    
    print("\n✅ 所有 BaiduClient 测试完成!")

async def main():
    """主函数 - 交互式菜单"""
    print("🎉 欢迎使用百度网盘测试工具!")
    
    while True:
        print_menu()
        choice = input("请选择操作 (0-92): ").strip()
        
        if choice == "0":
            print("👋 再见!")
            break
        elif choice == "1":
            await init_baidu_api()
        elif choice == "2":
            await test_api_user_info()
        elif choice == "3":
            await test_api_quota()
        elif choice == "4":
            await test_api_list_root()
        elif choice == "5":
            await test_api_list_custom()
        elif choice == "6":
            await test_api_exists()
        elif choice == "7":
            await test_api_meta()
        elif choice == "11":
            await init_baidu_client()
        elif choice == "12":
            await test_client_user_info()
        elif choice == "13":
            await test_client_disk_list()
        elif choice == "14":
            await test_client_disk_list_recursive()
        elif choice == "15":
            await test_client_mkdir()
        elif choice == "16":
            await test_client_remove()
        elif choice == "17":
            await test_client_rename()
        elif choice == "18":
            await test_client_relationship_list()
        elif choice == "19":
            await test_client_share_list()
        elif choice == "20":
            await test_client_share_detail()
        elif choice == "21":
            await test_client_get_share_list()
        elif choice == "22":
            await test_client_transfer()
        elif choice == "91":
            await run_all_api_tests()
        elif choice == "92":
            await run_all_client_tests()
        else:
            print("❌ 无效选择，请重新输入!")
        
        # 等待用户按键继续
        input("\n按回车键继续...")

if __name__ == "__main__":
    # 运行交互式主函数
    asyncio.run(main())