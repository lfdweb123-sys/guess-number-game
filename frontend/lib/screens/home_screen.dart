import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/game_provider.dart';
import 'create_game_screen.dart';
import 'game_detail_screen.dart';
import 'deposit_screen.dart';
import 'withdraw_screen.dart'; // AJOUTÉ

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<GameProvider>(context, listen: false).loadGames();
      Provider.of<AuthProvider>(context, listen: false).loadBalance();
    });
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final gameProvider = Provider.of<GameProvider>(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Guess Number Game'),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            child: Row(
              children: [
                const Icon(Icons.account_balance_wallet),
                const SizedBox(width: 4),
                Text(
                  '\$${authProvider.balance.toStringAsFixed(2)}',
                  style: const TextStyle(
                      fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const SizedBox(width: 8),
                // Bouton DEPOSIT (vert)
                IconButton(
                  icon: const Icon(Icons.add_circle, color: Colors.green),
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const DepositScreen()),
                    ).then((_) => authProvider.loadBalance());
                  },
                  tooltip: 'Deposit',
                ),
                // Bouton WITHDRAW (orange)
                IconButton(
                  icon: const Icon(Icons.remove_circle, color: Colors.orange),
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const WithdrawScreen()),
                    ).then((_) => authProvider.loadBalance());
                  },
                  tooltip: 'Withdraw',
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await authProvider.logout();
              if (context.mounted) {
                Navigator.pushReplacementNamed(context, '/login');
              }
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await gameProvider.loadGames();
          await authProvider.loadBalance();
        },
        child: gameProvider.isLoading
            ? const Center(child: CircularProgressIndicator())
            : gameProvider.games.isEmpty
                ? const Center(child: Text('No games available. Create one!'))
                : ListView.builder(
                    itemCount: gameProvider.games.length,
                    itemBuilder: (context, index) {
                      final game = gameProvider.games[index];
                      return Card(
                        margin: const EdgeInsets.all(8),
                        child: ListTile(
                          leading: CircleAvatar(
                            child: Text('${game.participantsCount}'),
                          ),
                          title: Text('Game #${game.id}'),
                          subtitle: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Creator: ${game.creatorName}'),
                              Text(
                                  'Bet: \$${game.betAmount} | Pot: \$${game.totalPot}'),
                              Text('Players: ${game.participantsCount}'),
                            ],
                          ),
                          trailing: ElevatedButton(
                            onPressed: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => GameDetailScreen(game: game),
                                ),
                              ).then((_) {
                                gameProvider.loadGames();
                                authProvider.loadBalance();
                              });
                            },
                            child: const Text('Join'),
                          ),
                        ),
                      );
                    },
                  ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const CreateGameScreen()),
          ).then((_) {
            gameProvider.loadGames();
            authProvider.loadBalance();
          });
        },
        child: const Icon(Icons.add),
      ),
    );
  }
}
