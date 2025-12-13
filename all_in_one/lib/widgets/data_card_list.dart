import 'package:flutter/material.dart';
import '../constants/appflowy_colors.dart';

/// 数据代理配置（类似 vxe-table 的 proxyConfig）
class ProxyConfig {
  /// 查询接口
  final Future<ProxyResponse> Function(ProxyParams params) ajax;

  /// 是否自动加载
  final bool autoLoad;

  /// 是否启用分页
  final bool enablePagination;

  /// 每页大小
  final int pageSize;

  const ProxyConfig({
    required this.ajax,
    this.autoLoad = true,
    this.enablePagination = true,
    this.pageSize = 20,
  });
}

/// 代理请求参数
class ProxyParams {
  final int page;
  final int pageSize;
  final Map<String, dynamic>? filters;
  final Map<String, dynamic>? sorts;

  const ProxyParams({
    required this.page,
    required this.pageSize,
    this.filters,
    this.sorts,
  });
}

/// 代理响应数据
class ProxyResponse {
  final List<Map<String, dynamic>> items;
  final int total;

  const ProxyResponse({
    required this.items,
    required this.total,
  });
}

/// 字段渲染类型
enum FieldRenderType {
  text,      // 普通文本
  tag,       // 标签
  image,     // 图片
  switchBtn, // 开关
  date,      // 日期
  link,      // 链接
  custom,    // 自定义
}

/// 标签配置
class TagOption {
  final dynamic value;
  final String label;
  final Color? color;
  final Color? backgroundColor;

  const TagOption({
    required this.value,
    required this.label,
    this.color,
    this.backgroundColor,
  });
}

/// 字段配置
class FieldConfig {
  /// 字段 key（对应数据中的 key）
  final String field;

  /// 字段标签
  final String label;

  /// 渲染类型
  final FieldRenderType renderType;

  /// 是否在卡片标题中显示
  final bool isTitle;

  /// 是否在卡片副标题中显示
  final bool isSubtitle;

  /// 标签选项（renderType 为 tag 时使用）
  final List<TagOption>? tagOptions;

  /// 日期格式（renderType 为 date 时使用）
  final String? dateFormat;

  /// 自定义渲染器
  final Widget Function(dynamic value, Map<String, dynamic> row)? customRender;

  /// 开关变更回调
  final Future<bool> Function(bool newValue, Map<String, dynamic> row)? onSwitchChange;

  /// 链接点击回调
  final void Function(Map<String, dynamic> row)? onLinkTap;

  /// 是否显示标签
  final bool showLabel;

  /// 图标
  final IconData? icon;

  const FieldConfig({
    required this.field,
    required this.label,
    this.renderType = FieldRenderType.text,
    this.isTitle = false,
    this.isSubtitle = false,
    this.tagOptions,
    this.dateFormat,
    this.customRender,
    this.onSwitchChange,
    this.onLinkTap,
    this.showLabel = true,
    this.icon,
  });
}

/// 操作按钮配置
class ActionConfig {
  /// 操作代码
  final String code;

  /// 显示文本
  final String text;

  /// 图标
  final IconData icon;

  /// 颜色
  final Color? color;

  /// 是否显示（可根据行数据动态判断）
  final bool Function(Map<String, dynamic> row)? showWhen;

  /// 是否需要确认（如删除操作）
  final bool needConfirm;

  /// 确认提示文本
  final String? confirmText;

  const ActionConfig({
    required this.code,
    required this.text,
    required this.icon,
    this.color,
    this.showWhen,
    this.needConfirm = false,
    this.confirmText,
  });

  /// 预设：编辑按钮
  static const edit = ActionConfig(
    code: 'edit',
    text: '编辑',
    icon: Icons.edit_outlined,
    color: AppFlowyColors.primary,
  );

  /// 预设：删除按钮
  static const delete = ActionConfig(
    code: 'delete',
    text: '删除',
    icon: Icons.delete_outlined,
    color: Colors.red,
    needConfirm: true,
    confirmText: '确定要删除这条记录吗？',
  );

