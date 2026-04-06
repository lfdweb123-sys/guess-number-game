import 'package:flutter/material.dart';
import '../config/colors.dart';
import '../widgets/loading_overlay.dart';

class LeaderboardScreen extends StatefulWidget {
  const LeaderboardScreen({super.key});

  @override
  State<LeaderboardScreen> createState() => _LeaderboardScreenState();
}

class _LeaderboardScreenState extends State<LeaderboardScreen> {
  List<Map<String, dynamic>> _players = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadLeaderboard();
  }

  Future<void> _loadLeaderboard() async {
    // Simuler chargement - à connecter à l'API
    await Future.delayed(const Duration(seconds: 1));

    setState(() {
      _players = [
        {
          'rank': 1,
          'name': 'ProGamer',
          'wins': 45,
          'winRate': 68,
          'totalWon': 1250
        },
        {
          'rank': 2,
          'name': 'LuckyQueen',
          'wins': 38,
          'winRate': 62,
          'totalWon': 980
        },
        {
          'rank': 3,
          'name': 'KingPlayer',
          'wins': 32,
          'winRate': 55,
          'totalWon': 750
        },
        {
          'rank': 4,
          'name': 'FastWinner',
          'wins': 28,
          'winRate': 50,
          'totalWon': 620
        },
        {
          'rank': 5,
          'name': 'RiskTaker',
          'wins': 25,
          'winRate': 48,
          'totalWon': 510
        },
      ];
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Leaderboard'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _isLoading
          ? const LoadingOverlay()
          : Column(
              children: [
                // Top 3 podium
                Container(
                  padding: const EdgeInsets.all(20),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      _buildPodium(2, _players[1]),
                      _buildPodium(1, _players[0]),
                      _buildPodium(3, _players[2]),
                    ],
                  ),
                ),
                // List
                Expanded(
                  child: ListView.builder(
                    itemCount: _players.length,
                    itemBuilder: (context, index) {
                      final player = _players[index];
                      return Card(
                        margin: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 4),
                        child: ListTile(
                          leading: Container(
                            width: 40,
                            height: 40,
                            decoration: BoxDecoration(
                              gradient: _getRankGradient(player['rank']),
                              shape: BoxShape.circle,
                            ),
                            child: Center(
                              child: Text(
                                '${player['rank']}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.black,
                                ),
                              ),
                            ),
                          ),
                          title: Text(
                            player['name'],
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          subtitle: Text(
                              '${player['wins']} wins • ${player['winRate']}% WR'),
                          trailing: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(
                                '\$${player['totalWon']}',
                                style: const TextStyle(
                                  color: AppColors.gold,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const Text(
                                'Total Won',
                                style:
                                    TextStyle(fontSize: 10, color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
    );
  }

  Widget _buildPodium(int rank, Map<String, dynamic> player) {
    double height = rank == 1
        ? 120
        : rank == 2
            ? 90
            : 70;
    Color color = rank == 1
        ? AppColors.gold
        : rank == 2
            ? Colors.grey
            : Colors.brown;

    return Expanded(
      child: Column(
        children: [
          Container(
            height: height,
            margin: const EdgeInsets.symmetric(horizontal: 8),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [color, color.withOpacity(0.5)],
              ),
              borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
            ),
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '${rank == 1 ? '👑' : '#'}$rank',
                    style: const TextStyle(fontSize: 24),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    player['name'],
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      color: AppColors.black,
                    ),
                  ),
                  Text(
                    '\$${player['totalWon']}',
                    style:
                        const TextStyle(fontSize: 12, color: AppColors.black),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Gradient _getRankGradient(int rank) {
    switch (rank) {
      case 1:
        return AppColors.goldGradient;
      case 2:
        return LinearGradient(
          colors: [Colors.grey.shade400, Colors.grey.shade600],
        );
      case 3:
        return LinearGradient(
          colors: [Colors.brown.shade400, Colors.brown.shade600],
        );
      default:
        return LinearGradient(
          colors: [Colors.grey.shade700, Colors.grey.shade800],
        );
    }
  }
}
