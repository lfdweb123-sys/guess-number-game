import 'package:flutter/material.dart';
import '../models/game.dart';
import '../services/api_service.dart';

class GameProvider extends ChangeNotifier {
  List<Game> _games = [];
  bool _isLoading = false;
  String? _error;

  List<Game> get games => _games;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> loadGames() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _games = await ApiService.getAvailableGames();
    } catch (e) {
      _error = e.toString();
      print('Load games error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> createGame(double betAmount) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await ApiService.createGame(betAmount);
      if (response.containsKey('game_id')) {
        await loadGames();
        return true;
      }
    } catch (e) {
      print('Create game error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
    return false;
  }

  Future<bool> joinGame(int gameId, int guessedNumber) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await ApiService.joinGame(gameId, guessedNumber);
      if (response.containsKey('message')) {
        await loadGames();
        return true;
      }
    } catch (e) {
      print('Join game error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
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

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
