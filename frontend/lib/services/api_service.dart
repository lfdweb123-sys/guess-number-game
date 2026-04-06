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

    // LOGS DE DEBUG
    print('========== GET HEADERS ==========');
    print('Token from SharedPreferences: ${token != null ? "EXISTS" : "NULL"}');
    if (token != null && token.length > 20) {
      print('Token preview: ${token.substring(0, 20)}...');
    }
    print('================================');

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

      final data = json.decode(response.body);

      // VÉRIFIER QUE LE TOKEN EST REÇU
      if (data.containsKey('access_token')) {
        print(
            '✅ Token received from backend: ${data['access_token'].substring(0, 20)}...');
      } else {
        print('❌ No token in response!');
      }

      return data;
    } catch (e) {
      print('Login error: $e');
      return {'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> getUserBalance() async {
    final headers = await _getHeaders();

    print('========== BALANCE REQUEST ==========');
    print('URL: $baseUrl/api/user/balance');
    print('Authorization header: ${headers['Authorization']}');
    print('====================================');

    final response = await http.get(
      Uri.parse('$baseUrl/api/user/balance'),
      headers: headers,
    );

    print('Balance response status: ${response.statusCode}');
    print('Balance response body: ${response.body}');

    return json.decode(response.body);
  }

  static Future<Map<String, dynamic>> createGame(double betAmount) async {
    final headers = await _getHeaders();
    final response = await http.post(
      Uri.parse('$baseUrl/api/games/create'),
      headers: headers,
      body: json.encode({'bet_amount': betAmount}),
    );
    print('Create game response: ${response.statusCode}');
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
    print('Join game response: ${response.statusCode}');
    return json.decode(response.body);
  }

  static Future<List<Game>> getAvailableGames() async {
    final headers = await _getHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/api/games/available'),
      headers: headers,
    );
    print('Get games response: ${response.statusCode}');
    final List<dynamic> data = json.decode(response.body);
    return data.map((json) => Game.fromJson(json)).toList();
  }

  static Future<Map<String, dynamic>> getGameDetails(int gameId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/games/$gameId/details'),
    );
    return json.decode(response.body);
  }

  static Future<Map<String, dynamic>> mobileMoneyWithdraw(
      String phoneNumber, double amount) async {
    final headers = await _getHeaders();
    final response = await http.post(
      Uri.parse('$baseUrl/api/mobile-money/withdraw'),
      headers: headers,
      body: json.encode({'phone_number': phoneNumber, 'amount': amount}),
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