  /// 预设：查看按钮
  static const view = ActionConfig(
    code: 'view',
    text: '查看',
    icon: Icons.visibility_outlined,
    color: AppFlowyColors.textSecondary,
  );
}

/// 操作回调参数
class ActionCallbackParams {
  final String code;
  final Map<String, dynamic> row;

  const ActionCallbackParams({
    required this.code,
    required this.row,
  });
}

/// 数据卡片列表组件
class DataCardList extends StatefulWidget {
  /// 数据列表（如果提供了 proxyConfig，则此字段将被忽略）
  final List<Map<String, dynamic>>? data;

  /// 数据代理配置（类似 vxe-table 的 proxyConfig）
  final ProxyConfig? proxyConfig;

  /// 字段配置
  final List<FieldConfig> fields;

  /// 操作按钮配置
  final List<ActionConfig>? actions;

  /// 操作按钮点击回调
  final void Function(ActionCallbackParams params)? onActionClick;

  /// 卡片点击回调
  final void Function(Map<String, dynamic> row)? onCardTap;

  /// 是否显示索引
  final bool showIndex;

  /// 是否显示分隔线
  final bool showDivider;

  /// 卡片外边距
  final EdgeInsets? cardMargin;

  /// 卡片内边距
  final EdgeInsets? cardPadding;

  /// 是否显示卡片阴影
  final bool showShadow;

  /// 空数据提示
  final String emptyText;

  /// 主键字段（用于唯一标识）
  final String? primaryKey;

  /// 标题字段（快捷方式，会自动将该字段设为 isTitle）
  final String? titleField;

  /// 副标题字段
  final String? subtitleField;

  /// 是否启用下拉刷新
  final bool enableRefresh;

  const DataCardList({
    super.key,
    this.data,
    this.proxyConfig,
    required this.fields,
    this.actions,
    this.onActionClick,
    this.onCardTap,
    this.showIndex = false,
    this.showDivider = true,
    this.cardMargin,
    this.cardPadding,
    this.showShadow = true,
    this.emptyText = '暂无数据',
    this.primaryKey,
    this.titleField,
    this.subtitleField,
    this.enableRefresh = true,
  }) : assert(data != null || proxyConfig != null, '必须提供 data 或 proxyConfig 之一');

  @override
  State<DataCardList> createState() => _DataCardListState();
}

class _DataCardListState extends State<DataCardList> {
  final Map<String, bool> _switchLoading = {};
  final ScrollController _scrollController = ScrollController();

  // 代理模式的状态
  List<Map<String, dynamic>> _proxyData = [];
  int _currentPage = 1;
  int _total = 0;
  bool _isLoading = false;
  bool _hasMore = true;
  bool _isLoadingMore = false;

  @override
  void initState() {
    super.initState();
    if (widget.proxyConfig != null) {
      if (widget.proxyConfig!.autoLoad) {
        _loadData();
      }
      if (widget.proxyConfig!.enablePagination) {
        _scrollController.addListener(_onScroll);
      }
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  /// 滚动监听（上拉加载更多）
  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      if (!_isLoadingMore && _hasMore) {
        _loadMore();
      }
    }
  }

  /// 加载数据
  Future<void> _loadData({bool isRefresh = false}) async {
    if (_isLoading) return;

    setState(() {
      _isLoading = true;
      if (isRefresh) {
        _currentPage = 1;
        _hasMore = true;
      }
    });

    try {
      final response = await widget.proxyConfig!.ajax(ProxyParams(
        page: _currentPage,
        pageSize: widget.proxyConfig!.pageSize,
      ));

      if (mounted) {
        setState(() {
          if (isRefresh) {
            _proxyData = response.items;
          } else {
            _proxyData.addAll(response.items);
          }
          _total = response.total;
          _hasMore = _proxyData.length < _total;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
      rethrow;
    }
  }

  /// 加载更多
  Future<void> _loadMore() async {
    if (_isLoadingMore || !_hasMore) return;

    setState(() {
      _isLoadingMore = true;
      _currentPage++;
    });

    try {
      await _loadData();
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingMore = false;
        });
      }
    }
  }

  /// 下拉刷新
  Future<void> _onRefresh() async {
    await _loadData(isRefresh: true);
  }

