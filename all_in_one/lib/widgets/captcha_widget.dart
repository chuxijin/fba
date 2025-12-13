import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import '../api/auth_service.dart';
import '../models/auth_models.dart';

/// 验证码组件
class CaptchaWidget extends StatefulWidget {
  /// 验证码数据回调
  final void Function(String uuid, String captchaCode)? onCaptchaChanged;

  const CaptchaWidget({
    super.key,
    this.onCaptchaChanged,
  });

  @override
  State<CaptchaWidget> createState() => _CaptchaWidgetState();
}

class _CaptchaWidgetState extends State<CaptchaWidget> {
  final AuthService _authService = AuthService();
  final TextEditingController _captchaController = TextEditingController();

  String _imageBase64 = '';
  String _uuid = '';
  bool _isEnabled = false;
  int _expireSeconds = 0;
  Timer? _refreshTimer;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadCaptcha();
    _captchaController.addListener(_onCaptchaTextChanged);
  }

  @override
  void dispose() {
    _captchaController.removeListener(_onCaptchaTextChanged);
    _captchaController.dispose();
    _cancelTimer();
    super.dispose();
  }

  /// 监听验证码输入变化
  void _onCaptchaTextChanged() {
    if (widget.onCaptchaChanged != null) {
      widget.onCaptchaChanged!(_uuid, _captchaController.text);
    }
  }

  /// 加载验证码
  Future<void> _loadCaptcha() async {
    if (_isLoading) return;

    setState(() {
      _isLoading = true;
    });

    try {
      final captcha = await _authService.getCaptcha();

      if (mounted) {
        setState(() {
          _isEnabled = captcha.isEnabled;
          _expireSeconds = captcha.expireSeconds;
          _uuid = captcha.uuid;
          _imageBase64 = captcha.image;
          _isLoading = false;
          _captchaController.clear();
        });

        // 设置自动刷新（提前3秒）
        if (_isEnabled && _expireSeconds > 0) {
          _cancelTimer();
          final refreshDelay = (_expireSeconds - 3).clamp(1, _expireSeconds);
          _refreshTimer = Timer(Duration(seconds: refreshDelay), () {
            _loadCaptcha();
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  /// 取消定时器
  void _cancelTimer() {
    _refreshTimer?.cancel();
    _refreshTimer = null;
  }

  @override
  Widget build(BuildContext context) {
    if (!_isEnabled) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Captcha',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            // 验证码输入框
            Expanded(
              child: TextFormField(
                controller: _captchaController,
                style: const TextStyle(
                  fontSize: 15,
                  color: AppColors.textPrimary,
                ),
                decoration: InputDecoration(
                  hintText: 'Enter captcha',
                  hintStyle: const TextStyle(
                    color: AppColors.textTertiary,
                    fontSize: 15,
                  ),
                  filled: true,
                  fillColor: AppColors.inputFill,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 14,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: const BorderSide(
                      color: AppColors.inputBorder,
                      width: 1,
                    ),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: const BorderSide(
                      color: AppColors.inputBorder,
                      width: 1,
                    ),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: const BorderSide(
                      color: AppColors.inputFocusBorder,
                      width: 2,
                    ),
                  ),
                ),
                validator: (value) {
                  if (_isEnabled && (value == null || value.isEmpty)) {
                    return 'Please enter captcha';
                  }
                  return null;
                },
              ),
            ),
            const SizedBox(width: 12),
            // 验证码图片
            GestureDetector(
              onTap: _loadCaptcha,
              child: Container(
                width: 140,
                height: 56,
                decoration: BoxDecoration(
                  color: AppColors.inputFill,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: AppColors.inputBorder,
                    width: 1,
                  ),
                ),
                child: _isLoading
                    ? const Center(
                        child: SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: AppColors.primary,
                          ),
                        ),
                      )
                    : _imageBase64.isNotEmpty
                        ? ClipRRect(
                            borderRadius: BorderRadius.circular(7),
                            child: Padding(
                              padding: const EdgeInsets.all(2),
                              child: Image.memory(
                                base64Decode(_imageBase64),
                                fit: BoxFit.contain,
                              ),
                            ),
                          )
                        : const Center(
                            child: Icon(
                              Icons.refresh,
                              color: AppColors.textSecondary,
                            ),
                          ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
