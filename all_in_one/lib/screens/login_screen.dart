import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:bot_toast/bot_toast.dart';
import '../constants/app_colors.dart';
import '../widgets/custom_text_field.dart';
import '../widgets/oauth_button.dart';
import '../widgets/captcha_widget.dart';
import '../api/auth_service.dart';
import '../models/auth_models.dart';
import 'home_screen.dart';

/// AppFlowy 风格登录页面
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final AuthService _authService = AuthService();

  bool _isLoading = false;
  String _captchaUuid = '';
  String _captchaCode = '';

  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    );

    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.2),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(
        parent: _animationController,
        curve: Curves.easeOutCubic,
      ),
    );

    _animationController.forward();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _animationController.dispose();
    super.dispose();
  }

  /// 显示 Toast 提示（支持堆叠，最新的在最上面）
  void _showToast(String message, {Color? backgroundColor, IconData? icon}) {
    BotToast.showCustomNotification(
      duration: const Duration(seconds: 3),
      toastBuilder: (cancelFunc) {
        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: backgroundColor ?? AppColors.primary,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.15),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, color: Colors.white, size: 20),
                const SizedBox(width: 10),
              ],
              Flexible(
                child: Text(
                  message,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: cancelFunc,
                child: const Icon(Icons.close, color: Colors.white70, size: 18),
              ),
            ],
          ),
        );
      },
      align: Alignment.bottomCenter,
    );
  }

  /// 用户名或邮箱验证
  String? _validateUsername(String? value) {
    if (value == null || value.isEmpty) {
      return 'Please enter your username or email';
    }
    return null;
  }

  /// 密码验证
  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Please enter your password';
    }
    if (value.length < 6) {
      return 'Password must be at least 6 characters';
    }
    return null;
  }

  /// 登录处理
  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final response = await _authService.login(
        LoginRequest(
          username: _usernameController.text.trim(),
          password: _passwordController.text,
          captcha: _captchaCode,
          uuid: _captchaUuid,
        ),
      );

      if (mounted) {
        setState(() {
          _isLoading = false;
        });

        _showToast(
          'Login successful!',
          backgroundColor: AppColors.success,
          icon: Icons.check_circle_outline,
        );

        // 跳转到主页
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (context) => const HomeScreen()),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });

        _showToast(
          'Login failed: ${e.toString()}',
          backgroundColor: AppColors.error,
          icon: Icons.error_outline,
        );
      }
    }
  }

  /// OAuth 登录处理
  void _handleOAuthLogin(OAuthProvider provider) {
    // 这里后续对接您的后端 OAuth API
    _showToast(
      '${provider.name.toUpperCase()} login (Demo)',
      icon: Icons.login,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: SlideTransition(
                position: _slideAnimation,
                child: Container(
                  constraints: const BoxConstraints(maxWidth: 400),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Logo 和标题
                        _buildHeader(),

                        const SizedBox(height: 48),

                        // OAuth 登录按钮
                        _buildOAuthButtons(),

                        const SizedBox(height: 32),

                        // 分隔线
                        _buildDivider(),

                        const SizedBox(height: 32),

                        // 用户名/邮箱输入框
                        CustomTextField(
                          labelText: 'Username / Email',
                          hintText: 'Enter your username or email',
                          prefixIcon: Icons.person_outline,
                          controller: _usernameController,
                          keyboardType: TextInputType.text,
                          validator: _validateUsername,
                        ),

                        const SizedBox(height: 20),

                        // 密码输入框
                        CustomTextField(
                          labelText: 'Password',
                          hintText: 'Enter your password',
                          prefixIcon: Icons.lock_outline,
                          controller: _passwordController,
                          isPassword: true,
                          validator: _validatePassword,
                        ),

                        const SizedBox(height: 20),

                        // 验证码
                        CaptchaWidget(
                          onCaptchaChanged: (uuid, code) {
                            _captchaUuid = uuid;
                            _captchaCode = code;
                          },
                        ),

                        const SizedBox(height: 12),

                        // 忘记密码
                        _buildForgotPassword(),

                        const SizedBox(height: 24),

                        // 登录按钮
                        _buildLoginButton(),

                        const SizedBox(height: 24),

                        // 注册链接
                        _buildSignUpLink(),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  /// 构建头部
  Widget _buildHeader() {
    return Column(
      children: [
        // AppFlowy Logo
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppColors.primary, AppColors.primaryLight],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: AppColors.primary.withValues(alpha: 0.3),
                blurRadius: 20,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: const Icon(
            Icons.developer_board,
            color: Colors.white,
            size: 32,
          ),
        ),
        const SizedBox(height: 24),
        const Text(
          'Welcome to AppFlowy',
          style: TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Sign in to your account',
          style: TextStyle(
            fontSize: 15,
            color: AppColors.textSecondary,
          ),
        ),
      ],
    );
  }

  /// 构建 OAuth 按钮
  Widget _buildOAuthButtons() {
    return Column(
      children: [
        OAuthButton(
          provider: OAuthProvider.github,
          onPressed: () => _handleOAuthLogin(OAuthProvider.github),
        ),
        const SizedBox(height: 12),
        OAuthButton(
          provider: OAuthProvider.discord,
          onPressed: () => _handleOAuthLogin(OAuthProvider.discord),
        ),
      ],
    );
  }

  /// 构建分隔线
  Widget _buildDivider() {
    return Row(
      children: [
        Expanded(
          child: Container(
            height: 1,
            color: AppColors.divider,
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            'Or continue with',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.textSecondary,
            ),
          ),
        ),
        Expanded(
          child: Container(
            height: 1,
            color: AppColors.divider,
          ),
        ),
      ],
    );
  }

  /// 构建忘记密码
  Widget _buildForgotPassword() {
    return Align(
      alignment: Alignment.centerRight,
      child: TextButton(
        onPressed: () {
          // 忘记密码逻辑
          _showToast('Forgot password feature (Demo)', icon: Icons.lock_reset);
        },
        style: TextButton.styleFrom(
          padding: EdgeInsets.zero,
          minimumSize: const Size(0, 0),
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
        child: const Text(
          'Forgot password?',
          style: TextStyle(
            fontSize: 14,
            color: AppColors.primary,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  /// 构建登录按钮
  Widget _buildLoginButton() {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: ElevatedButton(
        onPressed: _isLoading ? null : _handleLogin,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          disabledBackgroundColor: AppColors.primary.withValues(alpha: 0.6),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          elevation: 0,
        ),
        child: _isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : const Text(
                'Sign in',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
      ),
    );
  }

  /// 构建注册链接
  Widget _buildSignUpLink() {
    return Center(
      child: RichText(
        text: TextSpan(
          text: "Don't have an account? ",
          style: const TextStyle(
            fontSize: 14,
            color: AppColors.textSecondary,
          ),
          children: [
            TextSpan(
              text: 'Sign up',
              style: const TextStyle(
                color: AppColors.primary,
                fontWeight: FontWeight.w600,
              ),
              recognizer: TapGestureRecognizer()
                ..onTap = () {
                  // 注册页面逻辑
                  _showToast('Sign up feature (Demo)', icon: Icons.person_add);
                },
            ),
          ],
        ),
      ),
    );
  }
}
