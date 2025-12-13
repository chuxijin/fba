/// 云盘账户数据模型
class CoulddriveAccount {
  final int id;
  final String userId;
  final String? username;
  final String type;
  final String? avatarUrl;
  final int? quota;
  final int? used;
  final bool? isVip;
  final bool? isSuperVip;
  final String? cookies;
  final bool isValid;
  final DateTime? createdTime;
  final DateTime? updatedTime;

  CoulddriveAccount({
    required this.id,
    required this.userId,
    this.username,
    required this.type,
    this.avatarUrl,
    this.quota,
    this.used,
    this.isVip,
    this.isSuperVip,
    this.cookies,
    required this.isValid,
    this.createdTime,
    this.updatedTime,
  });

  factory CoulddriveAccount.fromJson(Map<String, dynamic> json) {
    return CoulddriveAccount(
      id: json['id'] as int,
      userId: json['user_id'] as String,
      username: json['username'] as String?,
      type: json['type'] as String,
      avatarUrl: json['avatar_url'] as String?,
      quota: json['quota'] as int?,
      used: json['used'] as int?,
      isVip: json['is_vip'] as bool?,
      isSuperVip: json['is_supervip'] as bool?,
      cookies: json['cookies'] as String?,
      isValid: (json['is_valid'] as bool?) ?? true,
      createdTime: json['created_time'] != null
          ? DateTime.parse(json['created_time'] as String)
          : null,
      updatedTime: json['updated_time'] != null
          ? DateTime.parse(json['updated_time'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'username': username,
      'type': type,
      'avatar_url': avatarUrl,
      'quota': quota,
      'used': used,
      'is_vip': isVip,
      'is_supervip': isSuperVip,
      'cookies': cookies,
      'is_valid': isValid,
      'created_time': createdTime?.toIso8601String(),
      'updated_time': updatedTime?.toIso8601String(),
    };
  }
}

/// 云盘账户分页响应
class CoulddriveAccountPageData {
  final List<CoulddriveAccount> items;
  final int total;
  final int page;
  final int size;

  CoulddriveAccountPageData({
    required this.items,
    required this.total,
    required this.page,
    required this.size,
  });

  factory CoulddriveAccountPageData.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return CoulddriveAccountPageData(
      items: (data['items'] as List)
          .map((item) => CoulddriveAccount.fromJson(item as Map<String, dynamic>))
          .toList(),
      total: data['total'] as int,
      page: data['page'] as int,
      size: data['size'] as int,
    );
  }
}

/// 好友信息
class FriendInfo {
  final int uk;
  final String uname;
  final String nickName;
  final String avatarUrl;
  final int isFriend;

  FriendInfo({
    required this.uk,
    required this.uname,
    required this.nickName,
    required this.avatarUrl,
    required this.isFriend,
  });

  factory FriendInfo.fromJson(Map<String, dynamic> json) {
    return FriendInfo(
      uk: json['uk'] as int,
      uname: json['uname'] as String,
      nickName: json['nick_name'] as String,
      avatarUrl: json['avatar_url'] as String,
      isFriend: json['is_friend'] as int,
    );
  }
}

/// 群组信息
class GroupInfo {
  final String gid;
  final String gnum;
  final String name;
  final String type;
  final String status;

  GroupInfo({
    required this.gid,
    required this.gnum,
    required this.name,
    required this.type,
    required this.status,
  });

  factory GroupInfo.fromJson(Map<String, dynamic> json) {
    return GroupInfo(
      gid: json['gid'] as String,
      gnum: json['gnum'] as String,
      name: json['name'] as String,
      type: json['type'] as String,
      status: json['status'] as String,
    );
  }
}

/// 关系列表响应（好友或群组的联合类型）
class RelationshipPageData {
  final List<dynamic> items; // FriendInfo 或 GroupInfo
  final int total;

  RelationshipPageData({
    required this.items,
    required this.total,
  });

  factory RelationshipPageData.fromJson(
    Map<String, dynamic> json,
    String relationshipType,
  ) {
    final data = json['data'] as Map<String, dynamic>;
    final itemsList = data['items'] as List;

    List<dynamic> parsedItems;
    if (relationshipType == 'friend') {
      parsedItems = itemsList
          .map((item) => FriendInfo.fromJson(item as Map<String, dynamic>))
          .toList();
    } else {
      parsedItems = itemsList
          .map((item) => GroupInfo.fromJson(item as Map<String, dynamic>))
          .toList();
    }

    return RelationshipPageData(
      items: parsedItems,
      total: data['total'] as int,
    );
  }
}
