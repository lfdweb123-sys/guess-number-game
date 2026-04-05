import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  String? _token;
  int? _userId;
  double _balance = 0.0;
  bool _isLoading = false;

  AuthProvider(String? initialToken) {
    _token = initialToken;
    if (initialToken != null) {
      loadBalance();
    }
  }

  String? get token => _token;
  int? get userId => _userId;
  double get balance => _balance;
  bool get isLoading => _isLoading;

  Future<bool> register(String username, String password) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await ApiService.register(username, password);
      if (response.containsKey('user_id')) {
        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (e) {
      print('Registration error: $e');
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await ApiService.login(username, password);
      if (response.containsKey('access_token')) {
        _token = response['access_token'];
        _userId = response['user_id'];
        _balance = (response['balance'] as num).toDouble();

        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_token', _token!);
        await prefs.setInt('user_id', _userId!);

        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (e) {
      print('Login error: $e');
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }

  Future<void> loadBalance() async {
    if (_token == null) return;

    try {
      final response = await ApiService.getUserBalance();
      _balance = (response['balance'] as num).toDouble();
      notifyListeners();
    } catch (e) {
      print('Load balance error: $e');
    }
  }

  Future<void> logout() async {
    _token = null;
    _userId = null;
    _balance = 0.0;

    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('user_id');

    notifyListeners();
  }

  void updateBalance(double newBalance) {
    _balance = newBalance;
    notifyListeners();
  }
}
