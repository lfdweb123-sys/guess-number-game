import 'package:flutter/material.dart';

class AppConstants {
  // Game constants
  static const int minNumber = 1;
  static const int maxNumber = 100;
  static const double minBet = 5.0;
  static const double maxBet = 100.0;
  static const double winnerPercentage = 0.75;
  static const double commissionPercentage = 0.25;
  static const int minPlayersToStart = 2;

  // Transaction limits
  static const double minDeposit = 5.0;
  static const double maxDeposit = 10000.0;
  static const double minWithdrawal = 5.0;
  static const double maxWithdrawal = 5000.0;

  // Timeouts (in seconds)
  static const int connectionTimeout = 30;
  static const int receiveTimeout = 30;
  static const int webSocketTimeout = 30;
  static const int tokenExpiryMinutes = 1440; // 24 hours

  // Cache keys
  static const String keyAuthToken = 'auth_token';
  static const String keyUserId = 'user_id';
  static const String keyUsername = 'username';
  static const String keyThemeMode = 'theme_mode';
  static const String keyNotificationsEnabled = 'notifications_enabled';

  // Animation durations
  static const Duration animationFast = Duration(milliseconds: 200);
  static const Duration animationMedium = Duration(milliseconds: 400);
  static const Duration animationSlow = Duration(milliseconds: 600);

  // Paging
  static const int pageSize = 20;
  static const int leaderboardLimit = 50;

  // Mobile Money providers
  static const List<String> mobileMoneyProviders = ['MTN', 'Orange', 'Moov'];

  // Quick amount options
  static const List<double> quickDepositAmounts = [10, 20, 50, 100, 200];
  static const List<double> quickWithdrawAmounts = [10, 20, 50, 100];
  static const List<double> quickBetAmounts = [5, 10, 20, 50, 100];

  // Regex patterns
  static const String phoneRegex = r'^[0-9]{9,15}$';
  static const String usernameRegex = r'^[a-zA-Z0-9_]{3,20}$';
  static const String passwordRegex = r'^.{4,}$';

  // Error messages
  static const String errorNetwork =
      'Network error. Please check your connection.';
  static const String errorServer = 'Server error. Please try again later.';
  static const String errorAuth = 'Authentication failed. Please login again.';
  static const String errorInsufficientBalance = 'Insufficient balance.';
  static const String errorInvalidAmount = 'Invalid amount.';
  static const String errorInvalidPhone = 'Invalid phone number.';
  static const String errorInvalidUsername =
      'Username must be 3-20 characters (letters, numbers, underscore).';
  static const String errorInvalidPassword =
      'Password must be at least 4 characters.';
  static const String errorGameNotFound = 'Game not found.';
  static const String errorAlreadyJoined = 'You already joined this game.';

  // Success messages
  static const String successLogin = 'Welcome back!';
  static const String successRegister = 'Account created successfully!';
  static const String successDeposit = 'Deposit successful!';
  static const String successWithdraw = 'Withdrawal successful!';
  static const String successGameCreated = 'Game created successfully!';
  static const String successGameJoined = 'Joined game successfully!';
}
