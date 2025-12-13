import 'package:flutter/material.dart';

/// AppFlowy 风格配色方案
/// 基于现代生产力工具的设计理念：简洁、优雅、高对比度
class AppFlowyColors {
  // ========== 主色调 ==========
  /// 主品牌色 - 柔和的蓝紫色
  static const Color primary = Color(0xFF6366F1); // Indigo-500
  static const Color primaryLight = Color(0xFF818CF8); // Indigo-400
  static const Color primaryDark = Color(0xFF4F46E5); // Indigo-600
  static const Color primarySurface = Color(0xFFEEF2FF); // Indigo-50

  // ========== 强调色 ==========
  /// 成功色
  static const Color success = Color(0xFF10B981); // Emerald-500
  static const Color successLight = Color(0xFFD1FAE5); // Emerald-100

  /// 警告色
  static const Color warning = Color(0xFFF59E0B); // Amber-500
  static const Color warningLight = Color(0xFFFEF3C7); // Amber-100

  /// 错误色
  static const Color error = Color(0xFFEF4444); // Red-500
  static const Color errorLight = Color(0xFFFEE2E2); // Red-100

  /// 信息色
  static const Color info = Color(0xFF3B82F6); // Blue-500
  static const Color infoLight = Color(0xFFDBEAFE); // Blue-100

  // ========== 背景色（浅色模式）==========
  /// 主背景 - 非常浅的灰色
  static const Color background = Color(0xFFFAFAFA); // Gray-50

  /// 卡片/容器背景 - 纯白
  static const Color surface = Color(0xFFFFFFFF);

  /// 侧边栏背景 - 浅灰
  static const Color sidebarBackground = Color(0xFFF7F7F7);

  /// 悬停背景 - 极浅灰
  static const Color hoverBackground = Color(0xFFF5F5F5); // Gray-100

  /// 选中背景 - 淡蓝色
  static const Color selectedBackground = Color(0xFFEEF2FF); // Indigo-50

  /// 输入框填充色
  static const Color inputFill = Color(0xFFF9FAFB); // Gray-50

  // ========== 文本颜色 ==========
  /// 主文本 - 深灰色（不用纯黑）
  static const Color textPrimary = Color(0xFF1F2937); // Gray-800

  /// 次要文本 - 中灰色
  static const Color textSecondary = Color(0xFF6B7280); // Gray-500

  /// 三级文本 - 浅灰色
  static const Color textTertiary = Color(0xFF9CA3AF); // Gray-400

  /// 占位符文本
  static const Color textPlaceholder = Color(0xFFD1D5DB); // Gray-300

  /// 禁用文本
  static const Color textDisabled = Color(0xFFE5E7EB); // Gray-200

  // ========== 边框颜色 ==========
  /// 默认边框
  static const Color border = Color(0xFFE5E7EB); // Gray-200

  /// 输入框边框
  static const Color borderInput = Color(0xFFD1D5DB); // Gray-300

  /// 聚焦边框
  static const Color borderFocus = Color(0xFF6366F1); // Indigo-500

  /// 分割线
  static const Color divider = Color(0xFFF3F4F6); // Gray-100

  // ========== 深色模式（可选）==========
  /// 深色背景
  static const Color darkBackground = Color(0xFF111827); // Gray-900

  /// 深色表面
  static const Color darkSurface = Color(0xFF1F2937); // Gray-800

  /// 深色侧边栏
  static const Color darkSidebar = Color(0xFF1A1F2E);

  /// 深色文本
  static const Color darkTextPrimary = Color(0xFFF9FAFB); // Gray-50
  static const Color darkTextSecondary = Color(0xFFD1D5DB); // Gray-300

  // ========== 功能色 ==========
  /// 标签背景色组
  static const List<Color> tagColors = [
    Color(0xFFDCFCE7), // Green-100
    Color(0xFFDBEAFE), // Blue-100
    Color(0xFFFEF3C7), // Amber-100
    Color(0xFFFCE7F3), // Pink-100
    Color(0xFFE0E7FF), // Indigo-100
    Color(0xFFE9D5FF), // Purple-100
  ];

  /// 阴影颜色
  static Color shadow = const Color(0xFF000000).withOpacity(0.04);
  static Color shadowHover = const Color(0xFF000000).withOpacity(0.08);
  static Color shadowActive = const Color(0xFF000000).withOpacity(0.12);

  // ========== 渐变色 ==========
  /// 主渐变
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  /// 背景渐变
  static const LinearGradient backgroundGradient = LinearGradient(
    colors: [Color(0xFFFAFAFA), Color(0xFFFFFFFF)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );
}

/// AppFlowy 风格的圆角尺寸
class AppFlowyRadius {
  static const double small = 6.0;
  static const double medium = 8.0;
  static const double large = 12.0;
  static const double xLarge = 16.0;
}

/// AppFlowy 风格的间距
class AppFlowySpacing {
  static const double xs = 4.0;
  static const double sm = 8.0;
  static const double md = 12.0;
  static const double lg = 16.0;
  static const double xl = 24.0;
  static const double xxl = 32.0;
}

/// AppFlowy 风格的字体大小
class AppFlowyFontSize {
  static const double xs = 11.0;
  static const double sm = 12.0;
  static const double base = 14.0;
  static const double md = 15.0;
  static const double lg = 16.0;
  static const double xl = 18.0;
  static const double xxl = 20.0;
  static const double title = 24.0;
  static const double display = 32.0;
}
