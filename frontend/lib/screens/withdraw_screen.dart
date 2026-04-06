import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../providers/auth_provider.dart';
import '../services/notification_service.dart';
import '../config/colors.dart';
import '../widgets/custom_button.dart';

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
  String _selectedProvider = 'MTN';

  final List<String> _providers = ['MTN', 'Orange', 'Moov'];

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final maxAmount = authProvider.balance;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Withdraw Funds'),
        backgroundColor: Colors.transparent,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: AppColors.orangeGradient,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Column(
                  children: [
                    const Text(
                      'Available Balance',
                      style: TextStyle(color: Colors.white),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '\$${authProvider.balance.toStringAsFixed(2)}',
                      style: const TextStyle(
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'Select Provider',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Row(
                children: _providers.map((provider) {
                  return Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: GestureDetector(
                        onTap: () =>
                            setState(() => _selectedProvider = provider),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: BoxDecoration(
                            color: _selectedProvider == provider
                                ? AppColors.orange
                                : Colors.grey.shade800,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            provider,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: _selectedProvider == provider
                                  ? AppColors.black
                                  : Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 16),
              const Text(
                'Phone Number',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: InputDecoration(
                  hintText: 'Enter your mobile money number',
                  prefixIcon:
                      Icon(Icons.phone_android, color: AppColors.orange),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
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
                'Amount',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _amountController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  hintText: 'Enter amount (min \$5)',
                  prefixIcon: Icon(Icons.attach_money, color: AppColors.orange),
                  suffixText: 'USD',
                  helperText: 'Max: \$${maxAmount.toStringAsFixed(2)}',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
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
              const SizedBox(height: 16),
              const Text(
                'Quick Amount',
                style: TextStyle(fontSize: 14, color: Colors.grey),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 10,
                children: [10, 20, 50, 100]
                    .where((a) => a <= maxAmount)
                    .map((amount) {
                  return FilterChip(
                    label: Text('\$$amount'),
                    selected: _amountController.text == amount.toString(),
                    onSelected: (_) {
                      setState(() {
                        _amountController.text = amount.toString();
                      });
                    },
                    backgroundColor: Colors.grey.shade800,
                    selectedColor: AppColors.orange,
                    labelStyle: TextStyle(
                      color: _amountController.text == amount.toString()
                          ? AppColors.black
                          : Colors.white,
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 24),
              CustomButton(
                text: 'Withdraw Now',
                onPressed: _isWithdrawing ? () {} : () => _withdraw(),
                icon: Icons.money_off,
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade800,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'ℹ️ Information',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    SizedBox(height: 8),
                    Text('• Processing time: 5-10 minutes'),
                    Text('• Minimum withdrawal: \$5.00'),
                    Text('• No fees for withdrawals'),
                    Text('• Funds sent to your Mobile Money account'),
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
          await Provider.of<AuthProvider>(context, listen: false).loadBalance();
          NotificationService.showSuccess(response['message']);
          Future.delayed(const Duration(seconds: 2), () {
            if (mounted) Navigator.pop(context);
          });
        } else {
          NotificationService.showError(response['message']);
        }
      }
    } catch (e) {
      NotificationService.showError('Withdrawal failed. Please try again.');
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
