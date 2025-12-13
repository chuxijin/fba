import 'package:flutter/material.dart';
import 'package:bot_toast/bot_toast.dart';
import '../../../models/sync_config_models.dart';
import '../../../services/sync_config_service.dart';
import 'sync_widgets.dart';
import 'sync_utils.dart';
import 'sync_task_detail_screen.dart';

/// 同步任务历史对话框
class SyncTasksDialog extends StatefulWidget {
  final int configId;

  const SyncTasksDialog({super.key, required this.configId});

  @override
  State<SyncTasksDialog> createState() => _SyncTasksDialogState();
}

class _SyncTasksDialogState extends State<SyncTasksDialog> {
  final SyncConfigService _syncService = SyncConfigService();
  List<SyncTask> _tasks = [];
  bool _loading = true;
  int _currentPage = 1;
  final int _pageSize = 10;
  int _total = 0;

  @override
  void initState() {
    super.initState();
    _loadTasks();
  }

  Future<void> _loadTasks() async {
    setState(() {
      _loading = true;
    });

    try {
      final pageData = await _syncService.getSyncTasks(
        configId: widget.configId,
        page: _currentPage,
        size: _pageSize,
      );

      setState(() {
        _tasks = pageData.items;
        _total = pageData.total;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
      });
      if (mounted) {
        BotToast.showText(text: '加载任务历史失败: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: Container(
        width: 800,
        height: 600,
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('同步任务历史', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context)),
              ],
            ),
            const SizedBox(height: 16),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _tasks.isEmpty
                      ? const Center(child: Text('暂无同步记录'))
                      : ListView.builder(
                          itemCount: _tasks.length,
                          itemBuilder: (context, index) {
                            final task = _tasks[index];
                            return _buildTaskItem(task);
                          },
                        ),
            ),
            if (_total > _pageSize) _buildPagination(),
          ],
        ),
      ),
    );
  }

  Widget _buildTaskItem(SyncTask task) {
    // 解析 task_num JSON
    String taskNumText = '';
    if (task.taskNum != null && task.taskNum!.isNotEmpty) {
      final taskNumData = task.taskNum!;
      final processed = taskNumData['files_processed'] ?? 0;
      final transferred = taskNumData['files_transferred'] ?? 0;
      final deleted = taskNumData['files_deleted'] ?? 0;
      final skipped = taskNumData['files_skipped'] ?? 0;

      final parts = <String>[];
      if (processed > 0) parts.add('处理$processed个');
      if (transferred > 0) parts.add('转存$transferred个');
      if (deleted > 0) parts.add('删除$deleted个');
      if (skipped > 0) parts.add('跳过$skipped个');

      taskNumText = parts.join('，');
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: TaskStatusTag(status: task.status),
        title: Text('任务 #${task.id}'),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (task.startTime != null)
              Text('开始: ${task.startTime!.year}-${task.startTime!.month.toString().padLeft(2, '0')}-${task.startTime!.day.toString().padLeft(2, '0')} ${task.startTime!.hour.toString().padLeft(2, '0')}:${task.startTime!.minute.toString().padLeft(2, '0')}:${task.startTime!.second.toString().padLeft(2, '0')}', style: const TextStyle(fontSize: 12)),
            if (task.duraTime > 0) Text('耗时: ${formatDuration(task.duraTime)}', style: const TextStyle(fontSize: 12)),
            if (taskNumText.isNotEmpty) Text('统计: $taskNumText', style: const TextStyle(fontSize: 12)),
            if (task.errMsg != null) Text('错误: ${task.errMsg}', style: const TextStyle(fontSize: 12, color: Colors.red)),
          ],
        ),
        trailing: IconButton(
          icon: const Icon(Icons.arrow_forward_ios, size: 16),
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute(
                builder: (context) => SyncTaskDetailScreen(task: task),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildPagination() {
    final totalPages = (_total / _pageSize).ceil();

    return Padding(
      padding: const EdgeInsets.only(top: 16),
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
                    _loadTasks();
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
                    _loadTasks();
                  }
                : null,
          ),
        ],
      ),
    );
  }
}
