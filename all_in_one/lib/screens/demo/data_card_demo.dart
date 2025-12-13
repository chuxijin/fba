import 'package:flutter/material.dart';
import 'package:bot_toast/bot_toast.dart';
import '../../constants/app_colors.dart';
import '../../widgets/data_card_list.dart';

/// 数据卡片示例页面（可用于测试和参考）
class DataCardDemo extends StatefulWidget {
  const DataCardDemo({super.key});

  @override
  State<DataCardDemo> createState() => _DataCardDemoState();
}

class _DataCardDemoState extends State<DataCardDemo> {
  // 模拟数据
  final List<Map<String, dynamic>> _mockData = [
    {
      'id': 1,
      'name': '张三',
      'phone': '13800138001',
      'email': 'zhangsan@example.com',
      'status': 1,
      'role': '管理员',
      'avatar': 'https://i.pravatar.cc/150?img=1',
      'createdAt': '2024-01-15 10:30:00',
    },
    {
      'id': 2,
      'name': '李四',
      'phone': '13800138002',
      'email': 'lisi@example.com',
      'status': 1,
      'role': '普通用户',
      'avatar': 'https://i.pravatar.cc/150?img=2',
      'createdAt': '2024-02-20 14:20:00',
    },
    {
      'id': 3,
      'name': '王五',
      'phone': '13800138003',
      'email': 'wangwu@example.com',
      'status': 0,
      'role': '普通用户',
      'avatar': 'https://i.pravatar.cc/150?img=3',
      'createdAt': '2024-03-10 09:15:00',
    },
  ];

  // 字段配置
  final List<FieldConfig> _fields = [
    const FieldConfig(
      field: 'name',
      label: '姓名',
      isTitle: true,
    ),
    const FieldConfig(
      field: 'role',
      label: '角色',
      isSubtitle: true,
    ),
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
        TagOption(value: 1, label: '启用', color: Colors.white, backgroundColor: Colors.green),
        TagOption(value: 0, label: '禁用', color: Colors.white, backgroundColor: Colors.red),
      ],
    ),
    const FieldConfig(
      field: 'createdAt',
      label: '创建时间',
      renderType: FieldRenderType.date,
      dateFormat: 'yyyy-MM-dd',
      icon: Icons.access_time_outlined,
    ),
  ];

  // 操作按钮配置
  final List<ActionConfig> _actions = const [
    ActionConfig.view,
    ActionConfig.edit,
    ActionConfig.delete,
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('用户列表'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: DataCardList(
        data: _mockData, // 直接传递数据
        fields: _fields,
        actions: _actions,
        showIndex: true,
        primaryKey: 'id',
        onCardTap: (row) {
          BotToast.showText(text: '点击了: ${row['name']}');
        },
        onActionClick: (params) {
          switch (params.code) {
            case 'view':
              BotToast.showText(text: '查看: ${params.row['name']}');
              break;
            case 'edit':
              BotToast.showText(text: '编辑: ${params.row['name']}');
              break;
            case 'delete':
              _handleDelete(params.row);
              break;
          }
        },
      ),
    );
  }

  void _handleDelete(Map<String, dynamic> row) {
    setState(() {
      _mockData.removeWhere((item) => item['id'] == row['id']);
    });
    BotToast.showText(text: '已删除: ${row['name']}');
  }
}

/// 带开关状态的示例
class DataCardWithSwitchDemo extends StatefulWidget {
  const DataCardWithSwitchDemo({super.key});

  @override
  State<DataCardWithSwitchDemo> createState() => _DataCardWithSwitchDemoState();
}

class _DataCardWithSwitchDemoState extends State<DataCardWithSwitchDemo> {
  final List<Map<String, dynamic>> _data = [
    {'id': 1, 'name': '功能A', 'description': '这是功能A的描述', 'enabled': 1},
    {'id': 2, 'name': '功能B', 'description': '这是功能B的描述', 'enabled': 0},
    {'id': 3, 'name': '功能C', 'description': '这是功能C的描述', 'enabled': 1},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('功能配置'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: DataCardList(
        data: _data,
        primaryKey: 'id',
        titleField: 'name',
        subtitleField: 'description',
        fields: [
          const FieldConfig(field: 'name', label: '名称', isTitle: true),
          const FieldConfig(field: 'description', label: '描述', isSubtitle: true),
          FieldConfig(
            field: 'enabled',
            label: '开关',
            renderType: FieldRenderType.switchBtn,
            onSwitchChange: (newValue, row) async {
              // 模拟 API 调用
              await Future.delayed(const Duration(seconds: 1));
              BotToast.showText(text: '${row['name']} ${newValue ? '已启用' : '已禁用'}');
              return true; // 返回 true 表示更新成功
            },
          ),
        ],
      ),
    );
  }
}
