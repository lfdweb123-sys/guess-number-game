import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../providers/auth_provider.dart';

class WithdrawScreen extends StatefulWidget {
  const WithdrawScreen({super.key});

  @override
  State<WithdrawScreen> createState() => _WithdrawScreenState();
}

class _WithdrawScreenState extends State<WithdrawScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _amountController = TextEditingController();
  bool _isWithdrawing = false;

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final maxAmount = authProvider.balance;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Withdraw Funds'),
        backgroundColor: Colors.orange,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Balance info card
              Card(
                color: Colors.orange.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      const Text(
                        'Available Balance',
                        style: TextStyle(fontSize: 14, color: Colors.grey),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '\$${authProvider.balance.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontSize: 32,
                          fontWeight: FontWeight.bold,
                          color: Colors.orange,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              const Text(
                'Mobile Money Number',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'Enter your mobile money number',
                  prefixIcon: Icon(Icons.phone_android),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Please enter phone number';
                  }
                  if (value.length < 9) {
                    return 'Enter valid phone number';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              const Text(
                'Amount to Withdraw',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _amountController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  border: const OutlineInputBorder(),
                  hintText: 'Enter amount',
                  prefixIcon: const Icon(Icons.attach_money),
                  suffixText: 'Max: \$${maxAmount.toStringAsFixed(2)}',
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Please enter amount';
                  }
                  final amount = double.tryParse(value);
                  if (amount == null || amount <= 0) {
                    return 'Please enter valid amount';
                  }
                  if (amount < 5) {
                    return 'Minimum withdrawal is \$5';
                  }
                  if (amount > maxAmount) {
                    return 'Insufficient balance';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 24),

              // Quick amount buttons
              Wrap(
                spacing: 10,
                children: [10, 20, 50, 100].map((amount) {
                  return FilterChip(
                    label: Text('\$$amount'),
                    selected: false,
                    onSelected: (_) {
                      setState(() {
                        _amountController.text = amount.toString();
                      });
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 24),

              SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: _isWithdrawing ? null : _withdraw,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.orange,
                    foregroundColor: Colors.white,
                  ),
                  child: _isWithdrawing
                      ? const CircularProgressIndicator(color: Colors.white)
                      : const Text(
                          'Withdraw Now',
                          style: TextStyle(fontSize: 18),
                        ),
                ),
              ),
              const SizedBox(height: 16),

              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey.shade300),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Withdrawal Information:',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    SizedBox(height: 8),
                    Text('• Processing time: 5-10 minutes'),
                    Text('• Minimum withdrawal: \$5.00'),
                    Text('• Funds sent to your Mobile Money account'),
                    Text('• No fees for withdrawals'),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _withdraw() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isWithdrawing = true);

    try {
      final amount = double.parse(_amountController.text);
      final response = await ApiService.mobileMoneyWithdraw(
        _phoneController.text,
        amount,
      );

      if (mounted) {
        if (response['success']) {
          // Refresh balance
          await Provider.of<AuthProvider>(context, listen: false).loadBalance();

          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(response['message']),
              backgroundColor: Colors.green,
            ),
          );

          // Close screen after 2 seconds
          Future.delayed(const Duration(seconds: 2), () {
            if (mounted) Navigator.pop(context);
          });
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(response['message']),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Withdrawal failed. Please try again.'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isWithdrawing = false);
      }
    }
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _amountController.dispose();
    super.dispose();
  }
}
