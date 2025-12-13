import 'package:flutter/material.dart';
import 'package:bot_toast/bot_toast.dart';
import '../../constants/app_colors.dart';
import '../../api/auth_service.dart';
import '../../services/user_service.dart';
import '../../models/auth_models.dart';
import '../login_screen.dart';

/// 我的 Tab
class MineTab extends StatefulWidget {
  const MineTab({super.key});

  @override
  State<MineTab> createState() => _MineTabState();
}

class _MineTabState extends State<MineTab> {
  final AuthService _authService = AuthService();
  final UserService _userService = UserService();
  UserInfo? _userInfo;
  bool _isLoading = true;
  bool _isLogoutLoading = false;
  bool _isRefreshing = false;

  @override
  void initState() {
    super.initState();
    _loadUserInfo();
  }

  /// 加载用户信息（使用缓存）
  Future<void> _loadUserInfo({bool forceRefresh = false}) async {
    print('🔍 开始加载用户信息... (forceRefresh: $forceRefresh)');

    // 先尝试从缓存获取
    if (!forceRefresh) {
      final cached = _userService.getCachedUserInfo();
      if (cached != null) {
        print('✅ 使用缓存的用户信息: ${cached.username}');
        if (mounted) {
          setState(() {
            _userInfo = cached;
            _isLoading = false;
          });
        }
        return;
      }
    }

    try {
      final userInfo = await _userService.getUserInfo(forceRefresh: forceRefresh);
      print('✅ 用户信息加载成功: ${userInfo.username}');
      if (mounted) {
        setState(() {
          _userInfo = userInfo;
          _isLoading = false;
          _isRefreshing = false;
        });
      }
    } catch (e) {
      print('❌ 加载用户信息失败: $e');
      if (mounted) {
        setState(() {
          _isLoading = false;
          _isRefreshing = false;
        });
        // 如果是401未授权,可能token过期了
        if (e.toString().contains('401')) {
          print('⚠️ Token过期,跳转登录页');
          _navigateToLogin();
        } else {
          // 显示错误提示
          BotToast.showText(
            text: '加载用户信息失败',
            contentColor: AppColors.error,
            textStyle: const TextStyle(color: Colors.white, fontSize: 14),
          );
        }
      }
    }
  }

  /// 下拉刷新
  Future<void> _handleRefresh() async {
    setState(() {
      _isRefreshing = true;
    });
    await _loadUserInfo(forceRefresh: true);
  }

  /// 退出登录
  Future<void> _handleLogout() async {
    setState(() {
      _isLogoutLoading = true;
    });

    try {
      await _authService.logout();

      // 清除用户信息缓存
      _userService.clearCache();

      if (mounted) {
        _navigateToLogin();

        BotToast.showText(
          text: '退出成功',
          contentColor: AppColors.success,
          textStyle: const TextStyle(color: Colors.white, fontSize: 14),
        );
      }
    } catch (e) {
      BotToast.showText(
        text: '退出失败: ${e.toString()}',
        contentColor: AppColors.error,
        textStyle: const TextStyle(color: Colors.white, fontSize: 14),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLogoutLoading = false;
        });
      }
    }
  }

  /// 导航到登录页
  void _navigateToLogin() {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (context) => const LoginScreen()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('我的'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: _isLoading
          ? const Center(
              child: CircularProgressIndicator(
                color: AppColors.primary,
              ),
            )
          : RefreshIndicator(
              onRefresh: _handleRefresh,
              color: AppColors.primary,
              child: ListView(
              children: [
                // 用户头像区域
                Container(
                  padding: const EdgeInsets.all(24),
                  color: AppColors.surface,
                  child: Row(
                    children: [
                      // 头像
                      _userInfo?.avatar != null
                          ? CircleAvatar(
                              radius: 40,
                              backgroundImage: NetworkImage(_userInfo!.avatar!),
                              onBackgroundImageError: (_, __) {},
                              child: _userInfo!.avatar!.isEmpty
                                  ? const Icon(Icons.person, size: 40, color: Colors.white)
                                  : null,
                            )
                          : CircleAvatar(
                              radius: 40,
                              backgroundColor: AppColors.primary,
                              child: Text(
                                _userInfo?.nickname.substring(0, 1) ?? '?',
                                style: const TextStyle(
                                  fontSize: 28,
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _userInfo?.nickname ?? '未登录',
                              style: const TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '@${_userInfo?.username ?? ''}',
                              style: const TextStyle(
                                fontSize: 14,
                                color: AppColors.textSecondary,
                              ),
                            ),
                            if (_userInfo?.email != null) ...[
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  const Icon(
                                    Icons.email_outlined,
                                    size: 14,
                                    color: AppColors.textTertiary,
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    _userInfo!.email!,
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: AppColors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ],
                        ),
                      ),
                      // 超级管理员标签
                      if (_userInfo?.isSuperuser == true)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.error.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(4),
                            border: Border.all(
                              color: AppColors.error.withValues(alpha: 0.3),
                            ),
                          ),
                          child: const Text(
                            '超管',
                            style: TextStyle(
                              fontSize: 11,
                              color: AppColors.error,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),

          const SizedBox(height: 10),

          // 功能列表
          _buildMenuItem(
            icon: Icons.settings,
            title: '设置',
            onTap: () {
              BotToast.showText(text: '设置功能开发中...');
            },
          ),
          _buildMenuItem(
            icon: Icons.help_outline,
            title: '帮助与反馈',
            onTap: () {
              BotToast.showText(text: '帮助功能开发中...');
            },
          ),
          _buildMenuItem(
            icon: Icons.info_outline,
            title: '关于',
            onTap: () {
              BotToast.showText(text: '关于功能开发中...');
            },
          ),

          const SizedBox(height: 20),

          // 退出登录按钮
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            child: SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                onPressed: _isLogoutLoading ? null : _handleLogout,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.error,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: _isLogoutLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Text(
                        '退出登录',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
            ),
          ),
        ],
      ),
            ),
    );
  }

  /// 构建菜单项
  Widget _buildMenuItem({
    required IconData icon,
    required String title,
    required VoidCallback onTap,
  }) {
    return ListTile(
      leading: Icon(icon, color: AppColors.textSecondary),
      title: Text(
        title,
        style: const TextStyle(
          fontSize: 16,
          color: AppColors.textPrimary,
        ),
      ),
      trailing: const Icon(
        Icons.chevron_right,
        color: AppColors.textTertiary,
      ),
      onTap: onTap,
    );
  }
}
