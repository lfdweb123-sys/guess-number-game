import 'package:flutter/material.dart';
import '../config/colors.dart';
import '../models/transaction.dart';
import '../services/api_service.dart';
import '../widgets/loading_overlay.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Transaction> _transactions = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoading = true);

    try {
      // Appel API temporairement commenté - à décommenter quand l'API sera prête
      // final response = await ApiService.getTransactionHistory();
      // if (response.containsKey('transactions')) {
      //   final List<dynamic> data = response['transactions'];
      //   setState(() {
      //     _transactions = data.map((json) => Transaction.fromJson(json)).toList();
      //   });
      // }

      // Données temporaires pour le test
      await Future.delayed(const Duration(seconds: 1));
      setState(() {
        _transactions = [
          Transaction(
            id: 1,
            amount: 100.0,
            type: 'deposit',
            status: 'completed',
            createdAt: DateTime.now().subtract(const Duration(days: 1)),
          ),
          Transaction(
            id: 2,
            amount: 10.0,
            type: 'bet',
            status: 'completed',
            createdAt: DateTime.now().subtract(const Duration(hours: 5)),
          ),
          Transaction(
            id: 3,
            amount: 15.0,
            type: 'win',
            status: 'completed',
            createdAt: DateTime.now().subtract(const Duration(hours: 2)),
          ),
        ];
      });
    } catch (e) {
      print('Error loading history: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Transaction History'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _isLoading
          ? const LoadingOverlay()
          : _transactions.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.history,
                        size: 80,
                        color: Colors.grey.shade600,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'No transactions yet',
                        style: TextStyle(
                          color: Colors.grey.shade400,
                          fontSize: 16,
                        ),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _transactions.length,
                  padding: const EdgeInsets.all(16),
                  itemBuilder: (context, index) {
                    final tx = _transactions[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: tx.typeColor.withOpacity(0.2),
                          child: Text(
                            tx.typeIcon,
                            style: const TextStyle(fontSize: 20),
                          ),
                        ),
                        title: Text(
                          tx.type.toUpperCase(),
                          style: TextStyle(
                            color: tx.typeColor,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        subtitle: Text(
                          _formatDate(tx.createdAt),
                          style: const TextStyle(fontSize: 12),
                        ),
                        trailing: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              '\$${tx.amount.toStringAsFixed(2)}',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: tx.amount > 0
                                    ? AppColors.green
                                    : AppColors.red,
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: tx.status == 'completed'
                                    ? AppColors.green.withOpacity(0.2)
                                    : AppColors.orange.withOpacity(0.2),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                tx.status,
                                style: TextStyle(
                                  fontSize: 10,
                                  color: tx.status == 'completed'
                                      ? AppColors.green
                                      : AppColors.orange,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inDays > 0) {
      return '${diff.inDays} days ago';
    } else if (diff.inHours > 0) {
      return '${diff.inHours} hours ago';
    } else if (diff.inMinutes > 0) {
      return '${diff.inMinutes} minutes ago';
    } else {
      return 'Just now';
    }
  }
}
