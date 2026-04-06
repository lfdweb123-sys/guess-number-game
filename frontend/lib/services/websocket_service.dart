import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'dart:convert';
import '../config/api_config.dart';
import 'package:shared_preferences/shared_preferences.dart';

class WebSocketService {
  static WebSocketChannel? _channel;
  static final List<void Function(Map<String, dynamic>)> _listeners = [];
  static int _currentGameId = 0;
  static bool _isConnecting = false;

  static Future<void> connect(int gameId) async {
    if (_currentGameId == gameId && _channel != null) {
      print('WebSocket already connected to game $gameId');
      return;
    }

    if (_isConnecting) {
      print('WebSocket connection already in progress');
      return;
    }

    disconnect();
    _currentGameId = gameId;
    _isConnecting = true;

    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('auth_token');

    if (token == null) {
      print('No token available');
      _isConnecting = false;
      return;
    }

    final wsUrl = '${ApiConfig.wsUrl}/ws/$gameId/$token';
    print('Connecting to WebSocket: $wsUrl');

    try {
      _channel = IOWebSocketChannel.connect(Uri.parse(wsUrl));

      _channel!.stream.listen((message) {
        print('WebSocket message received: $message');
        final data = json.decode(message);
        for (var listener in _listeners) {
          listener(data);
        }
      }, onError: (error) {
        print('WebSocket error: $error');
        _attemptReconnect();
      }, onDone: () {
        print('WebSocket disconnected for game $gameId');
        _channel = null;
      });

      // Send ping every 10 seconds to keep connection alive
      Future.delayed(const Duration(seconds: 10), _sendPing);
    } catch (e) {
      print('WebSocket connection error: $e');
      _channel = null;
    } finally {
      _isConnecting = false;
    }
  }

  static void _sendPing() {
    if (_channel != null) {
      _channel!.sink.add('ping');
      Future.delayed(const Duration(seconds: 10), _sendPing);
    }
  }

  static void _attemptReconnect() {
    Future.delayed(const Duration(seconds: 3), () {
      if (_currentGameId != 0 && _channel == null) {
        print('Attempting to reconnect to game $_currentGameId');
        connect(_currentGameId);
      }
    });
  }

  static void addListener(void Function(Map<String, dynamic>) listener) {
    if (!_listeners.contains(listener)) {
      _listeners.add(listener);
    }
  }

  static void removeListener(void Function(Map<String, dynamic>) listener) {
    _listeners.remove(listener);
  }

  static void disconnect() {
    if (_channel != null) {
      _channel!.sink.close();
      _channel = null;
    }
    _currentGameId = 0;
  }

  static bool isConnected() {
    return _channel != null;
  }
}
