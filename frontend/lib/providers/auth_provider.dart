import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  String? _token;
  int? _userId;
  String? _username;
  double _balance = 0.0;
  bool _isLoading = false;
  String? _error;

  AuthProvider(String? initialToken) {
    _token = initialToken;
    if (initialToken != null) {
      loadBalance();
      _loadUserInfo();
    }
  }

  String? get token => _token;
  int? get userId => _userId;
  String? get username => _username;
  double get balance => _balance;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> _loadUserInfo() async {
    final prefs = await SharedPreferences.getInstance();
    _username = prefs.getString('username');
    _userId = prefs.getInt('user_id');
    notifyListeners();
  }

  Future<bool> register(String username, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await ApiService.register(username, password);
      if (response.containsKey('user_id')) {
        return true;
      } else if (response.containsKey('detail')) {
        _error = response['detail'];
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
    return false;
  }

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await ApiService.login(username, password);
      if (response.containsKey('access_token')) {
        _token = response['access_token'];
        _userId = response['user_id'];
        _username = response['username'];
        _balance = (response['balance'] as num).toDouble();

        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_token', _token!);
        await prefs.setInt('user_id', _userId!);
        await prefs.setString('username', _username!);

        return true;
      } else if (response.containsKey('detail')) {
        _error = response['detail'];
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
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
    _username = null;
    _balance = 0.0;

    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('user_id');
    await prefs.remove('username');

    notifyListeners();
  }

  void updateBalance(double newBalance) {
    _balance = newBalance;
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
