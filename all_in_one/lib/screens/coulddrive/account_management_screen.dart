import 'package:flutter/material.dart';
import 'package:bot_toast/bot_toast.dart';
import 'dart:math' as math;
import '../../constants/appflowy_colors.dart';
import '../../widgets/data_card_list.dart';
import '../../services/coulddrive_service.dart';
import '../../models/coulddrive_models.dart';

/// 账号管理页面
class AccountManagementScreen extends StatefulWidget {
  final Function(VoidCallback)? onSearchCallbackReady;

  const AccountManagementScreen({super.key, this.onSearchCallbackReady});

  @override
  State<AccountManagementScreen> createState() => _AccountManagementScreenState();
}

class _AccountManagementScreenState extends State<AccountManagementScreen> {
  final CoulddriveService _coulddriveService = CoulddriveService();

  // 搜索条件
  String? _selectedType;
  final TextEditingController _usernameController = TextEditingController();

  // DataCardList 控制器的 key，用于刷新列表
  final GlobalKey _listKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    // 注册搜索回调
    widget.onSearchCallbackReady?.call(showSearchDialog);
  }

  @override
  void dispose() {
    _usernameController.dispose();
    super.dispose();
  }

  /// 显示搜索对话框
  void showSearchDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('搜索账号'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // 用户名搜索
              TextField(
                controller: _usernameController,
                decoration: const InputDecoration(
                  labelText: '用户名',
                  hintText: '请输入用户名',
                  prefixIcon: Icon(Icons.person_outline),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              // 类型筛选
              DropdownButtonFormField<String?>(
                value: _selectedType,
                decoration: const InputDecoration(
                  labelText: '网盘类型',
                  prefixIcon: Icon(Icons.cloud_outlined),
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: null, child: Text('全部')),
                  DropdownMenuItem(value: 'baidu', child: Text('百度网盘')),
                  DropdownMenuItem(value: 'quark', child: Text('夸克网盘')),
                  DropdownMenuItem(value: 'aliyun', child: Text('阿里云盘')),
                ],
                onChanged: (value) {
                  setState(() {
                    _selectedType = value;
                  });
                },
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              setState(() {
                _usernameController.clear();
                _selectedType = null;
              });
              Navigator.pop(context);
              (_listKey.currentState as dynamic)?.refresh();
            },
            child: const Text('重置'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              (_listKey.currentState as dynamic)?.refresh();
            },
            child: const Text('搜索'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MediaQuery.removePadding(
      context: context,
      removeLeft: true,
      removeRight: true,
      child: DataCardList(
        key: _listKey,
        proxyConfig: ProxyConfig(
          ajax: (params) => _fetchAccounts(params),
          autoLoad: true,
          enablePagination: true,
          pageSize: 20,
        ),
        fields: [
          FieldConfig(
            field: 'custom_card',
            label: '',
            renderType: FieldRenderType.custom,
            showLabel: false,
            customRender: (value, row) => _buildCustomCard(row),
          ),
        ],
        actions: [],
        showIndex: false,
        primaryKey: 'id',
        cardMargin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        cardPadding: const EdgeInsets.all(12),
        showShadow: true,
      ),
    );
  }

  /// 构建自定义卡片
  Widget _buildCustomCard(Map<String, dynamic> row) {
    final quota = row['quota'] as int?;
    final used = row['used'] as int?;
    final percentage = (quota != null && used != null && quota > 0)
        ? (used / quota)
        : 0.0;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!, width: 1),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 第一行：头像 + 空间进度
            Row(
              children: [
                // 左侧：方形头像
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.network(
                    row['avatar_url'] ?? '',
                    width: 60,
                    height: 60,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) => Container(
                      width: 60,
                      height: 60,
                      color: AppFlowyColors.inputFill,
                      child: const Icon(
                        Icons.person_outlined,
                        size: 30,
                        color: AppFlowyColors.textTertiary,
                      ),
                    ),
                  ),
                ),
              const SizedBox(width: 16),

              // 右侧：用户名 + 环形进度
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 用户名
                    Text(
                      row['username'] ?? '',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: AppFlowyColors.textPrimary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    // 网盘类型
                    Text(
                      _getTypeLabel(row['type']),
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppFlowyColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),

              // 环形进度
              SizedBox(
                width: 60,
                height: 60,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    // 环形进度条
                    SizedBox(
                      width: 60,
                      height: 60,
                      child: CustomPaint(
                        painter: _CircularProgressPainter(
                          progress: percentage,
                          color: percentage > 0.9 ? Colors.red : AppFlowyColors.primary,
                        ),
                      ),
                    ),
                    // 中间文字
                    Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          '${(percentage * 100).toStringAsFixed(0)}%',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: AppFlowyColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // 空间信息
          Row(
            children: [
              const Icon(Icons.storage_outlined, size: 14, color: AppFlowyColors.textSecondary),
              const SizedBox(width: 4),
              Text(
                '${_formatFileSize(used)} / ${_formatFileSize(quota)}',
                style: const TextStyle(
                  fontSize: 12,
                  color: AppFlowyColors.textSecondary,
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // 第二行：VIP 状态和账号状态
          Row(
            children: [
              _buildVipTag(row['is_vip'] == true, row['is_supervip'] == true),
              const SizedBox(width: 8),
              _buildStatusTag(row['is_valid'] == true),
            ],
          ),

          const SizedBox(height: 12),
          const Divider(height: 1),
          const SizedBox(height: 8),

          // 第三行：操作按钮
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              _buildActionButton(
                icon: Icons.refresh_outlined,
                label: '刷新',
                color: AppFlowyColors.primary,
                onTap: () => _handleRefresh(row),
              ),
              const SizedBox(width: 12),
              _buildActionButton(
                icon: Icons.edit_outlined,
                label: '编辑',
                color: AppFlowyColors.primary,
                onTap: () => _handleEdit(row),
              ),
              const SizedBox(width: 12),
              _buildActionButton(
                icon: Icons.people_outlined,
                label: '关系',
                color: Colors.blue,
                onTap: () => _handleRelationship(row),
              ),
              const SizedBox(width: 12),
              _buildActionButton(
                icon: Icons.delete_outlined,
                label: '删除',
                color: Colors.red,
                onTap: () => _handleDelete(row),
              ),
            ],
          ),
        ],
      ),
      ),
    );
  }

  /// 构建 VIP 标签
  Widget _buildVipTag(bool isVip, bool isSuperVip) {
    if (isSuperVip) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.purple,
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Text(
          '超级会员',
          style: TextStyle(fontSize: 11, color: Colors.white),
        ),
      );
    } else if (isVip) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.amber,
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Text(
          'VIP',
          style: TextStyle(fontSize: 11, color: Colors.white),
        ),
      );
    } else {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.grey[300],
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Text(
          '普通用户',
          style: TextStyle(fontSize: 11, color: Colors.black87),
        ),
      );
    }
  }

  /// 构建状态标签
  Widget _buildStatusTag(bool isValid) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isValid ? Colors.green : Colors.red,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        isValid ? '有效' : '无效',
        style: const TextStyle(fontSize: 11, color: Colors.white),
      ),
    );
  }

  /// 构建操作按钮
  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(fontSize: 13, color: color),
          ),
        ],
      ),
    );
  }

  /// 获取网盘类型标签
  String _getTypeLabel(String? type) {
    switch (type) {
      case 'baidu':
        return '百度网盘';
      case 'quark':
        return '夸克网盘';
      case 'aliyun':
        return '阿里云盘';
      default:
        return type ?? '未知';
    }
  }

  /// 获取账号列表（真实 API）
  Future<ProxyResponse> _fetchAccounts(ProxyParams params) async {
    try {
      print('🔍 获取云盘账户列表: page=${params.page}, size=${params.pageSize}, type=$_selectedType');

      final pageData = await _coulddriveService.getUserList(
        page: params.page,
        size: params.pageSize,
        type: _selectedType,
        isValid: null, // 可以根据需要添加筛选条件
      );

      // 转换为 Map 格式
      final items = pageData.items.map((account) => account.toJson()).toList();

      print('✅ 获取到 ${items.length} 条数据，总计 ${pageData.total} 条');

      return ProxyResponse(items: items, total: pageData.total);
    } catch (e) {
      print('❌ 获取账号列表失败: $e');
      BotToast.showText(
        text: '加载失败: ${e.toString()}',
        contentColor: Colors.red,
        textStyle: const TextStyle(color: Colors.white, fontSize: 14),
      );
      return ProxyResponse(items: [], total: 0);
    }
  }

  /// 格式化文件大小
  String _formatFileSize(int? bytes) {
    if (bytes == null || bytes == 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    final i = (bytes.bitLength - 1) ~/ 10;
    return '${(bytes / (1 << (i * 10))).toStringAsFixed(2)} ${sizes[i]}';
  }

  /// 刷新账号
  Future<void> _handleRefresh(Map<String, dynamic> row) async {
    final userId = row['id'] as int;
    final username = row['username'] ?? '未知用户';

    try {
      BotToast.showText(text: '正在刷新账号: $username...');
      await _coulddriveService.refreshAccount(userId);
      BotToast.showText(
        text: '刷新成功',
        contentColor: Colors.green,
        textStyle: const TextStyle(color: Colors.white, fontSize: 14),
      );
      // 刷新列表
      (_listKey.currentState as dynamic)?.refresh();
    } catch (e) {
      BotToast.showText(
        text: '刷新失败: ${e.toString()}',
        contentColor: Colors.red,
        textStyle: const TextStyle(color: Colors.white, fontSize: 14),
      );
    }
  }

  /// 编辑账号
  Future<void> _handleEdit(Map<String, dynamic> row) async {
    final userId = row['id'] as int;
    final username = row['username'] ?? '未知用户';
    final type = row['type'] as String;
    final currentCookies = row['cookies'] as String?;

    // 显示编辑对话框
    final cookiesController = TextEditingController(text: currentCookies ?? '');

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('编辑账号: $username'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '网盘类型: ${_getTypeLabel(type)}',
                style: const TextStyle(
                  fontSize: 14,
                  color: AppFlowyColors.textSecondary,
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: cookiesController,
                decoration: const InputDecoration(
                  labelText: '认证令牌 (Cookies)',
                  hintText: '请输入新的认证令牌',
                  border: OutlineInputBorder(),
                  helperText: '更新认证信息后将自动刷新用户数据',
                ),
                maxLines: 3,
                style: const TextStyle(fontSize: 14),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(
              foregroundColor: AppFlowyColors.primary,
            ),
            child: const Text('保存'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      final newCookies = cookiesController.text.trim();
      if (newCookies.isEmpty) {
        BotToast.showText(
          text: '认证令牌不能为空',
          contentColor: Colors.orange,
          textStyle: const TextStyle(color: Colors.white, fontSize: 14),
        );
        return;
      }

      try {
        BotToast.showText(text: '正在更新账号信息...');

        // 调用刷新API（后端会使用新的cookies更新用户信息）
        await _coulddriveService.refreshAccount(userId);

        BotToast.showText(
          text: '账号信息更新成功',
          contentColor: Colors.green,
          textStyle: const TextStyle(color: Colors.white, fontSize: 14),
        );
        // 刷新列表
        (_listKey.currentState as dynamic)?.refresh();
      } catch (e) {
        BotToast.showText(
          text: '更新失败: ${e.toString()}',
          contentColor: Colors.red,
          textStyle: const TextStyle(color: Colors.white, fontSize: 14),
        );
      }
    }

    cookiesController.dispose();
  }

  /// 查看关系
  Future<void> _handleRelationship(Map<String, dynamic> row) async {
    final username = row['username'] ?? '未知用户';
    final cookies = row['cookies'] as String?;
    final type = row['type'] as String;

    if (cookies == null || cookies.isEmpty) {
      BotToast.showText(
        text: '用户认证信息不完整',
        contentColor: Colors.orange,
        textStyle: const TextStyle(color: Colors.white, fontSize: 14),
      );
      return;
    }

    // 显示关系列表对话框
    showDialog(
      context: context,
      builder: (context) => _RelationshipDialog(
        username: username,
        cookies: cookies,
        driveType: type,
        coulddriveService: _coulddriveService,
      ),
    );
  }

  /// 删除账号
  Future<void> _handleDelete(Map<String, dynamic> row) async {
    final userId = row['id'] as int;
    final username = row['username'] ?? '未知用户';

    // 显示确认对话框
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('确认删除'),
        content: Text('确定要删除账号 "$username" 吗？此操作不可撤销。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(
              foregroundColor: Colors.red,
            ),
            child: const Text('删除'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      try {
        await _coulddriveService.deleteAccount(userId);
        BotToast.showText(
          text: '删除成功',
          contentColor: Colors.green,
          textStyle: const TextStyle(color: Colors.white, fontSize: 14),
        );
        // 刷新列表
        (_listKey.currentState as dynamic)?.refresh();
      } catch (e) {
        BotToast.showText(
          text: '删除失败: ${e.toString()}',
          contentColor: Colors.red,
          textStyle: const TextStyle(color: Colors.white, fontSize: 14),
        );
      }
    }
  }

}

/// 环形进度条画笔
class _CircularProgressPainter extends CustomPainter {
  final double progress;
  final Color color;

  _CircularProgressPainter({
    required this.progress,
    required this.color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 4;

    // 背景圆环
    final bgPaint = Paint()
      ..color = Colors.grey[200]!
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, radius, bgPaint);

    // 进度圆环
    final progressPaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;

    final sweepAngle = 2 * math.pi * progress;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      sweepAngle,
      false,
      progressPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _CircularProgressPainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.color != color;
  }
}

/// 关系列表对话框
class _RelationshipDialog extends StatefulWidget {
  final String username;
  final String cookies;
  final String driveType;
  final CoulddriveService coulddriveService;

  const _RelationshipDialog({
    required this.username,
    required this.cookies,
    required this.driveType,
    required this.coulddriveService,
  });

  @override
  State<_RelationshipDialog> createState() => _RelationshipDialogState();
}

class _RelationshipDialogState extends State<_RelationshipDialog>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<FriendInfo> _friendList = [];
  List<GroupInfo> _groupList = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(_onTabChanged);
    // 默认加载好友列表
    _loadFriendList();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (_tabController.index == 0 && _friendList.isEmpty) {
      _loadFriendList();
    } else if (_tabController.index == 1 && _groupList.isEmpty) {
      _loadGroupList();
    }
  }

  Future<void> _loadFriendList() async {
    if (_isLoading) return;

    setState(() {
      _isLoading = true;
    });

    try {
      final data = await widget.coulddriveService.getRelationshipList(
        cookies: widget.cookies,
        driveType: widget.driveType,
        relationshipType: 'friend',
      );

      if (mounted) {
        setState(() {
          _friendList = data.items.cast<FriendInfo>();
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
        BotToast.showText(
          text: '获取好友列表失败: ${e.toString()}',
          contentColor: Colors.red,
          textStyle: const TextStyle(color: Colors.white, fontSize: 14),
        );
      }
    }
  }

  Future<void> _loadGroupList() async {
    if (_isLoading) return;

    setState(() {
      _isLoading = true;
    });

    try {
      final data = await widget.coulddriveService.getRelationshipList(
        cookies: widget.cookies,
        driveType: widget.driveType,
        relationshipType: 'group',
      );

      if (mounted) {
        setState(() {
          _groupList = data.items.cast<GroupInfo>();
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
        BotToast.showText(
          text: '获取群组列表失败: ${e.toString()}',
          contentColor: Colors.red,
          textStyle: const TextStyle(color: Colors.white, fontSize: 14),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: Container(
        width: 600,
        height: 600,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            // 标题栏
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppFlowyColors.surface,
                borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      '${widget.username} 的关系列表',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppFlowyColors.textPrimary,
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close),
                    iconSize: 20,
                  ),
                ],
              ),
            ),

            // Tab 栏
            TabBar(
              controller: _tabController,
              labelColor: AppFlowyColors.primary,
              unselectedLabelColor: AppFlowyColors.textSecondary,
              indicatorColor: AppFlowyColors.primary,
              tabs: [
                Tab(text: '好友列表 (${_friendList.length})'),
                Tab(text: '群组列表 (${_groupList.length})'),
              ],
            ),

            // Tab 内容
            Expanded(
              child: _isLoading
                  ? const Center(
                      child: CircularProgressIndicator(
                        color: AppFlowyColors.primary,
                      ),
                    )
                  : TabBarView(
                      controller: _tabController,
                      children: [
                        _buildFriendList(),
                        _buildGroupList(),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFriendList() {
    if (_friendList.isEmpty) {
      return const Center(
        child: Text(
          '暂无好友',
          style: TextStyle(color: AppFlowyColors.textSecondary),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _friendList.length,
      itemBuilder: (context, index) {
        final friend = _friendList[index];
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppFlowyColors.surface,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              // 头像
              ClipOval(
                child: Image.network(
                  friend.avatarUrl,
                  width: 40,
                  height: 40,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) => Container(
                    width: 40,
                    height: 40,
                    color: AppFlowyColors.inputFill,
                    child: const Icon(
                      Icons.person,
                      color: AppFlowyColors.textTertiary,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              // 信息
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      friend.uname,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppFlowyColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      friend.nickName.isEmpty ? '无昵称' : friend.nickName,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppFlowyColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              // ID
              Text(
                'ID: ${friend.uk}',
                style: const TextStyle(
                  fontSize: 11,
                  color: AppFlowyColors.textTertiary,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildGroupList() {
    if (_groupList.isEmpty) {
      return const Center(
        child: Text(
          '暂无群组',
          style: TextStyle(color: AppFlowyColors.textSecondary),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _groupList.length,
      itemBuilder: (context, index) {
        final group = _groupList[index];
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppFlowyColors.surface,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              // 群图标
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: Colors.green.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Center(
                  child: Text(
                    '群',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: Colors.green,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              // 信息
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      group.name,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppFlowyColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '群号: ${group.gnum}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppFlowyColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              // ID
              Text(
                'ID: ${group.gid}',
                style: const TextStyle(
                  fontSize: 11,
                  color: AppFlowyColors.textTertiary,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
