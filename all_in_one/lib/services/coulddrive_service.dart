import 'package:dio/dio.dart';
import '../api/http_client.dart';
import '../config/api_config.dart';
import '../models/coulddrive_models.dart';

/// 云盘账户服务 - 单例模式
class CoulddriveService {
  static final CoulddriveService _instance = CoulddriveService._internal();
  factory CoulddriveService() => _instance;
  CoulddriveService._internal();

  final HttpClient _httpClient = HttpClient.instance;

  /// 获取云盘账户列表
  Future<CoulddriveAccountPageData> getUserList({
    int page = 1,
    int size = 20,
    String? type,
    bool? isValid,
  }) async {
    final queryParams = <String, dynamic>{
      'page': page,
      'size': size,
    };

    if (type != null) {
      queryParams['type'] = type;
    }

    if (isValid != null) {
      queryParams['is_valid'] = isValid;
    }

    final response = await _httpClient.get(
      ApiConfig.coulddriveUserList,
      queryParameters: queryParams,
    );

    return CoulddriveAccountPageData.fromJson(response.data);
  }

  /// 刷新云盘账户信息
  Future<void> refreshAccount(int userId) async {
    await _httpClient.dio.put(
      '${ApiConfig.coulddriveUserRefresh}/$userId/refresh',
    );
  }

  /// 删除云盘账户
  Future<void> deleteAccount(int userId) async {
    await _httpClient.dio.delete(
      '${ApiConfig.coulddriveUserDelete}/$userId',
    );
  }

  /// 获取关系列表（好友或群组）
  Future<RelationshipPageData> getRelationshipList({
    required String cookies,
    required String driveType,
    required String relationshipType, // 'friend' 或 'group'
    int page = 1,
    int size = 100,
  }) async {
    final response = await _httpClient.dio.get(
      ApiConfig.coulddriveRelationshipList,
      queryParameters: {
        'drive_type': driveType,
        'relationship_type': relationshipType,
        'page': page,
        'size': size,
      },
      options: Options(
        headers: {
          'x-token': cookies,
        },
      ),
    );

    return RelationshipPageData.fromJson(response.data, relationshipType);
  }
}