  /// 手动刷新（公开方法，可供外部调用）
  void refresh() {
    _loadData(isRefresh: true);
  }

  /// 获取数据列表
  List<Map<String, dynamic>> get _dataList {
    if (widget.proxyConfig != null) {
      return _proxyData;
    }
    return widget.data ?? [];
  }

  @override
  Widget build(BuildContext context) {
    // 初始加载状态
    if (widget.proxyConfig != null && _isLoading && _proxyData.isEmpty) {
      return _buildLoadingWidget();
    }

    // 空数据
    if (_dataList.isEmpty && !_isLoading) {
      return _buildEmptyWidget();
    }

    final listView = ListView.separated(
      controller: _scrollController,
      padding: EdgeInsets.zero,
      itemCount: _dataList.length + (_hasMore && widget.proxyConfig != null ? 1 : 0),
      separatorBuilder: (context, index) => widget.showDivider
          ? const Divider(height: 1)
          : const SizedBox(height: 8),
      itemBuilder: (context, index) {
        if (index >= _dataList.length) {
          return _buildLoadMoreWidget();
        }
        final row = _dataList[index];
        return _buildCard(row, index);
      },
    );

    // 如果启用代理且启用刷新，包裹 RefreshIndicator
    if (widget.proxyConfig != null && widget.enableRefresh) {
      return RefreshIndicator(
        onRefresh: _onRefresh,
        color: AppFlowyColors.primary,
        child: listView,
      );
    }

    return listView;
  }

  /// 构建加载中状态
  Widget _buildLoadingWidget() {
    return const Center(
      child: CircularProgressIndicator(color: AppFlowyColors.primary),
    );
  }

