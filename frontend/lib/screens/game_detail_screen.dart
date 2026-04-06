import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/game.dart';
import '../providers/game_provider.dart';
import '../providers/auth_provider.dart';
import '../services/websocket_service.dart';
import '../services/notification_service.dart';
import '../config/colors.dart';
import '../widgets/number_picker.dart';
import '../widgets/custom_button.dart';

class GameDetailScreen extends StatefulWidget {
  final Game game;

  const GameDetailScreen({super.key, required this.game});

  @override
  State<GameDetailScreen> createState() => _GameDetailScreenState();
}

class _GameDetailScreenState extends State<GameDetailScreen> {
  int _selectedNumber = 50;
  bool _isJoining = false;
  Map<String, dynamic>? _gameDetails;
  List<String> _participants = [];
  int _timerSeconds = 0;
  Timer? _uiTimer;
  bool _gameEnding = false;

  @override
  void initState() {
    super.initState();
    _loadGameDetails();
    _connectWebSocket();
  }

  void _connectWebSocket() {
    WebSocketService.connect(widget.game.id);
    WebSocketService.addListener(_onWebSocketMessage);
  }

  void _onWebSocketMessage(Map<String, dynamic> message) {
    print('WebSocket message: ${message['type']}');

    if (message['type'] == 'timer') {
      // Mettre à jour le timer
      setState(() {
        _timerSeconds = message['seconds'];
      });

      // Si le timer atteint 0, le jeu va se terminer
      if (_timerSeconds == 0 && !_gameEnding) {
        setState(() {
          _gameEnding = true;
        });
      }
    } else if (message['type'] == 'game_ended') {
      // Annuler le timer UI
      _uiTimer?.cancel();

      setState(() {
        _timerSeconds = 0;
        _gameEnding = false;
      });

      // Afficher la notification
      NotificationService.showSuccess(
          '🎉 Game ended! Winning number: ${message['winning_number']}');

      // Recharger les détails
      _loadGameDetails();
      Provider.of<AuthProvider>(context, listen: false).loadBalance();

      // Fermer l'écran après 3 secondes (optionnel)
      // Future.delayed(const Duration(seconds: 3), () {
      //   if (mounted) Navigator.pop(context);
      // });
    } else if (message['type'] == 'game_state') {
      setState(() {
        _gameDetails = message['data'];
        if (_gameDetails != null && _gameDetails!['participants'] != null) {
          _participants = (_gameDetails!['participants'] as String).split(',');
        }
      });
    }
  }

  Future<void> _loadGameDetails() async {
    final gameProvider = Provider.of<GameProvider>(context, listen: false);
    final details = await gameProvider.getGameDetails(widget.game.id);
    if (mounted) {
      setState(() {
        _gameDetails = details;
        if (details != null && details['participants'] != null) {
          _participants = (details['participants'] as String).split(',');
        }
      });
    }
  }

