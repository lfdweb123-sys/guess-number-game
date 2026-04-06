class UserStats {
  final int totalGames;
  final int wins;
  final double totalWon;
  final double totalLost;
  final double winRate;

  UserStats({
    required this.totalGames,
    required this.wins,
    required this.totalWon,
    required this.totalLost,
    required this.winRate,
  });

  factory UserStats.fromJson(Map<String, dynamic> json) {
    final totalGames = json['total_games'] ?? 0;
    final wins = json['wins'] ?? 0;
    return UserStats(
      totalGames: totalGames,
      wins: wins,
      totalWon: (json['total_won'] ?? 0).toDouble(),
      totalLost: (json['total_lost'] ?? 0).toDouble(),
      winRate: totalGames > 0 ? (wins / totalGames * 100) : 0,
    );
  }
}
