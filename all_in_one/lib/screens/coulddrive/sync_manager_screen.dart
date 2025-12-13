import 'package:flutter/material.dart';
import 'package:bot_toast/bot_toast.dart';
import '../../widgets/data_card_list.dart';
import '../../constants/appflowy_colors.dart';
import '../../models/sync_config_models.dart';
import '../../services/sync_config_service.dart';
import 'widgets/sync_widgets.dart';
import 'widgets/sync_utils.dart';
import 'widgets/sync_tasks_dialog.dart';

/// 同步管理页面
class SyncManagerScreen extends StatefulWidget {
  final Function(VoidCallback)? onSearchCallbackReady;

  const SyncManagerScreen({super.key, this.onSearchCallbackReady});

  @override
  State<SyncManagerScreen> createState() => _SyncManagerScreenState();
}

class _SyncManagerScreenState extends State<SyncManagerScreen> {
  final SyncConfigService _syncService = SyncConfigService();
  final GlobalKey _listKey = GlobalKey();

  // 搜索条件
  final TextEditingController _remarkController = TextEditingController();
  String? _selectedType;
  bool? _selectedEnable;

  // 执行状态管理
  final Map<int, String> _executingTasks = {};

  @override
  void initState() {
    super.initState();
    // 注册搜索回调
    widget.onSearchCallbackReady?.call(showSearchDialog);
  }

  @override
  void dispose() {
    _remarkController.dispose();
    super.dispose();
  }