  @override
  void dispose() {
    _uiTimer?.cancel();
    WebSocketService.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final game = _gameDetails ??
        {
          'status': widget.game.status,
          'bet_amount': widget.game.betAmount,
          'total_pot': widget.game.totalPot,
          'participants_count': widget.game.participantsCount,
          'creator_name': widget.game.creatorName,
        };

    final gameStatus = game['status'] as String? ?? widget.game.status;
    final betAmount =
        (game['bet_amount'] as num?)?.toDouble() ?? widget.game.betAmount;
    final totalPot =
        (game['total_pot'] as num?)?.toDouble() ?? widget.game.totalPot;
    final participantsCount =
        game['participants_count'] as int? ?? widget.game.participantsCount;
    final creatorName =
        game['creator_name'] as String? ?? widget.game.creatorName;

    final canJoin =
        gameStatus == 'waiting' && authProvider.balance >= betAmount;

    return Scaffold(
      appBar: AppBar(
        title: Text('Game #${widget.game.id}'),
      ),
      body: RefreshIndicator(
        onRefresh: _loadGameDetails,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Timer d'affichage
              if (_timerSeconds > 0 && gameStatus == 'active')
                _buildTimerCard(),

              _buildGameInfoCard(creatorName, betAmount, totalPot,
                  participantsCount, gameStatus),
              const SizedBox(height: 20),

              if (_participants.isNotEmpty) _buildParticipantsCard(),
              const SizedBox(height: 20),

              if (gameStatus == 'waiting')
                _buildJoinSection(canJoin, authProvider, betAmount),

              if (gameStatus == 'active' && _timerSeconds == 0)
                _buildWaitingCard(),

              if (gameStatus == 'ended') _buildResultCard(game),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTimerCard() {
    return Card(
      color: AppColors.orange.withOpacity(0.2),
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Icon(Icons.timer, size: 40, color: AppColors.orange),
            const SizedBox(height: 8),
            Text(
              'Game ends in:',
              style: TextStyle(color: AppColors.orange, fontSize: 14),
            ),
            Text(
              '$_timerSeconds seconds',
              style: const TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.bold,
                color: AppColors.orange,
              ),
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: _timerSeconds / 30,
              backgroundColor: Colors.grey.shade800,
              color: AppColors.orange,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWaitingCard() {
    return Card(
      color: AppColors.gold.withOpacity(0.1),
      child: const Padding(
        padding: EdgeInsets.all(20),
        child: Column(
          children: [
            SizedBox(
              height: 30,
              width: 30,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppColors.gold,
              ),
            ),
            SizedBox(height: 12),
            Text(
              'Game in progress...',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 4),
            Text(
              'The winner will be announced soon',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGameInfoCard(String creatorName, double betAmount,
      double totalPot, int participantsCount, String status) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _buildInfoRow('Creator', creatorName),
            const Divider(),
            _buildInfoRow('Bet Amount', '\$$betAmount'),
            const Divider(),
            _buildInfoRow('Total Pot', '\$$totalPot'),
            const Divider(),
            _buildInfoRow('Players', '$participantsCount'),
            const Divider(),
            _buildInfoRow('Status', status.toUpperCase()),
          ],
        ),
      ),
    );
  }

  Widget _buildParticipantsCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('👥 Participants',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ..._participants.map((participant) {
              final parts = participant.split(':');
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  children: [
                    Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                            color: AppColors.gold, shape: BoxShape.circle)),
                    const SizedBox(width: 12),
                    Text(parts[0],
                        style: const TextStyle(fontWeight: FontWeight.w500)),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                          color: AppColors.gold.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(12)),
                      child: Text('Guessed: ${parts[1]}',
                          style: const TextStyle(fontSize: 12)),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildJoinSection(
      bool canJoin, AuthProvider authProvider, double betAmount) {
    return Card(
      color: AppColors.gold.withOpacity(0.1),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Text('🎯 Your Guess',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 20),
            NumberPicker(
                value: _selectedNumber,
                onChanged: (value) => setState(() => _selectedNumber = value)),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                  color: AppColors.black.withOpacity(0.5),
                  borderRadius: BorderRadius.circular(12)),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Your Balance:'),
                  Text('\$${authProvider.balance.toStringAsFixed(2)}',
                      style: TextStyle(
                          color: canJoin ? AppColors.green : AppColors.red,
                          fontWeight: FontWeight.bold)),
                ],
              ),
            ),
            const SizedBox(height: 20),
            CustomButton(
              text: 'Join Game',
              onPressed: (_isJoining || !canJoin)
                  ? () {}
                  : () {
                      _joinGame(betAmount);
                    },
              isLoading: _isJoining,
              icon: Icons.play_arrow,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard(Map<String, dynamic> game) {
    final winnerId = game['winner_id'] as int?;
    final isWinner = winnerId == Provider.of<AuthProvider>(context).userId;
    final winningNumber = game['winning_number'] ?? '?';
    final winnerAmount = game['winner_amount'] as double? ?? 0;

    return Card(
      color: isWinner ? AppColors.green.withOpacity(0.2) : null,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Icon(isWinner ? Icons.emoji_events : Icons.sentiment_dissatisfied,
                size: 60, color: isWinner ? AppColors.gold : Colors.grey),
            const SizedBox(height: 12),
            Text(isWinner ? 'YOU WON!' : 'Game Ended',
                style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: isWinner ? AppColors.gold : Colors.grey)),
            const SizedBox(height: 8),
            Text('Winning Number: $winningNumber',
                style: const TextStyle(fontSize: 18)),
            if (isWinner) ...[
              const SizedBox(height: 8),
              Text('You won \$$winnerAmount',
                  style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: AppColors.gold)),
            ],
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => Navigator.pop(context),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.gold,
                foregroundColor: AppColors.black,
              ),
              child: const Text('Back to Games'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w500))
        ],
      ),
    );
  }

  Future<void> _joinGame(double betAmount) async {
    setState(() => _isJoining = true);

    final gameProvider = Provider.of<GameProvider>(context, listen: false);
    final authProvider = Provider.of<AuthProvider>(context, listen: false);

    final success =
        await gameProvider.joinGame(widget.game.id, _selectedNumber);

    setState(() => _isJoining = false);

    if (success && mounted) {
      await authProvider.loadBalance();
      NotificationService.showSuccess('Joined game successfully!');
      _loadGameDetails();
    } else if (mounted) {
      NotificationService.showError('Failed to join game');
    }
  }
}
