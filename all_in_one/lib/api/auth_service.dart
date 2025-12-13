import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';
import '../models/auth_models.dart';
import 'http_client.dart';

/// 认证 API 服务
class AuthService {
  final HttpClient _httpClient = HttpClient.instance;

  /// 获取验证码
  Future<CaptchaResponse> getCaptcha() async {
    final response = await _httpClient.get(ApiConfig.captcha);
    return CaptchaResponse.fromJson(response.data);
  }

  /// 用户登录
  Future<LoginResponse> login(LoginRequest request) async {
    final response = await _httpClient.post(
      ApiConfig.login,
      data: request.toJson(),
    );
    final loginResponse = LoginResponse.fromJson(response.data);

    // 保存 token 到本地
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', loginResponse.accessToken);
    await prefs.setString('session_uuid', loginResponse.sessionUuid);

    return loginResponse;
  }

  /// 用户登出
  Future<void> logout() async {
    try {
      await _httpClient.post(ApiConfig.logout);
    } finally {
      // 清除本地存储
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('access_token');
      await prefs.remove('session_uuid');
    }
  }

  /// 刷新 token
  Future<LoginResponse> refreshToken() async {
    final response = await _httpClient.post(ApiConfig.refresh);
    final loginResponse = LoginResponse.fromJson(response.data);

    // 更新 token
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', loginResponse.accessToken);
    await prefs.setString('session_uuid', loginResponse.sessionUuid);

    return loginResponse;
  }

  /// 获取权限码
  Future<List<String>> getCodes() async {
    final response = await _httpClient.get(ApiConfig.codes);
    final data = response.data['data'] as List;
    return data.map((e) => e.toString()).toList();
  }

  /// 检查是否已登录
  Future<bool> isLoggedIn() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey('access_token');
  }

  /// 获取当前 token
  Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('access_token');
  }

  /// 获取当前用户信息
  Future<UserInfo> getCurrentUser() async {
    final response = await _httpClient.get(ApiConfig.currentUser);
    return UserInfo.fromJson(response.data);
  }
}