  /// 显示搜索对话框
  void showSearchDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('搜索同步配置'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // 备注搜索
              TextField(
                controller: _remarkController,
                decoration: const InputDecoration(
                  labelText: '备注',
                  hintText: '请输入备注关键词',
                  prefixIcon: Icon(Icons.edit_note),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              // 类型筛选
              DropdownButtonFormField<String?>(
                value: _selectedType,
                decoration: const InputDecoration(
                  labelText: '网盘类型',
                  prefixIcon: Icon(Icons.cloud_outlined),
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: null, child: Text('全部')),
                  DropdownMenuItem(value: 'baidu', child: Text('百度网盘')),
                  DropdownMenuItem(value: 'quark', child: Text('夸克网盘')),
                  DropdownMenuItem(value: 'alist', child: Text('Alist')),
                ],
                onChanged: (value) {
                  setState(() {
                    _selectedType = value;
                  });
                },
              ),
              const SizedBox(height: 16),
              // 启用状态筛选
              DropdownButtonFormField<bool?>(
                value: _selectedEnable,
                decoration: const InputDecoration(
                  labelText: '状态',
                  prefixIcon: Icon(Icons.toggle_on),
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: null, child: Text('全部')),
                  DropdownMenuItem(value: true, child: Text('已启用')),
                  DropdownMenuItem(value: false, child: Text('已禁用')),
                ],
                onChanged: (value) {
                  setState(() {
                    _selectedEnable = value;
                  });
                },
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              setState(() {
                _remarkController.clear();
                _selectedType = null;
                _selectedEnable = null;
              });
              Navigator.pop(context);
              (_listKey.currentState as dynamic)?.refresh();
            },
            child: const Text('重置'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              (_listKey.currentState as dynamic)?.refresh();
            },
            child: const Text('搜索'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MediaQuery.removePadding(
      context: context,
      removeLeft: true,
      removeRight: true,
      child: DataCardList(
        key: _listKey,
        proxyConfig: ProxyConfig(
          ajax: (params) => _fetchSyncConfigs(params),
          autoLoad: true,
          enablePagination: true,
          pageSize: 20,
        ),
        fields: [
          FieldConfig(
            field: 'custom_card',
            label: '',
            renderType: FieldRenderType.custom,
            showLabel: false,
            customRender: (value, row) => _buildCustomCard(row),
          ),
        ],
        actions: [],
        showIndex: false,
        primaryKey: 'id',
        cardMargin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        cardPadding: const EdgeInsets.all(12),
        showShadow: true,
      ),
    );
  }

  /// 构建自定义卡片
  Widget _buildCustomCard(Map<String, dynamic> row) {
    final config = SyncConfig.fromJson(row);
    final executionStatus = _executingTasks[config.id] ?? 'idle';

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!, width: 1),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 头部：备注和类型标签
            Row(
              children: [
                Icon(
                  Icons.sync_rounded,
                  color: config.enable ? AppFlowyColors.primary : Colors.grey,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    config.remark ?? '未命名配置',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: config.enable ? AppFlowyColors.textPrimary : Colors.grey,
                    ),
                  ),
                ),
                TypeTag(type: config.type),
              ],
            ),
            const SizedBox(height: 12),

            // 主体内容
            InfoRow(icon: Icons.folder_outlined, label: '源路径', value: config.srcPath),
            const SizedBox(height: 8),
            InfoRow(icon: Icons.folder_special_outlined, label: '目标路径', value: config.dstPath),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(child: InfoRow(icon: Icons.sync_alt, label: '方式', value: getMethodLabel(config.method))),
                Expanded(child: InfoRow(icon: Icons.speed, label: '速度', value: getSpeedLabel(config.speed))),
              ],
            ),
            const SizedBox(height: 8),
            InfoRow(
              icon: Icons.access_time,
              label: '最后同步',
              value: config.lastSync != null
                  ? '${config.lastSync!.month}-${config.lastSync!.day} ${config.lastSync!.hour}:${config.lastSync!.minute.toString().padLeft(2, '0')}'
                  : '未同步',
            ),
            const SizedBox(height: 12),

            // 执行状态和启用开关
            Row(
              children: [
                Expanded(child: ExecutionStatus(status: executionStatus)),
                const SizedBox(width: 8),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(config.enable ? Icons.check_circle : Icons.cancel, size: 16, color: config.enable ? Colors.green : Colors.grey),
                    const SizedBox(width: 4),
                    Text(config.enable ? '启用' : '禁用', style: TextStyle(fontSize: 12, color: config.enable ? Colors.green : Colors.grey)),
                    const SizedBox(width: 4),
                    Transform.scale(
                      scale: 0.8,
                      child: Switch(
                        value: config.enable,
                        onChanged: (value) => _handleStatusChange(config, value),
                        activeColor: AppFlowyColors.primary,
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 12),

            // 底部操作按钮
            Row(
              children: [
                const Spacer(),
                if (executionStatus == 'executing')
                  ActionButton(label: '取消', icon: Icons.stop, color: Colors.red, onTap: () => _handleCancel(config))
                else
                  ActionButton(label: '执行', icon: Icons.play_arrow, color: AppFlowyColors.primary, onTap: () => _handleExecute(config)),
                const SizedBox(width: 8),
                ActionButton(label: '复制', icon: Icons.content_copy, color: Colors.blue, onTap: () => _handleCopy(config)),
                const SizedBox(width: 8),
                ActionButton(label: '记录', icon: Icons.history, color: Colors.orange, onTap: () => _handleViewLogs(config)),
                const SizedBox(width: 8),
                ActionButton(label: '删除', icon: Icons.delete, color: Colors.red, onTap: () => _handleDelete(config)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// 获取同步配置列表
  Future<ProxyResponse> _fetchSyncConfigs(ProxyParams params) async {
    try {
      final pageData = await _syncService.getSyncConfigList(
        page: params.page,
        size: params.pageSize,
        type: _selectedType,
        enable: _selectedEnable,
        remark: _remarkController.text.isEmpty ? null : _remarkController.text,
      );

      final items = pageData.items.map((config) => config.toJson()).toList();
      return ProxyResponse(items: items, total: pageData.total);
    } catch (e) {
      BotToast.showText(text: '获取同步配置列表失败: $e');
      return const ProxyResponse(items: [], total: 0);
    }
  }

  /// 处理状态切换
  Future<void> _handleStatusChange(SyncConfig config, bool newValue) async {
    try {
      await _syncService.updateSyncConfig(config.id, {'enable': newValue});
      BotToast.showText(text: newValue ? '配置已启用' : '配置已禁用');
      (_listKey.currentState as dynamic)?.refresh();
    } catch (e) {
      BotToast.showText(text: '更新状态失败: $e');
    }
  }

  /// 处理执行同步
  Future<void> _handleExecute(SyncConfig config) async {
    setState(() {
      _executingTasks[config.id] = 'executing';
    });

    BotToast.showLoading();
    try {
      final result = await _syncService.executeSyncTask(config.id);

      setState(() {
        _executingTasks[config.id] = 'completed';
      });

      if (result.result != null) {
        final stats = result.result!['stats'] as Map<String, dynamic>?;
        if (stats != null) {
          final processed = stats['files_processed'] ?? 0;
          final transferred = stats['files_transferred'] ?? 0;
          final deleted = stats['files_deleted'] ?? 0;

          String message = '同步任务执行成功';
          if (processed > 0 || transferred > 0 || deleted > 0) {
            final details = <String>[];
            if (processed > 0) details.add('处理 $processed 个文件');
            if (transferred > 0) details.add('转存 $transferred 个');
            if (deleted > 0) details.add('删除 $deleted 个');
            message += ',${details.join(',')}';
          } else {
            message += ',没有文件需要同步';
          }

          BotToast.showText(text: message);
        } else {
          BotToast.showText(text: result.message);
        }
      } else {
        BotToast.showText(text: result.message);
      }

      Future.delayed(const Duration(seconds: 3), () {
        if (mounted) {
          setState(() {
            _executingTasks.remove(config.id);
          });
          (_listKey.currentState as dynamic)?.refresh();
        }
      });
    } catch (e) {
      setState(() {
        _executingTasks.remove(config.id);
      });
      BotToast.showText(text: '执行同步任务失败: $e');
    } finally {
      BotToast.closeAllLoading();
    }
  }

  /// 处理取消同步
  Future<void> _handleCancel(SyncConfig config) async {
    BotToast.showText(text: '取消功能需要实际任务ID支持');
    setState(() {
      _executingTasks.remove(config.id);
    });
    (_listKey.currentState as dynamic)?.refresh();
  }

  /// 处理复制
  Future<void> _handleCopy(SyncConfig config) async {
    try {
      BotToast.showLoading();

      final copyData = {
        'enable': config.enable,
        'remark': '${config.remark ?? ''}_副本',
        'type': config.type,
        'src_path': config.srcPath,
        'src_meta': config.srcMeta,
        'dst_path': config.dstPath,
        'dst_meta': config.dstMeta,
        'user_id': config.userId,
        'cron': config.cron,
        'speed': config.speed,
        'method': config.method,
        'end_time': config.endTime?.toIso8601String(),
        'exclude_template_id': config.excludeTemplateId,
        'rename_template_id': config.renameTemplateId,
      };

      await _syncService.createSyncConfig(copyData);
      BotToast.showText(text: '配置复制成功');
      (_listKey.currentState as dynamic)?.refresh();
    } catch (e) {
      BotToast.showText(text: '复制配置失败: $e');
    } finally {
      BotToast.closeAllLoading();
    }
  }

  /// 处理查看日志
  Future<void> _handleViewLogs(SyncConfig config) async {
    showDialog(
      context: context,
      builder: (context) => SyncTasksDialog(configId: config.id),
    );
  }

  /// 处理删除
  Future<void> _handleDelete(SyncConfig config) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('确认删除'),
        content: Text('确定要删除配置 "${config.remark ?? config.id}" 吗？此操作不可恢复。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('删除'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        BotToast.showLoading();
        await _syncService.deleteSyncConfig(config.id);
        BotToast.showText(text: '配置删除成功');
        (_listKey.currentState as dynamic)?.refresh();
      } catch (e) {
        BotToast.showText(text: '删除配置失败: $e');
      } finally {
        BotToast.closeAllLoading();
      }
    }
  }
}
