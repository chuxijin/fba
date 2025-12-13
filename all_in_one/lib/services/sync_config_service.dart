import '../api/http_client.dart';
import '../config/api_config.dart';
import '../models/sync_config_models.dart';

/// 同步配置服务
class SyncConfigService {
  static final SyncConfigService _instance = SyncConfigService._internal();
  factory SyncConfigService() => _instance;
  SyncConfigService._internal();

  final HttpClient _httpClient = HttpClient.instance;

  /// 获取同步配置列表
  Future<SyncConfigPageData> getSyncConfigList({
    int page = 1,
    int size = 20,
    String? type,
    bool? enable,
    String? remark,
  }) async {
    final queryParams = <String, dynamic>{
      'page': page,
      'size': size,
    };

    if (type != null && type.isNotEmpty) {
      queryParams['type'] = type;
    }

    if (enable != null) {
      queryParams['enable'] = enable;
    }

    if (remark != null && remark.isNotEmpty) {
      queryParams['remark'] = remark;
    }

    final response = await _httpClient.get(
      ApiConfig.syncConfigList,
      queryParameters: queryParams,
    );

    // 检查response.data的结构
    if (response.data is Map<String, dynamic>) {
      final dataMap = response.data as Map<String, dynamic>;

      // 如果有items字段，直接解析
      if (dataMap.containsKey('items')) {
        return SyncConfigPageData.fromJson(response.data);
      }
      // 如果有data字段，说明response.data包含了整个响应对象
      else if (dataMap.containsKey('data')) {
        final actualData = dataMap['data'] as Map<String, dynamic>;
        return SyncConfigPageData.fromJson(actualData);
      }
    }

    return SyncConfigPageData.fromJson(response.data);
  }

  /// 创建同步配置
  Future<SyncConfig> createSyncConfig(Map<String, dynamic> data) async {
    final response = await _httpClient.dio.post(
      ApiConfig.syncConfigList,
      data: data,
    );

    if (response.statusCode == 200) {
      final responseData = response.data;
      if (responseData['code'] == 200 && responseData['data'] != null) {
        return SyncConfig.fromJson(responseData['data']);
      }
    }

    throw Exception('创建同步配置失败');
  }

  /// 更新同步配置
  Future<SyncConfig> updateSyncConfig(int configId, Map<String, dynamic> data) async {
    final response = await _httpClient.dio.put(
      '${ApiConfig.syncConfigList}/$configId',
      data: data,
    );

    if (response.statusCode == 200) {
      final responseData = response.data;
      if (responseData['code'] == 200 && responseData['data'] != null) {
        return SyncConfig.fromJson(responseData['data']);
      }
    }

    throw Exception('更新同步配置失败');
  }

  /// 删除同步配置
  Future<void> deleteSyncConfig(int configId) async {
    final response = await _httpClient.dio.delete(
      '${ApiConfig.syncConfigList}/$configId',
    );

    if (response.statusCode != 200) {
      throw Exception('删除同步配置失败');
    }
  }

  /// 执行同步任务
  Future<SyncExecutionResult> executeSyncTask(int configId) async {
    final response = await _httpClient.dio.post(
      '${ApiConfig.syncExecute}/$configId',
    );

    if (response.statusCode == 200) {
      final responseData = response.data;
      if (responseData['code'] == 200 && responseData['data'] != null) {
        return SyncExecutionResult.fromJson(responseData['data']);
      }
    }

    throw Exception('执行同步任务失败');
  }

  /// 取消同步任务
  Future<Map<String, dynamic>> cancelSyncTask(int taskId) async {
    final response = await _httpClient.dio.post(
      '${ApiConfig.syncTaskCancel}/$taskId/cancel',
    );

    if (response.statusCode == 200) {
      final responseData = response.data;
      if (responseData['code'] == 200 && responseData['data'] != null) {
        return responseData['data'] as Map<String, dynamic>;
      }
    }

    throw Exception('取消同步任务失败');
  }

  /// 获取同步任务列表
  Future<SyncTaskPageData> getSyncTasks({
    required int configId,
    int page = 1,
    int size = 20,
    String? status,
  }) async {
    final queryParams = <String, dynamic>{
      'page': page,
      'size': size,
    };

    if (status != null && status.isNotEmpty) {
      queryParams['status'] = status;
    }

    final response = await _httpClient.get(
      '${ApiConfig.syncTaskList}/$configId/tasks',
      queryParameters: queryParams,
    );

    // 检查response.data的结构
    if (response.data is Map<String, dynamic>) {
      final dataMap = response.data as Map<String, dynamic>;

      // 如果有data字段，说明response.data包含了整个响应对象
      if (dataMap.containsKey('data')) {
        final actualData = dataMap['data'] as Map<String, dynamic>;
        return SyncTaskPageData.fromJson(actualData);
      }
      // 如果有items字段，直接解析
      else if (dataMap.containsKey('items')) {
        return SyncTaskPageData.fromJson(response.data);
      }
    }

    return SyncTaskPageData.fromJson(response.data);
  }

  /// 获取同步任务详情
  Future<SyncTask> getSyncTaskDetail(int taskId) async {
    final response = await _httpClient.get(
      '${ApiConfig.syncTaskDetail}/$taskId',
    );

    if (response.data != null) {
      return SyncTask.fromJson(response.data);
    }

    throw Exception('获取同步任务详情失败');
  }

  /// 获取同步任务项列表
  Future<SyncTaskItemPageData> getSyncTaskItems({
    required int taskId,
    int page = 1,
    int size = 20,
    String? status,
    String? operationType,
  }) async {
    final queryParams = <String, dynamic>{
      'page': page,
      'size': size,
    };

    if (status != null && status.isNotEmpty) {
      queryParams['status'] = status;
    }

    if (operationType != null && operationType.isNotEmpty) {
      queryParams['operation_type'] = operationType;
    }

    final response = await _httpClient.get(
      '${ApiConfig.syncTaskDetail}/$taskId/items',
      queryParameters: queryParams,
    );

    // 检查response.data的结构
    if (response.data is Map<String, dynamic>) {
      final dataMap = response.data as Map<String, dynamic>;

      // 如果有data字段，说明response.data包含了整个响应对象
      if (dataMap.containsKey('data')) {
        final actualData = dataMap['data'] as Map<String, dynamic>;
        return SyncTaskItemPageData.fromJson(actualData);
      }
      // 如果有items字段，直接解析
      else if (dataMap.containsKey('items')) {
        return SyncTaskItemPageData.fromJson(response.data);
      }
    }

    return SyncTaskItemPageData.fromJson(response.data);
  }
}
