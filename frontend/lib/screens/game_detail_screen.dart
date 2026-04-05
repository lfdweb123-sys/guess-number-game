import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/game.dart';
import '../providers/game_provider.dart';
import '../providers/auth_provider.dart';
import '../widgets/number_picker.dart';

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

  @override
  void initState() {
    super.initState();
    _loadGameDetails();
  }

  Future<void> _loadGameDetails() async {
    final gameProvider = Provider.of<GameProvider>(context, listen: false);
    final details = await gameProvider.getGameDetails(widget.game.id);
    if (mounted) {
      setState(() {
        _gameDetails = details;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final gameProvider = Provider.of<GameProvider>(context);

    final canJoin = widget.game.status == 'waiting' &&
        authProvider.balance >= widget.game.betAmount;

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
              // Game Info Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      _buildInfoRow('Creator', widget.game.creatorName),
                      const Divider(),
                      _buildInfoRow('Bet Amount', '\$${widget.game.betAmount}'),
                      const Divider(),
                      _buildInfoRow('Total Pot',
                          '\$${widget.game.totalPot.toStringAsFixed(2)}'),
                      const Divider(),
                      _buildInfoRow(
                          'Players', '${widget.game.participantsCount}'),
                      const Divider(),
                      _buildInfoRow('Status', widget.game.status.toUpperCase()),
                      if (widget.game.status == 'ended' &&
                          widget.game.winningNumber != null) ...[
                        const Divider(),
                        _buildInfoRow(
                            'Winning Number', '${widget.game.winningNumber}'),
                      ],
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 20),

              // Participants List
              if (_gameDetails != null && _gameDetails!['participants'] != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Participants',
                          style: TextStyle(
                              fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 10),
                        ...(_gameDetails!['participants'] as String)
                            .split(',')
                            .map((participant) {
                          final parts = participant.split(':');
                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Text('• ${parts[0]} - Guessed: ${parts[1]}'),
                          );
                        }),
                      ],
                    ),
                  ),
                ),

              const SizedBox(height: 20),

              // Join Game Section
              if (widget.game.status == 'waiting')
                Card(
                  color: Colors.amber.shade50,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        const Text(
                          'Your Guess',
                          style: TextStyle(
                              fontSize: 20, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 20),
                        NumberPicker(
                          value: _selectedNumber,
                          onChanged: (value) {
                            setState(() {
                              _selectedNumber = value;
                            });
                          },
                        ),
                        const SizedBox(height: 20),
                        Text(
                          'Your balance: \$${authProvider.balance.toStringAsFixed(2)}',
                          style: TextStyle(
                            color: canJoin ? Colors.green : Colors.red,
                          ),
                        ),
                        const SizedBox(height: 10),
                        SizedBox(
                          width: double.infinity,
                          height: 50,
                          child: ElevatedButton(
                            onPressed: _isJoining || !canJoin
                                ? null
                                : () async {
                                    setState(() => _isJoining = true);
                                    final success = await gameProvider.joinGame(
                                      widget.game.id,
                                      _selectedNumber,
                                    );
                                    setState(() => _isJoining = false);

                                    if (success && mounted) {
                                      await authProvider.loadBalance();
                                      ScaffoldMessenger.of(context)
                                          .showSnackBar(
                                        const SnackBar(
                                            content: Text(
                                                'Joined game successfully!')),
                                      );
                                      Navigator.pop(context);
                                    } else if (mounted) {
                                      ScaffoldMessenger.of(context)
                                          .showSnackBar(
                                        const SnackBar(
                                            content:
                                                Text('Failed to join game')),
                                      );
                                    }
                                  },
                            child: _isJoining
                                ? const CircularProgressIndicator()
                                : Text(
                                    'Join Game (\$${widget.game.betAmount})'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              if (widget.game.status == 'ended' && widget.game.winnerId != null)
                Card(
                  color: Colors.green.shade50,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: const [
                        Icon(Icons.emoji_events, size: 50, color: Colors.amber),
                        SizedBox(height: 10),
                        Text(
                          'Game Ended!',
                          style: TextStyle(
                              fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
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
          Text(
            label,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
          ),
          Text(
            value,
            style: const TextStyle(fontSize: 16),
          ),
        ],
      ),
    );
  }
}
