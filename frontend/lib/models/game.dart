class Game {
  final int id;
  final int creatorId;
  final String creatorName;
  final double betAmount;
  final double totalPot;
  final String status;
  final int? winningNumber;
  final int? winnerId;
  final int participantsCount;
  final String? participants;
  final DateTime createdAt;

  Game({
    required this.id,
    required this.creatorId,
    required this.creatorName,
    required this.betAmount,
    required this.totalPot,
    required this.status,
    this.winningNumber,
    this.winnerId,
    required this.participantsCount,
    this.participants,
    required this.createdAt,
  });

  factory Game.fromJson(Map<String, dynamic> json) {
    return Game(
      id: json['id'],
      creatorId: json['creator_id'],
      creatorName: json['creator_name'] ?? 'Unknown',
      betAmount: (json['bet_amount'] as num).toDouble(),
      totalPot: (json['total_pot'] as num).toDouble(),
      status: json['status'],
      winningNumber: json['winning_number'],
      winnerId: json['winner_id'],
      participantsCount: json['participants_count'] ?? 0,
      participants: json['participants'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}
