/// API 配置
class ApiConfig {
  /// 基础URL - 请修改为您的后端地址
  /// localhost: 仅用于本地开发（Web、桌面）
  /// 192.168.1.53: 用于局域网内的移动设备访问
  /// admin.yzxj.vip: 线上生产环境
  static const String baseUrl = 'https://admin.yzxj.vip';

  /// API 版本
  static const String apiVersion = '/api/v1';

  /// 完整 API 基础路径
  static String get apiBaseUrl => '$baseUrl$apiVersion';

  /// 超时时间（毫秒）
  static const int connectTimeout = 30000;
  static const int receiveTimeout = 30000;

  /// API 端点
  static const String captcha = '/auth/captcha';
  static const String login = '/auth/login';
  static const String logout = '/auth/logout';
  static const String refresh = '/auth/refresh';
  static const String codes = '/auth/codes';
  static const String currentUser = '/sys/users/me'; // 获取当前用户信息

  /// 云盘相关端点
  static const String coulddriveUserList = '/coulduser/userlist'; // 获取云盘账户列表
  static const String coulddriveUserRefresh = '/coulduser'; // 刷新云盘账户信息
  static const String coulddriveUserDelete = '/coulduser'; // 删除云盘账户
  static const String coulddriveRelationshipList = '/coulduser/relationshiplist'; // 获取关系列表

  /// 云盘同步相关端点
  static const String syncConfigList = '/couldsync/config'; // 同步配置列表
  static const String syncExecute = '/couldsync/execute'; // 执行同步
  static const String syncTaskCancel = '/couldsync/task'; // 取消同步任务
  static const String syncTaskList = '/couldsync'; // 同步任务列表
  static const String syncTaskDetail = '/couldsync/task'; // 同步任务详情
}
