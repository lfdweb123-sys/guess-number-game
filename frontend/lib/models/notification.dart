import 'package:flutter/material.dart';

class NotificationModel {
  final int id;
  final String title;
  final String message;
  final String type;
  final String? action;
  final Map<String, dynamic>? data;
  final bool read;
  final DateTime createdAt;

  NotificationModel({
    required this.id,
    required this.title,
    required this.message,
    required this.type,
    this.action,
    this.data,
    required this.read,
    required this.createdAt,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id'],
      title: json['title'],
      message: json['message'],
      type: json['type'],
      action: json['action'],
      data: json['data'],
      read: json['read'] ?? false,
      createdAt: DateTime.parse(json['createdAt']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'message': message,
      'type': type,
      'action': action,
      'data': data,
      'read': read,
      'createdAt': createdAt.toIso8601String(),
    };
  }

  IconData get icon {
    switch (type) {
      case 'win':
        return Icons.emoji_events;
      case 'game':
        return Icons.games;
      case 'transaction':
        return Icons.payment;
      case 'warning':
        return Icons.warning;
      case 'tournament':
        return Icons.emoji_events;
      default:
        return Icons.notifications;
    }
  }

  Color get color {
    switch (type) {
      case 'win':
        return Colors.green;
      case 'game':
        return Colors.blue;
      case 'transaction':
        return Colors.orange;
      case 'warning':
        return Colors.red;
      case 'tournament':
        return Colors.purple;
      default:
        return Colors.grey;
    }
  }

  String get timeAgo {
    final now = DateTime.now();
    final difference = now.difference(createdAt);

    if (difference.inDays > 7) {
      return '${(difference.inDays / 7).floor()}w ago';
    } else if (difference.inDays > 0) {
      return '${difference.inDays}d ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours}h ago';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes}m ago';
    } else {
      return 'Just now';
    }
  }
}
