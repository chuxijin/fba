/// 格式化文件大小
String formatFileSize(int bytes) {
  if (bytes == 0) return '0 B';
  const k = 1024;
  final sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  final i = (bytes.bitLength - 1) ~/ 10;
  return '${(bytes / (1 << (i * 10))).toStringAsFixed(2)} ${sizes[i]}';
}

/// 格式化时长
String formatDuration(int seconds) {
  if (seconds < 60) {
    return '${seconds}秒';
  } else if (seconds < 3600) {
    final minutes = seconds ~/ 60;
    final remainingSeconds = seconds % 60;
    return '$minutes分${remainingSeconds}秒';
  } else {
    final hours = seconds ~/ 3600;
    final minutes = (seconds % 3600) ~/ 60;
    return '$hours小时$minutes分钟';
  }
}

/// 获取同步方式标签
String getMethodLabel(String method) {
  switch (method) {
    case 'incremental':
      return '增量';
    case 'full':
      return '完全';
    case 'overwrite':
      return '覆盖';
    default:
      return method;
  }
}

/// 获取速度标签
String getSpeedLabel(int speed) {
  switch (speed) {
    case 0:
      return '正常';
    case 1:
      return '慢速';
    case 2:
      return '快速';
    default:
      return speed.toString();
  }
}
