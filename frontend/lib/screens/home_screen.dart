import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/game_provider.dart';
import '../config/colors.dart';
import '../widgets/game_card.dart';
import '../widgets/custom_button.dart';
import '../widgets/bottom_nav_bar.dart';
import '../services/websocket_service.dart';
import '../services/notification_service.dart';
import 'create_game_screen.dart';
import 'deposit_screen.dart';
import 'withdraw_screen.dart';
import 'leaderboard_screen.dart';
import 'profile_screen.dart';
import 'game_detail_screen.dart'; // AJOUTÉ - c'est ce qui manquait

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final gameProvider = Provider.of<GameProvider>(context, listen: false);
    final authProvider = Provider.of<AuthProvider>(context, listen: false);

    await gameProvider.loadGames();
    await authProvider.loadBalance();

    // Listen to WebSocket for game updates
    WebSocketService.addListener(_handleWebSocketMessage);
  }

  void _handleWebSocketMessage(Map<String, dynamic> message) {
    if (message['type'] == 'game_ended') {
      NotificationService.showSuccess(
          'Game ended! Winner received \$${message['winner_amount']}');
      _loadData();
    }
  }

  @override
  void dispose() {
    WebSocketService.removeListener(_handleWebSocketMessage);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final gameProvider = Provider.of<GameProvider>(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('GUESS NUMBER'),
        actions: [
          // Balance card
          Container(
            margin: const EdgeInsets.only(right: 16),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              gradient: AppColors.goldGradient,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              children: [
                const Icon(Icons.account_balance_wallet,
                    size: 18, color: AppColors.black),
                const SizedBox(width: 4),
                Text(
                  '\$${authProvider.balance.toStringAsFixed(2)}',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: AppColors.black,
                  ),
                ),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const DepositScreen()),
                    ).then((_) => authProvider.loadBalance());
                  },
                  child: const Icon(Icons.add_circle,
                      size: 20, color: AppColors.black),
                ),
                const SizedBox(width: 4),
                GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const WithdrawScreen()),
                    ).then((_) => authProvider.loadBalance());
                  },
                  child: const Icon(Icons.remove_circle,
                      size: 20, color: AppColors.black),
                ),
              ],
            ),
          ),
        ],
      ),
      body: _getBody(),
      floatingActionButton: _currentIndex == 0
          ? FloatingActionButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const CreateGameScreen()),
                ).then((_) => _loadData());
              },
              child: const Icon(Icons.add),
            )
          : null,
      bottomNavigationBar: BottomNavBar(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() => _currentIndex = index);
        },
      ),
    );
  }

  Widget _getBody() {
    switch (_currentIndex) {
      case 0:
        return _buildGamesTab();
      case 1:
        return const LeaderboardScreen();
      case 2:
        return const ProfileScreen();
      default:
        return _buildGamesTab();
    }
  }

  Widget _buildGamesTab() {
    final gameProvider = Provider.of<GameProvider>(context);

    return RefreshIndicator(
      onRefresh: _loadData,
      child: gameProvider.isLoading
          ? const Center(
              child: CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(AppColors.gold),
              ),
            )
          : gameProvider.games.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.games,
                        size: 80,
                        color: Colors.grey.shade600,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'No games available',
                        style: TextStyle(
                          fontSize: 18,
                          color: Colors.grey.shade400,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Create a new game to start playing',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.grey.shade500,
                        ),
                      ),
                      const SizedBox(height: 24),
                      CustomButton(
                        text: 'Create Game',
                        onPressed: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (_) => const CreateGameScreen()),
                          ).then((_) => _loadData());
                        },
                        icon: Icons.add,
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: gameProvider.games.length,
                  itemBuilder: (context, index) {
                    final game = gameProvider.games[index];
                    return GameCard(
                      game: game,
                      onJoin: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => GameDetailScreen(game: game),
                          ),
                        ).then((_) => _loadData());
                      },
                    );
                  },
                ),
    );
  }
}
