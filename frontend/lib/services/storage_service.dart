import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

class StorageService {
  static SharedPreferences? _prefs;

  static Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  // String methods
  static Future<bool> setString(String key, String value) async {
    return await _prefs?.setString(key, value) ?? false;
  }

  static String? getString(String key) {
    return _prefs?.getString(key);
  }

  // Int methods
  static Future<bool> setInt(String key, int value) async {
    return await _prefs?.setInt(key, value) ?? false;
  }

  static int? getInt(String key) {
    return _prefs?.getInt(key);
  }

  // Double methods
  static Future<bool> setDouble(String key, double value) async {
    return await _prefs?.setDouble(key, value) ?? false;
  }

  static double? getDouble(String key) {
    return _prefs?.getDouble(key);
  }

  // Bool methods
  static Future<bool> setBool(String key, bool value) async {
    return await _prefs?.setBool(key, value) ?? false;
  }

  static bool? getBool(String key) {
    return _prefs?.getBool(key);
  }

  // List<String> methods
  static Future<bool> setStringList(String key, List<String> value) async {
    return await _prefs?.setStringList(key, value) ?? false;
  }

  static List<String>? getStringList(String key) {
    return _prefs?.getStringList(key);
  }

  // Object methods (JSON)
  static Future<bool> setObject(String key, Map<String, dynamic> value) async {
    final jsonString = json.encode(value);
    return await setString(key, jsonString);
  }

  static Map<String, dynamic>? getObject(String key) {
    final jsonString = getString(key);
    if (jsonString != null) {
      return json.decode(jsonString);
    }
    return null;
  }

  // List<Object> methods (JSON)
  static Future<bool> setObjectList(
      String key, List<Map<String, dynamic>> value) async {
    final jsonString = json.encode(value);
    return await setString(key, jsonString);
  }

  static List<Map<String, dynamic>>? getObjectList(String key) {
    final jsonString = getString(key);
    if (jsonString != null) {
      final List<dynamic> decoded = json.decode(jsonString);
      return decoded.map((e) => Map<String, dynamic>.from(e)).toList();
    }
    return null;
  }

  // Remove methods
  static Future<bool> remove(String key) async {
    return await _prefs?.remove(key) ?? false;
  }

  // Clear all
  static Future<bool> clear() async {
    return await _prefs?.clear() ?? false;
  }

  // Check if key exists
  static bool containsKey(String key) {
    return _prefs?.containsKey(key) ?? false;
  }

  // Get all keys
  static Set<String> getKeys() {
    return _prefs?.getKeys() ?? {};
  }

  // Auth specific methods
  static Future<void> saveAuthToken(String token) async {
    await setString('auth_token', token);
  }

  static String? getAuthToken() {
    return getString('auth_token');
  }

  static Future<void> saveUserInfo({
    required int userId,
    required String username,
    required double balance,
  }) async {
    await setInt('user_id', userId);
    await setString('username', username);
    await setDouble('balance', balance);
  }

  static Map<String, dynamic>? getUserInfo() {
    final userId = getInt('user_id');
    final username = getString('username');
    final balance = getDouble('balance');

    if (userId != null && username != null && balance != null) {
      return {
        'user_id': userId,
        'username': username,
        'balance': balance,
      };
    }
    return null;
  }

  static Future<void> clearAuth() async {
    await remove('auth_token');
    await remove('user_id');
    await remove('username');
    await remove('balance');
  }

  // Cache methods
  static Future<void> cacheGameList(List<Map<String, dynamic>> games) async {
    await setObjectList('cached_games', games);
    await setInt('cache_timestamp', DateTime.now().millisecondsSinceEpoch);
  }

  static List<Map<String, dynamic>>? getCachedGames() {
    return getObjectList('cached_games');
  }

  static bool isCacheValid() {
    final timestamp = getInt('cache_timestamp');
    if (timestamp == null) return false;

    final cacheAge = DateTime.now().millisecondsSinceEpoch - timestamp;
    const cacheDuration = 5 * 60 * 1000; // 5 minutes

    return cacheAge < cacheDuration;
  }
}
