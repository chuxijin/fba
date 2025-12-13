import '../api/auth_service.dart';
import '../models/auth_models.dart';

/// 用户服务 - 单例模式，管理用户信息缓存
class UserService {
  static final UserService _instance = UserService._internal();
  factory UserService() => _instance;
  UserService._internal();

  final AuthService _authService = AuthService();

  // 缓存的用户信息
  UserInfo? _cachedUserInfo;

  // 是否正在加载
  bool _isLoading = false;

  /// 获取用户信息（带缓存）
  Future<UserInfo> getUserInfo({bool forceRefresh = false}) async {
    // 如果有缓存且不强制刷新，直接返回缓存
    if (_cachedUserInfo != null && !forceRefresh) {
      return _cachedUserInfo!;
    }

    // 如果正在加载，等待加载完成
    if (_isLoading) {
      // 简单的轮询等待，实际项目可以用 Completer
      while (_isLoading) {
        await Future.delayed(const Duration(milliseconds: 100));
      }
      return _cachedUserInfo!;
    }

    // 开始加载
    _isLoading = true;
    try {
      final userInfo = await _authService.getCurrentUser();
      _cachedUserInfo = userInfo;
      return userInfo;
    } finally {
      _isLoading = false;
    }
  }

  /// 清除缓存（退出登录时调用）
  void clearCache() {
    _cachedUserInfo = null;
  }

  /// 更新缓存
  void updateCache(UserInfo userInfo) {
    _cachedUserInfo = userInfo;
  }

  /// 获取缓存的用户信息（不请求网络）
  UserInfo? getCachedUserInfo() {
    return _cachedUserInfo;
  }
}
