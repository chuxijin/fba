import 'package:flutter/material.dart';
import 'package:bot_toast/bot_toast.dart';
import '../../../constants/appflowy_colors.dart';
import '../../../models/sync_config_models.dart';
import '../../../services/sync_config_service.dart';
import 'sync_widgets.dart';
import 'sync_utils.dart';

/// 同步任务详情屏幕（显示任务项列表）
class SyncTaskDetailScreen extends StatefulWidget {
  final SyncTask task;

  const SyncTaskDetailScreen({super.key, required this.task});

  @override
  State<SyncTaskDetailScreen> createState() => _SyncTaskDetailScreenState();
}

class _SyncTaskDetailScreenState extends State<SyncTaskDetailScreen> {
  final SyncConfigService _syncService = SyncConfigService();
  List<SyncTaskItem> _taskItems = [];
  bool _loading = true;
  int _currentPage = 1;
  final int _pageSize = 20;
  int _total = 0;

  String? _selectedStatus;
  String? _selectedOperationType;

  @override
  void initState() {
    super.initState();
    _loadTaskItems();
  }

  Future<void> _loadTaskItems() async {
    setState(() {
      _loading = true;
    });

    try {
      final pageData = await _syncService.getSyncTaskItems(
        taskId: widget.task.id,
        page: _currentPage,
        size: _pageSize,
        status: _selectedStatus,
        operationType: _selectedOperationType,
      );

      setState(() {
        _taskItems = pageData.items;
        _total = pageData.total;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
      });
      if (mounted) {
        BotToast.showText(text: '加载任务项失败: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppFlowyColors.background,
      appBar: AppBar(
        title: Text('任务详情 #${widget.task.id}'),
        backgroundColor: AppFlowyColors.surface,
        foregroundColor: AppFlowyColors.textPrimary,
        elevation: 0,
      ),
      body: Column(
        children: [
          // 筛选区域
          Container(
            color: AppFlowyColors.surface,
            padding: EdgeInsets.all(AppFlowySpacing.md),
            child: Row(
              children: [
                // 状态筛选
                Expanded(
                  child: _buildFilterDropdown(
                    value: _selectedStatus,
                    hint: '状态',
                    items: [
                      DropdownMenuItem(value: null, child: const Text('全部')),
                      DropdownMenuItem(value: 'pending', child: const Text('等待中')),
                      DropdownMenuItem(value: 'running', child: const Text('执行中')),
                      DropdownMenuItem(value: 'completed', child: const Text('已完成')),
                      DropdownMenuItem(value: 'failed', child: const Text('失败')),
                    ],
                    onChanged: (value) {
                      setState(() {
                        _selectedStatus = value;
                        _currentPage = 1;
                      });
                      _loadTaskItems();
                    },
                  ),
                ),
                const SizedBox(width: 8),
                // 操作类型筛选
                Expanded(
                  child: _buildFilterDropdown(
                    value: _selectedOperationType,
                    hint: '操作类型',
                    items: [
                      DropdownMenuItem(value: null, child: const Text('全部')),
                      DropdownMenuItem(value: 'add', child: const Text('添加')),
                      DropdownMenuItem(value: 'delete', child: const Text('删除')),
                      DropdownMenuItem(value: 'copy', child: const Text('复制')),
                      DropdownMenuItem(value: 'move', child: const Text('移动')),
                      DropdownMenuItem(value: 'rename', child: const Text('重命名')),
                    ],
                    onChanged: (value) {
                      setState(() {
                        _selectedOperationType = value;
                        _currentPage = 1;
                      });
                      _loadTaskItems();
                    },
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),

          // 任务项列表
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _taskItems.isEmpty
                    ? const Center(child: Text('暂无任务项'))
                    : ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: _taskItems.length,
                        itemBuilder: (context, index) {
                          final item = _taskItems[index];
                          return _buildTaskItemCard(item);
                        },
                      ),
          ),

          // 分页
          if (_total > _pageSize) _buildPagination(),
        ],
      ),
    );
  }

  Widget _buildFilterDropdown({
    required String? value,
    required String hint,
    required List<DropdownMenuItem<String?>> items,
    required ValueChanged<String?> onChanged,
  }) {
    return Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: AppFlowyColors.inputFill,
        border: Border.all(color: AppFlowyColors.borderInput),
        borderRadius: BorderRadius.circular(8),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String?>(
          value: value,
          hint: Text(hint, style: const TextStyle(fontSize: 13)),
          isExpanded: true,
          icon: const Icon(Icons.arrow_drop_down, size: 20),
          items: items,
          onChanged: onChanged,
        ),
      ),
    );
  }

  Widget _buildTaskItemCard(SyncTaskItem item) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 头部：文件名和标签
            Row(
              children: [
                Expanded(
                  child: Text(
                    item.fileName,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                OperationTypeTag(type: item.type),
                const SizedBox(width: 4),
                TaskStatusTag(status: item.status),
              ],
            ),
            const SizedBox(height: 8),

            // 详细信息
            InfoRow(icon: Icons.folder_outlined, label: '源路径', value: item.srcPath),
            const SizedBox(height: 4),
            InfoRow(icon: Icons.folder_special_outlined, label: '目标路径', value: item.dstPath),
            const SizedBox(height: 4),
            InfoRow(icon: Icons.file_present, label: '文件大小', value: formatFileSize(item.fileSize)),

            if (item.errMsg != null) ...[
              const SizedBox(height: 4),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.error_outline, size: 16, color: Colors.red),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '错误: ${item.errMsg}',
                      style: TextStyle(fontSize: 12, color: Colors.red),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildPagination() {
    final totalPages = (_total / _pageSize).ceil();

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(
        color: AppFlowyColors.surface,
        border: Border(top: BorderSide(color: AppFlowyColors.divider)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          IconButton(
            icon: const Icon(Icons.chevron_left),
            onPressed: _currentPage > 1
                ? () {
                    setState(() {
                      _currentPage--;
                    });
                    _loadTaskItems();
                  }
                : null,
          ),
          Text('$_currentPage / $totalPages'),
          IconButton(
            icon: const Icon(Icons.chevron_right),
            onPressed: _currentPage < totalPages
                ? () {
                    setState(() {
                      _currentPage++;
                    });
                    _loadTaskItems();
                  }
                : null,
          ),
        ],
      ),
    );
  }
}
