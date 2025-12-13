import 'package:flutter/material.dart';
import 'package:bot_toast/bot_toast.dart';
import '../../constants/appflowy_colors.dart';
import '../coulddrive/account_management_screen.dart';

/// 工作 Tab（AppFlowy 风格，使用 IndexedStack 管理子页面）
class WorkTab extends StatefulWidget {
  const WorkTab({super.key});

  @override
  State<WorkTab> createState() => _WorkTabState();
}

class _WorkTabState extends State<WorkTab> with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _slideAnimation;
  bool _isDrawerOpen = false;
  int _currentPageIndex = 0; // 当前页面索引：0=工作台首页, 1=账号管理

  // 页面配置
  final List<_PageConfig> _pages = [
    _PageConfig(title: '工作', page: null), // null 表示使用内联的工作台首页
    _PageConfig(title: '账号管理', page: const AccountManagementScreen()),
  ];

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _slideAnimation = Tween<double>(begin: 0, end: 0.2).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  /// 切换侧边栏
  void _toggleDrawer() {
    setState(() {
      _isDrawerOpen = !_isDrawerOpen;
      if (_isDrawerOpen) {
        _animationController.forward();
      } else {
        _animationController.reverse();
      }
    });
  }

  /// 切换页面
  void _switchPage(int index) {
    setState(() {
      _currentPageIndex = index;
      _isDrawerOpen = false;
    });
    _animationController.reverse();
  }

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final drawerWidth = screenWidth * 0.25;
    final currentPage = _pages[_currentPageIndex];

    return Scaffold(
      backgroundColor: AppFlowyColors.background,
      body: Stack(
        children: [
          // 主内容区域（底层）
          AnimatedBuilder(
            animation: _slideAnimation,
            builder: (context, child) {
              return Transform.translate(
                offset: Offset(screenWidth * _slideAnimation.value, 0),
                child: child,
              );
            },
            child: GestureDetector(
              onTap: _isDrawerOpen ? _toggleDrawer : null,
              onHorizontalDragEnd: (details) {
                if (details.primaryVelocity != null) {
                  if (details.primaryVelocity! > 0 && !_isDrawerOpen) {
                    _toggleDrawer();
                  } else if (details.primaryVelocity! < 0 && _isDrawerOpen) {
                    _toggleDrawer();
                  }
                }
              },
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  boxShadow: _isDrawerOpen
                      ? [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.2),
                            blurRadius: 20,
                            offset: const Offset(-5, 0),
                          ),
                        ]
                      : [],
                ),
                child: Scaffold(
                  appBar: AppBar(
                    title: Text(currentPage.title),
                    backgroundColor: AppFlowyColors.surface,
                    foregroundColor: AppFlowyColors.textPrimary,
                    elevation: 0,
                    toolbarHeight: 56,
                    titleTextStyle: const TextStyle(
                      color: AppFlowyColors.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      letterSpacing: -0.2,
                    ),
                    leading: IconButton(
                      icon: Icon(
                        _isDrawerOpen ? Icons.close : Icons.menu_rounded,
                        color: AppFlowyColors.textSecondary,
                        size: 22,
                      ),
                      onPressed: _toggleDrawer,
                    ),
                    bottom: PreferredSize(
                      preferredSize: const Size.fromHeight(1),
                      child: Container(
                        height: 1,
                        color: AppFlowyColors.divider,
                      ),
                    ),
                  ),
                  body: Stack(
                    children: [
                      // 使用 IndexedStack 保持页面状态，无动画切换
                      IndexedStack(
                        index: _currentPageIndex,
                        children: [
                          _buildWorkHomePage(), // 工作台首页
                          const AccountManagementScreen(), // 账号管理
                        ],
                      ),
                      // 半透明遮罩层（仅在侧边栏打开时显示）
                      if (_isDrawerOpen)
                        Positioned.fill(
                          child: GestureDetector(
                            onTap: _toggleDrawer,
                            child: Container(
                              color: Colors.black.withValues(alpha: 0.3),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          // 侧边栏（顶层，覆盖在主内容上方）
          AnimatedBuilder(
            animation: _slideAnimation,
            builder: (context, child) {
              return Transform.translate(
                offset: Offset(-drawerWidth + (drawerWidth * _slideAnimation.value / 0.2), 0),
                child: child,
              );
            },
            child: _buildDrawer(context, drawerWidth),
          ),
        ],
      ),
    );
  }

  /// 构建侧边栏
  Widget _buildDrawer(BuildContext context, double drawerWidth) {
    return Container(
      width: drawerWidth,
      decoration: BoxDecoration(
        color: AppFlowyColors.sidebarBackground,
        border: Border(
          right: BorderSide(
            color: AppFlowyColors.border,
            width: 1,
          ),
        ),
      ),
      child: SafeArea(
        child: Column(
          children: [
            // 简洁的头部
            Padding(
              padding: EdgeInsets.all(AppFlowySpacing.lg),
              child: Row(
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      gradient: AppFlowyColors.primaryGradient,
                      borderRadius: BorderRadius.circular(AppFlowyRadius.medium),
                    ),
                    child: const Icon(
                      Icons.work_rounded,
                      color: Colors.white,
                      size: 18,
                    ),
                  ),
                  SizedBox(width: AppFlowySpacing.md),
                  const Expanded(
                    child: Text(
                      '工作台',
                      style: TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w600,
                        color: AppFlowyColors.textPrimary,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            Divider(
              height: 1,
              thickness: 1,
              color: AppFlowyColors.divider,
            ),

            // 菜单列表
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(vertical: 8),
                children: [
                  // 工作台
                  _buildMenuItem(
                    icon: Icons.home_outlined,
                    title: '工作台',
                    isActive: _currentPageIndex == 0,
                    onTap: () => _switchPage(0),
                  ),

                  const Divider(height: 16, indent: 16, endIndent: 16),

                  // 网盘管理（带子菜单）
                  _buildExpandableMenuItem(
                    icon: Icons.cloud_outlined,
                    activeIcon: Icons.cloud_rounded,
                    title: '网盘管理',
                    subItems: [
                      _SubMenuItem(
                        icon: Icons.sync_rounded,
                        title: '网盘同步',
                        isActive: false,
                        onTap: () {
                          _toggleDrawer();
                          _showToast('网盘同步功能开发中...');
                        },
                      ),
                      _SubMenuItem(
                        icon: Icons.manage_accounts_rounded,
                        title: '账号管理',
                        isActive: _currentPageIndex == 1,
                        onTap: () => _switchPage(1),
                      ),
                    ],
                  ),

                  // 照片管理
                  _buildMenuItem(
                    icon: Icons.photo_library_outlined,
                    title: '照片管理',
                    isActive: false,
                    onTap: () {
                      _toggleDrawer();
                      _showToast('照片管理功能开发中...');
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 构建可展开菜单项
  Widget _buildExpandableMenuItem({
    required IconData icon,
    required IconData activeIcon,
    required String title,
    required List<_SubMenuItem> subItems,
  }) {
    return Theme(
      data: Theme.of(context).copyWith(
        dividerColor: Colors.transparent,
        splashColor: AppFlowyColors.primary.withValues(alpha: 0.05),
        highlightColor: AppFlowyColors.primary.withValues(alpha: 0.08),
      ),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.only(left: 12, right: 8, top: 4, bottom: 4),
        leading: Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: AppFlowyColors.primary.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: AppFlowyColors.primary, size: 20),
        ),
        title: Text(
          title,
          style: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w500,
            color: AppFlowyColors.textPrimary,
          ),
        ),
        trailing: Icon(
          Icons.keyboard_arrow_down_rounded,
          color: AppFlowyColors.textSecondary,
          size: 24,
        ),
        iconColor: AppFlowyColors.primary,
        collapsedIconColor: AppFlowyColors.textSecondary,
        childrenPadding: const EdgeInsets.only(bottom: 8),
        children: subItems.map((subItem) {
          return InkWell(
            onTap: subItem.onTap,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              margin: const EdgeInsets.only(left: 12, right: 12, top: 2),
              decoration: BoxDecoration(
                color: subItem.isActive ? AppFlowyColors.primary.withValues(alpha: 0.1) : null,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const SizedBox(width: 40),
                  Icon(
                    subItem.icon,
                    color: subItem.isActive ? AppFlowyColors.primary : AppFlowyColors.textSecondary,
                    size: 18,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      subItem.title,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: subItem.isActive ? FontWeight.w600 : FontWeight.normal,
                        color: subItem.isActive ? AppFlowyColors.primary : AppFlowyColors.textPrimary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  /// 构建普通菜单项
  Widget _buildMenuItem({
    required IconData icon,
    required String title,
    bool isActive = false,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      splashColor: Colors.transparent,
      highlightColor: AppFlowyColors.hoverBackground,
      borderRadius: BorderRadius.circular(AppFlowyRadius.small),
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: AppFlowySpacing.md,
          vertical: AppFlowySpacing.sm + 2,
        ),
        margin: EdgeInsets.symmetric(horizontal: AppFlowySpacing.sm, vertical: 1),
        decoration: BoxDecoration(
          color: isActive ? AppFlowyColors.selectedBackground : Colors.transparent,
          borderRadius: BorderRadius.circular(AppFlowyRadius.small),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              color: isActive ? AppFlowyColors.primary : AppFlowyColors.textSecondary,
              size: 18,
            ),
            SizedBox(width: AppFlowySpacing.md),
            Expanded(
              child: Text(
                title,
                style: TextStyle(
                  fontSize: AppFlowyFontSize.sm,
                  fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                  color: isActive ? AppFlowyColors.primary : AppFlowyColors.textPrimary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 构建工作主页
  Widget _buildWorkHomePage() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 欢迎标题
          const Text(
            '工作台',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: AppFlowyColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '概览和快捷入口',
            style: TextStyle(
              fontSize: 14,
              color: AppFlowyColors.textSecondary,
            ),
          ),
          const SizedBox(height: 24),

          // 统计卡片区域
          const Text(
            '账号统计',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppFlowyColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),

          // 第一行卡片（2列）
          Row(
            children: [
              Expanded(
                child: _buildStatCard(
                  icon: Icons.people_outlined,
                  iconColor: Colors.blue,
                  title: '总账号数',
                  value: '12',
                  bgColor: Colors.blue.withValues(alpha: 0.1),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildStatCard(
                  icon: Icons.check_circle_outline,
                  iconColor: Colors.green,
                  title: '有效账号',
                  value: '10',
                  bgColor: Colors.green.withValues(alpha: 0.1),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // 第二行卡片（2列）
          Row(
            children: [
              Expanded(
                child: _buildStatCard(
                  icon: Icons.storage_outlined,
                  iconColor: Colors.purple,
                  title: '总空间',
                  value: '2.5 TB',
                  bgColor: Colors.purple.withValues(alpha: 0.1),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildStatCard(
                  icon: Icons.pie_chart_outline,
                  iconColor: Colors.orange,
                  title: '已用空间',
                  value: '1.2 TB',
                  subtitle: '48%',
                  bgColor: Colors.orange.withValues(alpha: 0.1),
                ),
              ),
            ],
          ),

          const SizedBox(height: 32),

          // 快捷功能区域
          const Text(
            '快捷功能',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppFlowyColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),

          _buildQuickActionCard(
            icon: Icons.manage_accounts_rounded,
            iconColor: AppFlowyColors.primary,
            title: '账号管理',
            subtitle: '管理网盘账号',
            onTap: () => _switchPage(1),
          ),
          const SizedBox(height: 12),

          _buildQuickActionCard(
            icon: Icons.sync_rounded,
            iconColor: Colors.blue,
            title: '网盘同步',
            subtitle: '同步文件到云盘',
            onTap: () {
              _showToast('网盘同步功能开发中...');
            },
          ),
          const SizedBox(height: 12),

          _buildQuickActionCard(
            icon: Icons.photo_library_outlined,
            iconColor: Colors.pink,
            title: '照片管理',
            subtitle: '管理和备份照片',
            onTap: () {
              _showToast('照片管理功能开发中...');
            },
          ),
        ],
      ),
    );
  }

  /// 构建统计卡片
  Widget _buildStatCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String value,
    String? subtitle,
    required Color bgColor,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: bgColor,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: iconColor, size: 24),
          ),
          const SizedBox(height: 12),
          Text(
            title,
            style: const TextStyle(
              fontSize: 13,
              color: AppFlowyColors.textSecondary,
            ),
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Text(
                value,
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: AppFlowyColors.textPrimary,
                ),
              ),
              if (subtitle != null) ...[
                const SizedBox(width: 8),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 14,
                    color: AppFlowyColors.textSecondary,
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  /// 构建快捷操作卡片
  Widget _buildQuickActionCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: iconColor, size: 24),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppFlowyColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppFlowyColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              color: AppFlowyColors.textTertiary,
              size: 24,
            ),
          ],
        ),
      ),
    );
  }

  /// 显示 Toast
  void _showToast(String message) {
    BotToast.showText(
      text: message,
      contentColor: AppFlowyColors.primary,
      textStyle: const TextStyle(color: Colors.white, fontSize: 14),
    );
  }
}

/// 子菜单项数据类
class _SubMenuItem {
  final IconData icon;
  final String title;
  final bool isActive;
  final VoidCallback onTap;

  _SubMenuItem({
    required this.icon,
    required this.title,
    this.isActive = false,
    required this.onTap,
  });
}

/// 页面配置类
class _PageConfig {
  final String title;
  final Widget? page;

  _PageConfig({
    required this.title,
    this.page,
  });
}
