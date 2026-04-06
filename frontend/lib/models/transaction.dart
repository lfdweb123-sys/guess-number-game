import 'package:flutter/material.dart';

class Transaction {
  final int id;
  final double amount;
  final String type;
  final String status;
  final DateTime createdAt;

  Transaction({
    required this.id,
    required this.amount,
    required this.type,
    required this.status,
    required this.createdAt,
  });

  factory Transaction.fromJson(Map<String, dynamic> json) {
    return Transaction(
      id: json['id'],
      amount: (json['amount'] as num).toDouble(),
      type: json['type'],
      status: json['status'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  String get typeIcon {
    switch (type) {
      case 'win':
        return '🏆';
      case 'bet':
        return '🎲';
      case 'deposit':
        return '💰';
      case 'withdrawal':
        return '💸';
      default:
        return '📝';
    }
  }

  Color get typeColor {
    switch (type) {
      case 'win':
        return Colors.green;
      case 'bet':
        return Colors.orange;
      case 'deposit':
        return Colors.blue;
      case 'withdrawal':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }
}
