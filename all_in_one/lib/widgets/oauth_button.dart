import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

/// OAuth 登录按钮类型
enum OAuthProvider {
  google,
  github,
  discord,
}

/// OAuth 登录按钮组件
class OAuthButton extends StatelessWidget {
  /// OAuth 提供商
  final OAuthProvider provider;

  /// 点击回调
  final VoidCallback onPressed;

  const OAuthButton({
    super.key,
    required this.provider,
    required this.onPressed,
  });

  /// 获取按钮配置
  Map<String, dynamic> get _config {
    switch (provider) {
      case OAuthProvider.google:
        return {
          'label': 'Continue with Google',
          'icon': Icons.g_mobiledata,
          'bgColor': AppColors.googleButton,
          'textColor': AppColors.textPrimary,
          'borderColor': AppColors.inputBorder,
        };
      case OAuthProvider.github:
        return {
          'label': 'Continue with GitHub',
          'icon': Icons.code,
          'bgColor': AppColors.githubButton,
          'textColor': Colors.white,
          'borderColor': AppColors.githubButton,
        };
      case OAuthProvider.discord:
        return {
          'label': 'Continue with Discord',
          'icon': Icons.discord,
          'bgColor': AppColors.discordButton,
          'textColor': Colors.white,
          'borderColor': AppColors.discordButton,
        };
    }
  }

  @override
  Widget build(BuildContext context) {
    final config = _config;

    return SizedBox(
      width: double.infinity,
      height: 48,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          backgroundColor: config['bgColor'],
          side: BorderSide(
            color: config['borderColor'],
            width: 1,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              config['icon'],
              color: config['textColor'],
              size: 20,
            ),
            const SizedBox(width: 12),
            Text(
              config['label'],
              style: TextStyle(
                color: config['textColor'],
                fontSize: 15,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
