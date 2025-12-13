/// 验证码响应
class CaptchaResponse {
  final bool isEnabled;
  final int expireSeconds;
  final String uuid;
  final String image;

  CaptchaResponse({
    required this.isEnabled,
    required this.expireSeconds,
    required this.uuid,
    required this.image,
  });

  factory CaptchaResponse.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return CaptchaResponse(
      // 兼容线上环境：如果没有 is_enabled 字段，默认为 true
      isEnabled: (data['is_enabled'] as bool?) ?? true,
      // 如果没有 expire_seconds 字段，默认为 300 秒
      expireSeconds: (data['expire_seconds'] as int?) ?? 300,
      uuid: data['uuid'] as String,
      image: data['image'] as String,
    );
  }
}

/// 登录响应
class LoginResponse {
  final String accessToken;
  final String sessionUuid;

  LoginResponse({
    required this.accessToken,
    required this.sessionUuid,
  });

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return LoginResponse(
      accessToken: data['access_token'] as String,
      sessionUuid: data['session_uuid'] as String,
    );
  }
}

/// 登录请求参数
class LoginRequest {
  final String username;
  final String password;
  final String? uuid;
  final String? captcha;

  LoginRequest({
    required this.username,
    required this.password,
    this.uuid,
    this.captcha,
  });

  Map<String, dynamic> toJson() {
    return {
      'username': username,
      'password': password,
      if (uuid != null) 'uuid': uuid,
      if (captcha != null) 'captcha': captcha,
    };
  }
}

/// 用户信息
class UserInfo {
  final int id;
  final String username;
  final String nickname;
  final String? avatar;
  final String? email;
  final String? phone;
  final bool isSuperuser;
  final bool isStaff;
  final DateTime? lastLoginTime;

  UserInfo({
    required this.id,
    required this.username,
    required this.nickname,
    this.avatar,
    this.email,
    this.phone,
    required this.isSuperuser,
    required this.isStaff,
    this.lastLoginTime,
  });

  factory UserInfo.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return UserInfo(
      id: data['id'] as int,
      username: data['username'] as String,
      nickname: data['nickname'] as String,
      avatar: data['avatar'] as String?,
      email: data['email'] as String?,
      phone: data['phone'] as String?,
      isSuperuser: data['is_superuser'] as bool,
      isStaff: data['is_staff'] as bool,
      lastLoginTime: data['last_login_time'] != null
          ? DateTime.parse(data['last_login_time'] as String)
          : null,
    );
  }
}