  /// 构建加载更多组件
  Widget _buildLoadMoreWidget() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      alignment: Alignment.center,
      child: _isLoadingMore
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppFlowyColors.primary,
              ),
            )
          : const Text(
              '加载更多...',
              style: TextStyle(
                fontSize: 12,
                color: AppFlowyColors.textSecondary,
              ),
            ),
    );
  }

  /// 构建空数据提示
  Widget _buildEmptyWidget() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.inbox_outlined,
            size: 64,
            color: AppFlowyColors.textTertiary,
          ),
          const SizedBox(height: 16),
          Text(
            widget.emptyText,
            style: const TextStyle(
              fontSize: 14,
              color: AppFlowyColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  /// 构建卡片
  Widget _buildCard(Map<String, dynamic> row, int index) {
    final titleField = _getTitleField();
    final subtitleField = _getSubtitleField();
    final contentFields = widget.fields.where((f) =>
      !f.isTitle && !f.isSubtitle && f.field != titleField?.field && f.field != subtitleField?.field
    ).toList();

    return GestureDetector(
      onTap: widget.onCardTap != null ? () => widget.onCardTap!(row) : null,
      child: Container(
        margin: widget.cardMargin ?? const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        padding: widget.cardPadding ?? const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: widget.showShadow
              ? [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 10,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 标题行
            if (titleField != null || widget.showIndex) _buildTitleRow(row, index, titleField, subtitleField),

            // 内容字段
            if (contentFields.isNotEmpty) ...[
              const SizedBox(height: 12),
              ...contentFields.map((field) => _buildFieldRow(field, row)),
            ],

            // 操作按钮
            if (widget.actions != null && widget.actions!.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Divider(height: 1),
              const SizedBox(height: 12),
              _buildActions(row),
            ],
          ],
        ),
      ),
    );
  }

  /// 获取标题字段
  FieldConfig? _getTitleField() {
    if (widget.titleField != null) {
      return widget.fields.firstWhere(
        (f) => f.field == widget.titleField,
        orElse: () => FieldConfig(field: widget.titleField!, label: ''),
      );
    }
    try {
      return widget.fields.firstWhere((f) => f.isTitle);
    } catch (_) {
      return null;
    }
  }

  /// 获取副标题字段
  FieldConfig? _getSubtitleField() {
    if (widget.subtitleField != null) {
      return widget.fields.firstWhere(
        (f) => f.field == widget.subtitleField,
        orElse: () => FieldConfig(field: widget.subtitleField!, label: ''),
      );
    }
    try {
      return widget.fields.firstWhere((f) => f.isSubtitle);
    } catch (_) {
      return null;
    }
  }

  /// 构建标题行
  Widget _buildTitleRow(Map<String, dynamic> row, int index, FieldConfig? titleField, FieldConfig? subtitleField) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 索引
        if (widget.showIndex)
          Container(
            width: 24,
            height: 24,
            margin: const EdgeInsets.only(right: 12),
            decoration: BoxDecoration(
              color: AppFlowyColors.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Center(
              child: Text(
                '${index + 1}',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppFlowyColors.primary,
                ),
              ),
            ),
          ),

        // 标题和副标题
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (titleField != null)
                Text(
                  '${row[titleField.field] ?? ''}',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppFlowyColors.textPrimary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              if (subtitleField != null) ...[
                const SizedBox(height: 4),
                Text(
                  '${row[subtitleField.field] ?? ''}',
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppFlowyColors.textSecondary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  /// 构建字段行
  Widget _buildFieldRow(FieldConfig field, Map<String, dynamic> row) {
    final value = row[field.field];

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 图标
          if (field.icon != null) ...[
            Icon(
              field.icon,
              size: 16,
              color: AppFlowyColors.textSecondary,
            ),
            const SizedBox(width: 8),
          ],

          // 标签
          if (field.showLabel)
            SizedBox(
              width: 80,
              child: Text(
                '${field.label}：',
                style: const TextStyle(
                  fontSize: 13,
                  color: AppFlowyColors.textSecondary,
                ),
              ),
            ),

          // 值
          Expanded(
            child: _renderField(field, value, row),
          ),
        ],
      ),
    );
  }

  /// 渲染字段值
  Widget _renderField(FieldConfig field, dynamic value, Map<String, dynamic> row) {
    switch (field.renderType) {
      case FieldRenderType.text:
        return Text(
          '${value ?? '-'}',
          style: const TextStyle(
            fontSize: 13,
            color: AppFlowyColors.textPrimary,
          ),
        );

      case FieldRenderType.tag:
        return _renderTag(field, value);

      case FieldRenderType.image:
        return _renderImage(value);

      case FieldRenderType.switchBtn:
        return _renderSwitch(field, value, row);

      case FieldRenderType.date:
        return _renderDate(field, value);

      case FieldRenderType.link:
        return _renderLink(field, value, row);

      case FieldRenderType.custom:
        if (field.customRender != null) {
          return field.customRender!(value, row);
        }
        return Text('${value ?? '-'}');
    }
  }

  /// 渲染标签
  Widget _renderTag(FieldConfig field, dynamic value) {
    final tagOptions = field.tagOptions ?? [
      const TagOption(value: 1, label: '启用', color: Colors.white, backgroundColor: Colors.green),
      const TagOption(value: 0, label: '禁用', color: Colors.white, backgroundColor: Colors.red),
    ];

    final tagOption = tagOptions.firstWhere(
      (opt) => opt.value == value,
      orElse: () => TagOption(value: value, label: '$value'),
    );

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: tagOption.backgroundColor ?? AppFlowyColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        tagOption.label,
        style: TextStyle(
          fontSize: 12,
          color: tagOption.color ?? AppFlowyColors.primary,
        ),
      ),
    );
  }

  /// 渲染图片
  Widget _renderImage(dynamic value) {
    if (value == null || value.toString().isEmpty) {
      return Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: AppFlowyColors.inputFill,
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Icon(
          Icons.image_outlined,
          size: 20,
          color: AppFlowyColors.textTertiary,
        ),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(4),
      child: Image.network(
        value.toString(),
        width: 40,
        height: 40,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) => Container(
          width: 40,
          height: 40,
          color: AppFlowyColors.inputFill,
          child: const Icon(
            Icons.broken_image_outlined,
            size: 20,
            color: AppFlowyColors.textTertiary,
          ),
        ),
      ),
    );
  }

  /// 渲染开关
  Widget _renderSwitch(FieldConfig field, dynamic value, Map<String, dynamic> row) {
    final key = widget.primaryKey != null ? '${row[widget.primaryKey]}_${field.field}' : '${row.hashCode}_${field.field}';
    final isLoading = _switchLoading[key] ?? false;

    return SizedBox(
      height: 24,
      child: Switch(
        value: value == 1 || value == true,
        onChanged: isLoading
            ? null
            : (newValue) async {
                if (field.onSwitchChange != null) {
                  setState(() {
                    _switchLoading[key] = true;
                  });
                  try {
                    final success = await field.onSwitchChange!(newValue, row);
                    if (success) {
                      setState(() {
                        row[field.field] = newValue ? 1 : 0;
                      });
                    }
                  } finally {
                    setState(() {
                      _switchLoading[key] = false;
                    });
                  }
                }
              },
        activeColor: AppFlowyColors.primary,
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
    );
  }

  /// 渲染日期
  Widget _renderDate(FieldConfig field, dynamic value) {
    if (value == null) {
      return const Text('-', style: TextStyle(fontSize: 13, color: AppFlowyColors.textPrimary));
    }

    String displayValue;
    if (value is DateTime) {
      displayValue = _formatDate(value, field.dateFormat);
    } else {
      try {
        final dateTime = DateTime.parse(value.toString());
        displayValue = _formatDate(dateTime, field.dateFormat);
      } catch (_) {
        displayValue = value.toString();
      }
    }

    return Text(
      displayValue,
      style: const TextStyle(
        fontSize: 13,
        color: AppFlowyColors.textPrimary,
      ),
    );
  }

  /// 格式化日期
  String _formatDate(DateTime date, String? format) {
    format ??= 'yyyy-MM-dd HH:mm';
    return format
        .replaceAll('yyyy', date.year.toString())
        .replaceAll('MM', date.month.toString().padLeft(2, '0'))
        .replaceAll('dd', date.day.toString().padLeft(2, '0'))
        .replaceAll('HH', date.hour.toString().padLeft(2, '0'))
        .replaceAll('mm', date.minute.toString().padLeft(2, '0'))
        .replaceAll('ss', date.second.toString().padLeft(2, '0'));
  }

  /// 渲染链接
  Widget _renderLink(FieldConfig field, dynamic value, Map<String, dynamic> row) {
    return GestureDetector(
      onTap: () => field.onLinkTap?.call(row),
      child: Text(
        '${value ?? '-'}',
        style: const TextStyle(
          fontSize: 13,
          color: AppFlowyColors.primary,
          decoration: TextDecoration.underline,
        ),
      ),
    );
  }

  /// 构建操作按钮
  Widget _buildActions(Map<String, dynamic> row) {
    final visibleActions = widget.actions!.where((action) {
      if (action.showWhen != null) {
        return action.showWhen!(row);
      }
      return true;
    }).toList();

    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: visibleActions.map((action) {
        return _buildActionButton(action, row);
      }).toList(),
    );
  }

  /// 构建操作按钮
  Widget _buildActionButton(ActionConfig action, Map<String, dynamic> row) {
    return Padding(
      padding: const EdgeInsets.only(left: 16),
      child: GestureDetector(
        onTap: () {
          if (action.needConfirm) {
            _showConfirmDialog(action, row);
          } else {
            widget.onActionClick?.call(ActionCallbackParams(code: action.code, row: row));
          }
        },
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              action.icon,
              size: 16,
              color: action.color ?? AppFlowyColors.primary,
            ),
            const SizedBox(width: 4),
            Text(
              action.text,
              style: TextStyle(
                fontSize: 13,
                color: action.color ?? AppFlowyColors.primary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 显示确认对话框
  void _showConfirmDialog(ActionConfig action, Map<String, dynamic> row) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('确认'),
        content: Text(action.confirmText ?? '确定要执行此操作吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              widget.onActionClick?.call(ActionCallbackParams(code: action.code, row: row));
            },
            style: TextButton.styleFrom(foregroundColor: action.color ?? Colors.red),
            child: const Text('确定'),
          ),
        ],
      ),
    );
  }
}
