import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/game.dart';
import '../config/api_config.dart';

class ApiService {
  static String get baseUrl => ApiConfig.baseUrl;
  static String get wsBaseUrl => ApiConfig.wsUrl;

  static Future<Map<String, String>> _getHeaders() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('auth_token');
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  static Future<Map<String, dynamic>> register(
      String username, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/register'),
        body: json.encode({'username': username, 'password': password}),
        headers: {'Content-Type': 'application/json'},
      );

      print('Register response: ${response.statusCode} - ${response.body}');
      return json.decode(response.body);
    } catch (e) {
      print('Register error: $e');
      return {'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> login(
      String username, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/login'),
        body: json.encode({'username': username, 'password': password}),
        headers: {'Content-Type': 'application/json'},
      );

      print('Login response: ${response.statusCode} - ${response.body}');
      return json.decode(response.body);
    } catch (e) {
      print('Login error: $e');
      return {'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> getUserBalance() async {
    final headers = await _getHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/api/user/balance'),
      headers: headers,
    );
    return json.decode(response.body);
  }

  static Future<Map<String, dynamic>> createGame(double betAmount) async {
    final headers = await _getHeaders();
    final response = await http.post(
      Uri.parse('$baseUrl/api/games/create'),
      headers: headers,
      body: json.encode({'bet_amount': betAmount}),
    );
    return json.decode(response.body);
  }

  static Future<Map<String, dynamic>> joinGame(
      int gameId, int guessedNumber) async {
    final headers = await _getHeaders();
    final response = await http.post(
      Uri.parse('$baseUrl/api/games/join'),
      headers: headers,
      body: json.encode({'game_id': gameId, 'guessed_number': guessedNumber}),
    );
    return json.decode(response.body);
  }

  static Future<List<Game>> getAvailableGames() async {
    final headers = await _getHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/api/games/available'),
      headers: headers,
    );
    final List<dynamic> data = json.decode(response.body);
    return data.map((json) => Game.fromJson(json)).toList();
  }

  static Future<Map<String, dynamic>> getGameDetails(int gameId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/games/$gameId/details'),
    );
    return json.decode(response.body);
  }

  static Future<Map<String, dynamic>> mobileMoneyDeposit(
      String phoneNumber, double amount) async {
    final headers = await _getHeaders();
    final response = await http.post(
      Uri.parse('$baseUrl/api/mobile-money/deposit'),
      headers: headers,
      body: json.encode({'phone_number': phoneNumber, 'amount': amount}),
    );
    return json.decode(response.body);
  }
}
