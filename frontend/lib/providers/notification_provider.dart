import 'package:flutter/material.dart';
import '../services/storage_service.dart';

class NotificationProvider extends ChangeNotifier {
  bool _notificationsEnabled = true;
  List<Map<String, dynamic>> _notifications = [];

  NotificationProvider() {
    _loadPreferences();
  }

  bool get notificationsEnabled => _notificationsEnabled;
  List<Map<String, dynamic>> get notifications => _notifications;
  int get unreadCount => _notifications.where((n) => !n['read']).length;

  Future<void> _loadPreferences() async {
    _notificationsEnabled =
        StorageService.getBool('notifications_enabled') ?? true;
    _notifications = StorageService.getObjectList('notifications') ?? [];
    notifyListeners();
  }

  Future<void> toggleNotifications() async {
    _notificationsEnabled = !_notificationsEnabled;
    await StorageService.setBool(
        'notifications_enabled', _notificationsEnabled);
    notifyListeners();
  }

  Future<void> addNotification({
    required String title,
    required String message,
    required String type,
    String? action,
    Map<String, dynamic>? data,
  }) async {
    final notification = {
      'id': DateTime.now().millisecondsSinceEpoch,
      'title': title,
      'message': message,
      'type': type,
      'action': action,
      'data': data,
      'read': false,
      'createdAt': DateTime.now().toIso8601String(),
    };

    _notifications.insert(0, notification);

    // Keep only last 100 notifications
    if (_notifications.length > 100) {
      _notifications = _notifications.take(100).toList();
    }

    await StorageService.setObjectList('notifications', _notifications);
    notifyListeners();

    // Show system notification if enabled
    if (_notificationsEnabled) {
      // TODO: Implement push notifications
      print('Notification: $title - $message');
    }
  }

  Future<void> markAsRead(int notificationId) async {
    final index = _notifications.indexWhere((n) => n['id'] == notificationId);
    if (index != -1) {
      _notifications[index]['read'] = true;
      await StorageService.setObjectList('notifications', _notifications);
      notifyListeners();
    }
  }

  Future<void> markAllAsRead() async {
    for (var i = 0; i < _notifications.length; i++) {
      _notifications[i]['read'] = true;
    }
    await StorageService.setObjectList('notifications', _notifications);
    notifyListeners();
  }

  Future<void> clearAll() async {
    _notifications = [];
    await StorageService.remove('notifications');
    notifyListeners();
  }

  Future<void> removeNotification(int notificationId) async {
    _notifications.removeWhere((n) => n['id'] == notificationId);
    await StorageService.setObjectList('notifications', _notifications);
    notifyListeners();
  }

  // Game notifications
  Future<void> notifyGameCreated(int gameId, double betAmount) async {
    await addNotification(
      title: 'Game Created',
      message: 'Your game #$gameId with \$$betAmount bet has been created',
      type: 'game',
      action: 'view_game',
      data: {'game_id': gameId},
    );
  }

  Future<void> notifyGameJoined(int gameId, int guessedNumber) async {
    await addNotification(
      title: 'Game Joined',
      message: 'You joined game #$gameId with guess $guessedNumber',
      type: 'game',
      action: 'view_game',
      data: {'game_id': gameId},
    );
  }

  Future<void> notifyGameWon(int gameId, double amount) async {
    await addNotification(
      title: '🎉 You Won!',
      message:
          'Congratulations! You won \$${amount.toStringAsFixed(2)} from game #$gameId',
      type: 'win',
      action: 'view_game',
      data: {'game_id': gameId},
    );
  }

  // Transaction notifications
  Future<void> notifyDepositSuccess(double amount, String transactionId) async {
    await addNotification(
      title: 'Deposit Successful',
      message: '\$${amount.toStringAsFixed(2)} has been added to your balance',
      type: 'transaction',
      action: 'view_transaction',
      data: {'transaction_id': transactionId, 'amount': amount},
    );
  }

  Future<void> notifyWithdrawSuccess(
      double amount, String transactionId) async {
    await addNotification(
      title: 'Withdrawal Successful',
      message:
          '\$${amount.toStringAsFixed(2)} has been sent to your mobile money',
      type: 'transaction',
      action: 'view_transaction',
      data: {'transaction_id': transactionId, 'amount': amount},
    );
  }

  // Balance notifications
  Future<void> notifyLowBalance(double balance) async {
    if (balance < 10) {
      await addNotification(
        title: 'Low Balance',
        message:
            'Your balance is low (\$${balance.toStringAsFixed(2)}). Deposit to continue playing!',
        type: 'warning',
        action: 'deposit',
      );
    }
  }

  // Tournament notifications
  Future<void> notifyTournamentStarted(
      int tournamentId, String tournamentName) async {
    await addNotification(
      title: 'Tournament Started',
      message: '$tournamentName has started! Join now to compete!',
      type: 'tournament',
      action: 'view_tournament',
      data: {'tournament_id': tournamentId},
    );
  }
}
