import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/game_provider.dart';
import '../providers/auth_provider.dart';
import '../widgets/number_picker.dart';

class CreateGameScreen extends StatefulWidget {
  const CreateGameScreen({super.key});

  @override
  State<CreateGameScreen> createState() => _CreateGameScreenState();
}

class _CreateGameScreenState extends State<CreateGameScreen> {
  final _formKey = GlobalKey<FormState>();
  double _betAmount = 10.0;
  bool _isCreating = false;

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final gameProvider = Provider.of<GameProvider>(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Create New Game'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Bet Amount',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: DropdownButtonFormField<double>(
                  value: _betAmount,
                  items: [5, 10, 20, 50, 100].map((amount) {
                    return DropdownMenuItem(
                      value: amount.toDouble(),
                      child: Text('\$$amount'),
                    );
                  }).toList(),
                  onChanged: (value) {
                    setState(() {
                      _betAmount = value!;
                    });
                  },
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Card(
                color: Colors.blue.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Game Rules:',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                          '• Each player guesses a number between 1-100'),
                      const Text('• Minimum 2 players required'),
                      const Text('• Winner gets 75% of total pot'),
                      const Text('• Site takes 25% commission'),
                      const SizedBox(height: 8),
                      Text(
                        'Your balance: \$${authProvider.balance.toStringAsFixed(2)}',
                        style: TextStyle(
                          color: authProvider.balance >= _betAmount
                              ? Colors.green
                              : Colors.red,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: _isCreating || authProvider.balance < _betAmount
                      ? null
                      : () async {
                          if (_formKey.currentState!.validate()) {
                            setState(() => _isCreating = true);
                            final success =
                                await gameProvider.createGame(_betAmount);
                            setState(() => _isCreating = false);

                            if (success && context.mounted) {
                              await authProvider.loadBalance();
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                    content:
                                        Text('Game created successfully!')),
                              );
                              Navigator.pop(context);
                            } else if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                    content: Text('Failed to create game')),
                              );
                            }
                          }
                        },
                  child: _isCreating
                      ? const CircularProgressIndicator()
                      : const Text('Create Game',
                          style: TextStyle(fontSize: 18)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
