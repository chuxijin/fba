/// 同步配置数据模型
class SyncConfig {
  final int id;
  final bool enable;
  final String? remark;
  final String type;
  final String srcPath;
  final String? srcMeta;
  final String dstPath;
  final String? dstMeta;
  final int userId;
  final String? cron;
  final int speed;
  final String method;
  final DateTime? endTime;
  final int? excludeTemplateId;
  final int? renameTemplateId;
  final DateTime? lastSync;
  final DateTime createdTime;
  final DateTime? updatedTime;
  final int createdBy;
  final int? updatedBy;

  SyncConfig({
    required this.id,
    required this.enable,
    this.remark,
    required this.type,
    required this.srcPath,
    this.srcMeta,
    required this.dstPath,
    this.dstMeta,
    required this.userId,
    this.cron,
    required this.speed,
    required this.method,
    this.endTime,
    this.excludeTemplateId,
    this.renameTemplateId,
    this.lastSync,
    required this.createdTime,
    this.updatedTime,
    required this.createdBy,
    this.updatedBy,
  });

  factory SyncConfig.fromJson(Map<String, dynamic> json) {
    return SyncConfig(
      id: json['id'] as int,
      enable: json['enable'] as bool,
      remark: json['remark'] as String?,
      type: json['type'] as String,
      srcPath: json['src_path'] as String,
      srcMeta: json['src_meta'] as String?,
      dstPath: json['dst_path'] as String,
      dstMeta: json['dst_meta'] as String?,
      userId: json['user_id'] as int,
      cron: json['cron'] as String?,
      speed: json['speed'] as int,
      method: json['method'] as String,
      endTime: json['end_time'] != null
          ? DateTime.parse(json['end_time'] as String)
          : null,
      excludeTemplateId: json['exclude_template_id'] as int?,
      renameTemplateId: json['rename_template_id'] as int?,
      lastSync: json['last_sync'] != null
          ? DateTime.parse(json['last_sync'] as String)
          : null,
      createdTime: DateTime.parse(json['created_time'] as String),
      updatedTime: json['updated_time'] != null
          ? DateTime.parse(json['updated_time'] as String)
          : null,
      createdBy: json['created_by'] as int,
      updatedBy: json['updated_by'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'enable': enable,
      'remark': remark,
      'type': type,
      'src_path': srcPath,
      'src_meta': srcMeta,
      'dst_path': dstPath,
      'dst_meta': dstMeta,
      'user_id': userId,
      'cron': cron,
      'speed': speed,
      'method': method,
      'end_time': endTime?.toIso8601String(),
      'exclude_template_id': excludeTemplateId,
      'rename_template_id': renameTemplateId,
      'last_sync': lastSync?.toIso8601String(),
      'created_time': createdTime.toIso8601String(),
      'updated_time': updatedTime?.toIso8601String(),
      'created_by': createdBy,
      'updated_by': updatedBy,
    };
  }
}

/// 同步配置列表分页数据
class SyncConfigPageData {
  final List<SyncConfig> items;
  final int total;
  final int page;
  final int size;
  final int totalPages;

  SyncConfigPageData({
    required this.items,
    required this.total,
    required this.page,
    required this.size,
    required this.totalPages,
  });

  factory SyncConfigPageData.fromJson(Map<String, dynamic> json) {
    final itemsList = json['items'] as List<dynamic>? ?? [];
    return SyncConfigPageData(
      items: itemsList.map((item) => SyncConfig.fromJson(item as Map<String, dynamic>)).toList(),
      total: json['total'] as int? ?? 0,
      page: json['page'] as int? ?? 1,
      size: json['size'] as int? ?? 20,
      totalPages: json['total_pages'] as int? ?? 0,
    );
  }
}

/// 同步任务数据模型
class SyncTask {
  final int id;
  final int configId;
  final String status;
  final String? errMsg;
  final DateTime? startTime;
  final Map<String, dynamic>? taskNum;
  final int duraTime;
  final bool cancelRequested;
  final DateTime createdTime;
  final DateTime? updatedTime;
  final int createdBy;
  final int? updatedBy;

  SyncTask({
    required this.id,
    required this.configId,
    required this.status,
    this.errMsg,
    this.startTime,
    this.taskNum,
    required this.duraTime,
    required this.cancelRequested,
    required this.createdTime,
    this.updatedTime,
    required this.createdBy,
    this.updatedBy,
  });

