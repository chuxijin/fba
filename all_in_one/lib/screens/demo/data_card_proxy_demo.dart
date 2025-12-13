import 'package:flutter/material.dart';
import '../../constants/app_colors.dart';
import '../../widgets/data_card_list.dart';

/// 带数据代理和下拉刷新的示例
class DataCardProxyDemo extends StatelessWidget {
  const DataCardProxyDemo({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('用户列表（代理模式）'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: DataCardList(
        // 使用 proxyConfig 自动处理数据加载
        proxyConfig: ProxyConfig(
          ajax: (params) => _fetchUsers(params),
          autoLoad: true,
          enablePagination: true,
          pageSize: 10,
        ),
        fields: [
          const FieldConfig(field: 'name', label: '姓名', isTitle: true),
          const FieldConfig(field: 'role', label: '角色', isSubtitle: true),
          const FieldConfig(
            field: 'phone',
            label: '手机号',
            icon: Icons.phone_outlined,
          ),
          const FieldConfig(
            field: 'email',
            label: '邮箱',
            icon: Icons.email_outlined,
          ),
          FieldConfig(
            field: 'status',
            label: '状态',
            renderType: FieldRenderType.tag,
            tagOptions: const [
              TagOption(
                value: 1,
                label: '启用',
                color: Colors.white,
                backgroundColor: Colors.green,
              ),
              TagOption(
                value: 0,
                label: '禁用',
                color: Colors.white,
                backgroundColor: Colors.red,
              ),
            ],
          ),
          const FieldConfig(
            field: 'createdAt',
            label: '创建时间',
            renderType: FieldRenderType.date,
            dateFormat: 'yyyy-MM-dd HH:mm',
            icon: Icons.access_time_outlined,
          ),
        ],
        actions: const [
          ActionConfig.view,
          ActionConfig.edit,
          ActionConfig.delete,
        ],
        showIndex: true,
        primaryKey: 'id',
        onActionClick: (params) {
          print('操作: ${params.code}, 行数据: ${params.row}');
        },
      ),
    );
  }

  /// 模拟 API 请求
  Future<ProxyResponse> _fetchUsers(ProxyParams params) async {
    // 模拟网络延迟
    await Future.delayed(const Duration(seconds: 1));

    // 模拟生成数据
    final items = List.generate(params.pageSize, (index) {
      final actualIndex = (params.page - 1) * params.pageSize + index;
      return {
        'id': actualIndex + 1,
        'name': '用户${actualIndex + 1}',
        'role': actualIndex % 3 == 0 ? '管理员' : '普通用户',
        'phone': '138000${(actualIndex + 10000).toString().padLeft(5, '0')}',
        'email': 'user${actualIndex + 1}@example.com',
        'status': actualIndex % 3 == 0 ? 0 : 1,
        'createdAt': DateTime.now()
            .subtract(Duration(days: actualIndex))
            .toIso8601String(),
      };
    });

    // 模拟总数
    const total = 50;

    return ProxyResponse(items: items, total: total);
  }
}

/// 使用真实 API 的示例
class DataCardRealApiDemo extends StatelessWidget {
  const DataCardRealApiDemo({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('用户列表（真实 API）'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: DataCardList(
        proxyConfig: ProxyConfig(
          ajax: (params) => _fetchFromApi(params),
          autoLoad: true,
          enablePagination: true,
          pageSize: 20,
        ),
        fields: const [
          FieldConfig(field: 'username', label: '用户名', isTitle: true),
          FieldConfig(field: 'nickname', label: '昵称', isSubtitle: true),
          FieldConfig(
            field: 'email',
            label: '邮箱',
            icon: Icons.email_outlined,
          ),
        ],
        actions: const [ActionConfig.edit, ActionConfig.delete],
        primaryKey: 'id',
        onActionClick: (params) {
          // 调用你的 API 进行操作
          switch (params.code) {
            case 'edit':
              // 打开编辑页面
              break;
            case 'delete':
              // 调用删除 API
              break;
          }
        },
      ),
    );
  }

  /// 真实 API 请求示例
  Future<ProxyResponse> _fetchFromApi(ProxyParams params) async {
    // 这里替换为你的真实 API 调用
    // 例如使用 Dio:
    /*
    final response = await dio.get('/api/users', queryParameters: {
      'page': params.page,
      'pageSize': params.pageSize,
      'filters': params.filters,
      'sorts': params.sorts,
    });

    return ProxyResponse(
      items: List<Map<String, dynamic>>.from(response.data['items']),
      total: response.data['total'],
    );
    */

    // 暂时返回模拟数据
    await Future.delayed(const Duration(milliseconds: 500));
    return ProxyResponse(items: [], total: 0);
  }
}
