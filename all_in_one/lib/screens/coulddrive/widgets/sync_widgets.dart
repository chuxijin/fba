import 'package:flutter/material.dart';
import '../../../constants/appflowy_colors.dart';

/// 构建类型标签
class TypeTag extends StatelessWidget {
  final String type;

  const TypeTag({super.key, required this.type});

  @override
  Widget build(BuildContext context) {
    Color color;
    String label;

    switch (type) {
      case 'baidu_drive':
        color = Colors.blue;
        label = '百度';
        break;
      case 'quark_drive':
        color = Colors.orange;
        label = '夸克';
        break;
      case 'alist':
        color = Colors.green;
        label = 'Alist';
        break;
      default:
        color = Colors.grey;
        label = type;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w500)),
    );
  }
}

/// 构建执行状态
class ExecutionStatus extends StatelessWidget {
  final String status;

  const ExecutionStatus({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    Widget content;

    switch (status) {
      case 'executing':
        content = Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation<Color>(Colors.blue)),
            ),
            const SizedBox(width: 8),
            const Text('执行中', style: TextStyle(color: Colors.blue, fontSize: 13)),
          ],
        );
        break;
      case 'completed':
        content = const Text('已完成', style: TextStyle(color: Colors.green, fontSize: 13));
        break;
      default:
        content = const Text('空闲', style: TextStyle(color: Colors.grey, fontSize: 13));
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: status == 'executing'
            ? Colors.blue.withValues(alpha: 0.1)
            : status == 'completed'
                ? Colors.green.withValues(alpha: 0.1)
                : Colors.grey.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(6),
      ),
      child: content,
    );
  }
}

/// 构建操作按钮
class ActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const ActionButton({
    super.key,
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(label, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

/// 构建信息行
class InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const InfoRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: AppFlowyColors.textSecondary),
        const SizedBox(width: 8),
        Text('$label: ', style: TextStyle(fontSize: 13, color: AppFlowyColors.textSecondary)),
        Expanded(
          child: Text(
            value,
            style: TextStyle(fontSize: 13, color: AppFlowyColors.textPrimary),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}

/// 任务状态标签
class TaskStatusTag extends StatelessWidget {
  final String status;

  const TaskStatusTag({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    Color statusColor;
    String statusText;

    switch (status) {
      case 'completed':
        statusColor = Colors.green;
        statusText = '完成';
        break;
      case 'failed':
        statusColor = Colors.red;
        statusText = '失败';
        break;
      case 'running':
        statusColor = Colors.blue;
        statusText = '运行中';
        break;
      case 'cancelled':
        statusColor = Colors.orange;
        statusText = '已取消';
        break;
      default:
        statusColor = Colors.grey;
        statusText = status;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: statusColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: statusColor.withValues(alpha: 0.3)),
      ),
      child: Text(statusText, style: TextStyle(color: statusColor, fontSize: 12, fontWeight: FontWeight.w500)),
    );
  }
}

/// 操作类型标签
class OperationTypeTag extends StatelessWidget {
  final String type;

  const OperationTypeTag({super.key, required this.type});

  @override
  Widget build(BuildContext context) {
    Color typeColor;
    String typeLabel;

    switch (type) {
      case 'add':
        typeColor = Colors.blue;
        typeLabel = '添加';
        break;
      case 'delete':
        typeColor = Colors.red;
        typeLabel = '删除';
        break;
      case 'copy':
        typeColor = Colors.green;
        typeLabel = '复制';
        break;
      case 'move':
        typeColor = Colors.purple;
        typeLabel = '移动';
        break;
      case 'rename':
        typeColor = Colors.orange;
        typeLabel = '重命名';
        break;
      default:
        typeColor = Colors.grey;
        typeLabel = type;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: typeColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: typeColor.withValues(alpha: 0.3)),
      ),
      child: Text(typeLabel, style: TextStyle(color: typeColor, fontSize: 11)),
    );
  }
}