  factory SyncTask.fromJson(Map<String, dynamic> json) {
    // 安全解析 task_num，可能是 Map 也可能是 null 或其他类型
    Map<String, dynamic>? taskNumMap;
    final taskNumRaw = json['task_num'];
    if (taskNumRaw != null && taskNumRaw is Map) {
      taskNumMap = Map<String, dynamic>.from(taskNumRaw);
    }

    return SyncTask(
      id: json['id'] as int,
      configId: json['config_id'] as int,
      status: json['status'] as String,
      errMsg: json['err_msg'] as String?,
      startTime: json['start_time'] != null
          ? DateTime.parse(json['start_time'] as String)
          : null,
      taskNum: taskNumMap,
      duraTime: json['dura_time'] as int,
      cancelRequested: json['cancel_requested'] as bool? ?? false,
      createdTime: DateTime.parse(json['created_time'] as String),
      updatedTime: json['updated_time'] != null
          ? DateTime.parse(json['updated_time'] as String)
          : null,
      createdBy: json['created_by'] as int,
      updatedBy: json['updated_by'] as int?,
    );
  }
}

/// 同步任务项数据模型
class SyncTaskItem {
  final int id;
  final int taskId;
  final String type;
  final String srcPath;
  final String dstPath;
  final String fileName;
  final int fileSize;
  final String status;
  final String? errMsg;
  final DateTime createdTime;
  final DateTime? updatedTime;

  SyncTaskItem({
    required this.id,
    required this.taskId,
    required this.type,
    required this.srcPath,
    required this.dstPath,
    required this.fileName,
    required this.fileSize,
    required this.status,
    this.errMsg,
    required this.createdTime,
    this.updatedTime,
  });

  factory SyncTaskItem.fromJson(Map<String, dynamic> json) {
    return SyncTaskItem(
      id: json['id'] as int,
      taskId: json['task_id'] as int,
      type: json['type'] as String,
      srcPath: json['src_path'] as String,
      dstPath: json['dst_path'] as String,
      fileName: json['file_name'] as String,
      fileSize: json['file_size'] as int,
      status: json['status'] as String,
      errMsg: json['err_msg'] as String?,
      createdTime: DateTime.parse(json['created_time'] as String),
      updatedTime: json['updated_time'] != null
          ? DateTime.parse(json['updated_time'] as String)
          : null,
    );
  }
}

/// 同步任务列表分页数据
class SyncTaskPageData {
  final List<SyncTask> items;
  final int total;
  final int page;
  final int size;
  final int totalPages;

  SyncTaskPageData({
    required this.items,
    required this.total,
    required this.page,
    required this.size,
    required this.totalPages,
  });

  factory SyncTaskPageData.fromJson(Map<String, dynamic> json) {
    final itemsList = json['items'] as List<dynamic>? ?? [];
    return SyncTaskPageData(
      items: itemsList.map((item) => SyncTask.fromJson(item as Map<String, dynamic>)).toList(),
      total: json['total'] as int? ?? 0,
      page: json['page'] as int? ?? 1,
      size: json['size'] as int? ?? 20,
      totalPages: json['total_pages'] as int? ?? 0,
    );
  }
}

/// 同步任务项列表分页数据
class SyncTaskItemPageData {
  final List<SyncTaskItem> items;
  final int total;
  final int page;
  final int size;
  final int totalPages;

  SyncTaskItemPageData({
    required this.items,
    required this.total,
    required this.page,
    required this.size,
    required this.totalPages,
  });

  factory SyncTaskItemPageData.fromJson(Map<String, dynamic> json) {
    final itemsList = json['items'] as List<dynamic>? ?? [];
    return SyncTaskItemPageData(
      items: itemsList.map((item) => SyncTaskItem.fromJson(item as Map<String, dynamic>)).toList(),
      total: json['total'] as int? ?? 0,
      page: json['page'] as int? ?? 1,
      size: json['size'] as int? ?? 20,
      totalPages: json['total_pages'] as int? ?? 0,
    );
  }
}

/// 同步执行结果
class SyncExecutionResult {
  final int? taskId;
  final String status;
  final String message;
  final Map<String, dynamic>? result;

  SyncExecutionResult({
    this.taskId,
    required this.status,
    required this.message,
    this.result,
  });

  factory SyncExecutionResult.fromJson(Map<String, dynamic> json) {
    return SyncExecutionResult(
      taskId: json['task_id'] as int?,
      status: json['status'] as String,
      message: json['message'] as String,
      result: json['result'] as Map<String, dynamic>?,
    );
  }
}
