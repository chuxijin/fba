import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';

/// HTTP 客户端单例
class HttpClient {
  static HttpClient? _instance;
  late Dio _dio;
  bool _isRefreshing = false;
  final List<Function> _pendingRequests = [];

  HttpClient._() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.apiBaseUrl,
        connectTimeout: const Duration(milliseconds: ApiConfig.connectTimeout),
        receiveTimeout: const Duration(milliseconds: ApiConfig.receiveTimeout),
        headers: {
          'Content-Type': 'application/json',
          'Accept-Language': 'zh-CN',
        },
      ),
    );

    // 日志拦截器 - 方便调试
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          print('🌐 请求: ${options.method} ${options.uri}');
          print('📤 Headers: ${options.headers}');
          if (options.data != null) {
            print('📦 Data: ${options.data}');
          }
          return handler.next(options);
        },
        onResponse: (response, handler) {
          print('✅ 响应: ${response.statusCode} ${response.requestOptions.uri}');
          print('📥 Data: ${response.data}');
          return handler.next(response);
        },
        onError: (error, handler) {
          print('❌ 错误: ${error.message}');
          print('🔗 URL: ${error.requestOptions.uri}');
          if (error.response != null) {
            print('📛 状态码: ${error.response?.statusCode}');
            print('📛 响应: ${error.response?.data}');
          }
          return handler.next(error);
        },
      ),
    );

    // 请求拦截器 - 自动添加 token
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // 自动添加 Authorization header
          final prefs = await SharedPreferences.getInstance();
          final token = prefs.getString('access_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onResponse: (response, handler) {
          // 检查响应格式
          if (response.data is Map<String, dynamic>) {
            final code = response.data['code'] as int?;
            // 如果 code 不是 200，视为业务错误
            if (code != null && code != 200) {
              final message = response.data['msg'] ?? response.data['message'] ?? 'Unknown error';
              return handler.reject(
                DioException(
                  requestOptions: response.requestOptions,
                  response: response,
                  type: DioExceptionType.badResponse,
                  error: message,
                ),
              );
            }
          }
          return handler.next(response);
        },
        onError: (error, handler) async {
          // 401 错误处理 - Token 过期
          if (error.response?.statusCode == 401) {
            // 尝试刷新 token
            if (!_isRefreshing) {
              _isRefreshing = true;

              try {
                // 调用刷新 token 接口
                final newToken = await _refreshToken();

                if (newToken != null) {
                  // 刷新成功，重试所有等待的请求
                  _isRefreshing = false;
                  _retryPendingRequests();

                  // 重试当前请求
                  error.requestOptions.headers['Authorization'] = 'Bearer $newToken';
                  final response = await _dio.fetch(error.requestOptions);
                  return handler.resolve(response);
                } else {
                  // 刷新失败，清除 token
                  await _clearAuth();
                  _isRefreshing = false;
                  return handler.next(error);
                }
              } catch (e) {
                // 刷新失败
                await _clearAuth();
                _isRefreshing = false;
                return handler.next(error);
              }
            } else {
              // 正在刷新中，将请求加入等待队列
              _pendingRequests.add(() async {
                final prefs = await SharedPreferences.getInstance();
                final token = prefs.getString('access_token');
                if (token != null) {
                  error.requestOptions.headers['Authorization'] = 'Bearer $token';
                  return _dio.fetch(error.requestOptions);
                }
              });
            }
          }

          // 403 错误 - 权限不足
          if (error.response?.statusCode == 403) {
            // 可以在这里处理权限不足的逻辑
          }

          return handler.next(error);
        },
      ),
    );
  }

  static HttpClient get instance {
    _instance ??= HttpClient._();
    return _instance!;
  }

  Dio get dio => _dio;

  /// 刷新 token
  Future<String?> _refreshToken() async {
    try {
      final response = await _dio.post(
        ApiConfig.refresh,
        options: Options(
          headers: {
            // 刷新接口使用 cookie 认证，不需要 Authorization header
          },
        ),
      );

      if (response.data is Map<String, dynamic>) {
        final data = response.data['data'] as Map<String, dynamic>?;
        if (data != null) {
          final accessToken = data['access_token'] as String?;
          final sessionUuid = data['session_uuid'] as String?;

          if (accessToken != null && sessionUuid != null) {
            // 保存新 token
            final prefs = await SharedPreferences.getInstance();
            await prefs.setString('access_token', accessToken);
            await prefs.setString('session_uuid', sessionUuid);
            return accessToken;
          }
        }
      }
    } catch (e) {
      print('Refresh token failed: $e');
    }
    return null;
  }

  /// 清除认证信息
  Future<void> _clearAuth() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('session_uuid');
  }

  /// 重试等待的请求
  void _retryPendingRequests() {
    for (final request in _pendingRequests) {
      request();
    }
    _pendingRequests.clear();
  }

  /// GET 请求
  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    return _dio.get<T>(
      path,
      queryParameters: queryParameters,
      options: options,
    );
  }

  /// POST 请求
  Future<Response<T>> post<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    return _dio.post<T>(
      path,
      data: data,
      queryParameters: queryParameters,
      options: options,
    );
  }
}
