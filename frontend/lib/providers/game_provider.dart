import 'package:flutter/material.dart';
import '../../models/game.dart';
import '../../services/api_service.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:convert';

class GameProvider extends ChangeNotifier {
  List<Game> _games = [];
  bool _isLoading = false;
  WebSocketChannel? _webSocketChannel;
  Game? _currentGame;
  String? _lastMessage;

  List<Game> get games => _games;
  bool get isLoading => _isLoading;
  Game? get currentGame => _currentGame;
  String? get lastMessage => _lastMessage;

  Future<void> loadGames() async {
    _isLoading = true;
    notifyListeners();

    try {
      _games = await ApiService.getAvailableGames();
    } catch (e) {
      print('Load games error: $e');
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> createGame(double betAmount) async {
    try {
      final response = await ApiService.createGame(betAmount);
      if (response.containsKey('game_id')) {
        await loadGames();
        return true;
      }
    } catch (e) {
      print('Create game error: $e');
    }
    return false;
  }

  Future<bool> joinGame(int gameId, int guessedNumber) async {
    try {
      final response = await ApiService.joinGame(gameId, guessedNumber);
      if (response.containsKey('message')) {
        await loadGames();
        return true;
      }
    } catch (e) {
      print('Join game error: $e');
    }
    return false;
  }

  Future<Map<String, dynamic>?> getGameDetails(int gameId) async {
    try {
      return await ApiService.getGameDetails(gameId);
    } catch (e) {
      print('Get game details error: $e');
      return null;
    }
  }

  void connectToGame(int gameId, String token) {
    final wsUrl = Uri.parse('${ApiService.wsBaseUrl}/ws/$gameId/$token');
    _webSocketChannel = WebSocketChannel.connect(wsUrl);

    _webSocketChannel!.stream.listen((message) {
      final data = json.decode(message);
      _lastMessage = message;

      if (data['type'] == 'game_ended') {
        _currentGame = null;
      }

      notifyListeners();
    });
  }

  void disconnectWebSocket() {
    _webSocketChannel?.sink.close();
    _webSocketChannel = null;
  }

  void setCurrentGame(Game? game) {
    _currentGame = game;
    notifyListeners();
  }

  @override
  void dispose() {
    disconnectWebSocket();
    super.dispose();
  }
}
