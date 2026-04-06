import 'package:flutter/material.dart';
import '../config/colors.dart';
import '../widgets/custom_button.dart';
import '../services/notification_service.dart';

class TournamentScreen extends StatefulWidget {
  const TournamentScreen({super.key});

  @override
  State<TournamentScreen> createState() => _TournamentScreenState();
}

class _TournamentScreenState extends State<TournamentScreen> {
  List<Map<String, dynamic>> _tournaments = [];
  bool _isLoading = true;
  int _selectedTab = 0; // 0: Active, 1: Upcoming, 2: Completed

  @override
  void initState() {
    super.initState();
    _loadTournaments();
  }

  Future<void> _loadTournaments() async {
    await Future.delayed(const Duration(seconds: 1));
    setState(() {
      _tournaments = [
        {
          'id': 1,
          'name': 'Weekly Championship',
          'prize': 500,
          'entryFee': 10,
          'participants': 48,
          'maxParticipants': 100,
          'startDate': DateTime.now(),
          'endDate': DateTime.now().add(const Duration(days: 7)),
          'status': 'active',
          'rankings': [
            {'rank': 1, 'username': 'ProGamer', 'score': 1250, 'prize': 200},
            {'rank': 2, 'username': 'LuckyQueen', 'score': 1180, 'prize': 150},
            {'rank': 3, 'username': 'KingPlayer', 'score': 1100, 'prize': 100},
          ]
        },
        {
          'id': 2,
          'name': 'Diamond Tournament',
          'prize': 1000,
          'entryFee': 25,
          'participants': 32,
          'maxParticipants': 50,
          'startDate': DateTime.now().add(const Duration(days: 3)),
          'endDate': DateTime.now().add(const Duration(days: 10)),
          'status': 'upcoming',
          'rankings': []
        },
        {
          'id': 3,
          'name': 'Gold Rush',
          'prize': 250,
          'entryFee': 5,
          'participants': 120,
          'maxParticipants': 200,
          'startDate': DateTime.now().subtract(const Duration(days: 2)),
          'endDate': DateTime.now().subtract(const Duration(days: 1)),
          'status': 'completed',
          'rankings': [
            {'rank': 1, 'username': 'FastWinner', 'score': 890, 'prize': 125},
            {'rank': 2, 'username': 'RiskTaker', 'score': 820, 'prize': 75},
            {'rank': 3, 'username': 'LuckyStar', 'score': 780, 'prize': 50},
          ]
        },
      ];
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final filteredTournaments = _tournaments.where((t) {
      if (_selectedTab == 0) return t['status'] == 'active';
      if (_selectedTab == 1) return t['status'] == 'upcoming';
      return t['status'] == 'completed';
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tournaments'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Column(
        children: [
          // Tab selector
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                _buildTab('Active', 0),
                const SizedBox(width: 12),
                _buildTab('Upcoming', 1),
                const SizedBox(width: 12),
                _buildTab('Completed', 2),
              ],
            ),
          ),

          // Content
          Expanded(
            child: _isLoading
                ? const Center(
                    child: CircularProgressIndicator(color: AppColors.gold))
                : filteredTournaments.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.emoji_events,
                                size: 80, color: Colors.grey.shade600),
                            const SizedBox(height: 16),
                            Text(
                              'No tournaments available',
                              style: TextStyle(color: Colors.grey.shade400),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: filteredTournaments.length,
                        itemBuilder: (context, index) {
                          final tournament = filteredTournaments[index];
                          return _buildTournamentCard(tournament);
                        },
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildTab(String title, int index) {
    final isSelected = _selectedTab == index;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _selectedTab = index),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            gradient: isSelected ? AppColors.goldGradient : null,
            color: isSelected ? null : Colors.grey.shade800,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            title,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: isSelected ? AppColors.black : Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTournamentCard(Map<String, dynamic> tournament) {
    final isActive = tournament['status'] == 'active';
    final isUpcoming = tournament['status'] == 'upcoming';
    final progress = tournament['participants'] / tournament['maxParticipants'];

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header with prize
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: AppColors.goldGradient,
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(16)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      tournament['name'],
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.black,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Entry: \$${tournament['entryFee']}',
                      style: const TextStyle(color: AppColors.black),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    const Text(
                      'PRIZE POOL',
                      style: TextStyle(fontSize: 10, color: AppColors.black),
                    ),
                    Text(
                      '\$${tournament['prize']}',
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppColors.black,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Progress
                if (isActive || isUpcoming) ...[
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Participants: ${tournament['participants']}/${tournament['maxParticipants']}',
                        style: const TextStyle(fontSize: 12),
                      ),
                      Text(
                        '${(progress * 100).toInt()}%',
                        style: const TextStyle(
                            fontSize: 12, color: AppColors.gold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  LinearProgressIndicator(
                    value: progress,
                    backgroundColor: Colors.grey.shade800,
                    color: AppColors.gold,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  const SizedBox(height: 16),
                ],

                // Dates
                Row(
                  children: [
                    Icon(Icons.calendar_today, size: 14, color: Colors.grey),
                    const SizedBox(width: 8),
                    Text(
                      'Start: ${_formatDate(tournament['startDate'])}',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    const SizedBox(width: 16),
                    Icon(Icons.flag, size: 14, color: Colors.grey),
                    const SizedBox(width: 8),
                    Text(
                      'End: ${_formatDate(tournament['endDate'])}',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Rankings (if completed or active)
                if (tournament['rankings'].isNotEmpty) ...[
                  const Divider(),
                  const SizedBox(height: 8),
                  const Text(
                    '🏆 Top Rankings',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  ...tournament['rankings'].take(3).map((rank) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          children: [
                            Container(
                              width: 30,
                              height: 30,
                              decoration: BoxDecoration(
                                color: _getRankColor(rank['rank']),
                                shape: BoxShape.circle,
                              ),
                              child: Center(
                                child: Text(
                                  '${rank['rank']}',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.black,
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(child: Text(rank['username'])),
                            Text(
                              '${rank['score']} pts',
                              style: const TextStyle(color: AppColors.gold),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              '\$${rank['prize']}',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                color: AppColors.green,
                              ),
                            ),
                          ],
                        ),
                      )),
                ],

                const SizedBox(height: 16),

                // Action button
                if (isActive || isUpcoming)
                  CustomButton(
                    text: isActive ? 'Join Tournament' : 'Pre-register',
                    onPressed: () {
                      NotificationService.showInfo(
                        isActive
                            ? 'Tournament joining fee: \$${tournament['entryFee']}'
                            : 'You will be notified when tournament starts',
                      );
                    },
                    icon: isActive ? Icons.emoji_events : Icons.notifications,
                  ),

                if (tournament['status'] == 'completed')
                  Center(
                    child: Text(
                      'Tournament Ended',
                      style: TextStyle(color: Colors.grey.shade500),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.day}/${date.month}/${date.year}';
  }

  Color _getRankColor(int rank) {
    switch (rank) {
      case 1:
        return AppColors.gold;
      case 2:
        return Colors.grey;
      case 3:
        return Colors.brown;
      default:
        return Colors.grey.shade600;
    }
  }
}
