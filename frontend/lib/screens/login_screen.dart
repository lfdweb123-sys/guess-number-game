import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../config/colors.dart';
import '../widgets/custom_button.dart';
import '../services/notification_service.dart';
import 'home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _regUsernameController = TextEditingController();
  final TextEditingController _regPasswordController = TextEditingController();
  final TextEditingController _confirmPasswordController =
      TextEditingController();

  bool _isLogin = true;
  bool _obscurePassword = true;
  bool _obscureRegPassword = true;
  bool _isLoading = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: AppColors.backgroundGradient,
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                const SizedBox(height: 50),
                // Logo
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: AppColors.goldGradient,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.games,
                    size: 50,
                    color: AppColors.black,
                  ),
                ),
                const SizedBox(height: 20),
                const Text(
                  'GUESS NUMBER',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: AppColors.gold,
                    letterSpacing: 2,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Premium Gaming Experience',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                ),
                const SizedBox(height: 40),

                // Switch buttons
                Row(
                  children: [
                    Expanded(
                      child: GestureDetector(
                        onTap: () => setState(() => _isLogin = true),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: BoxDecoration(
                            border: Border(
                              bottom: BorderSide(
                                color: _isLogin ? AppColors.gold : Colors.grey,
                                width: 2,
                              ),
                            ),
                          ),
                          child: Text(
                            'LOGIN',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: _isLogin ? AppColors.gold : Colors.grey,
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      child: GestureDetector(
                        onTap: () => setState(() => _isLogin = false),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: BoxDecoration(
                            border: Border(
                              bottom: BorderSide(
                                color: !_isLogin ? AppColors.gold : Colors.grey,
                                width: 2,
                              ),
                            ),
                          ),
                          child: Text(
                            'REGISTER',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: !_isLogin ? AppColors.gold : Colors.grey,
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 30),

                // Form
                if (_isLogin) _buildLoginForm() else _buildRegisterForm(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLoginForm() {
    final authProvider = Provider.of<AuthProvider>(context);

    return Column(
      children: [
        TextField(
          controller: _usernameController,
          style: const TextStyle(color: AppColors.white),
          decoration: const InputDecoration(
            labelText: 'Username',
            prefixIcon: Icon(Icons.person, color: AppColors.gold),
            hintText: 'Enter your username',
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _passwordController,
          obscureText: _obscurePassword,
          style: const TextStyle(color: AppColors.white),
          decoration: InputDecoration(
            labelText: 'Password',
            prefixIcon: const Icon(Icons.lock, color: AppColors.gold),
            suffixIcon: IconButton(
              icon: Icon(
                _obscurePassword ? Icons.visibility_off : Icons.visibility,
                color: AppColors.gold,
              ),
              onPressed: () =>
                  setState(() => _obscurePassword = !_obscurePassword),
            ),
            hintText: 'Enter your password',
          ),
        ),
        const SizedBox(height: 24),
        CustomButton(
          text: 'Login',
          onPressed: () async {
            if (_usernameController.text.isEmpty ||
                _passwordController.text.isEmpty) {
              NotificationService.showError('Please fill all fields');
              return;
            }

            setState(() => _isLoading = true);
            final success = await authProvider.login(
              _usernameController.text,
              _passwordController.text,
            );
            setState(() => _isLoading = false);

            if (success && mounted) {
              NotificationService.showSuccess('Welcome back!');
              Navigator.pushReplacement(
                context,
                MaterialPageRoute(builder: (_) => const HomeScreen()),
              );
            } else {
              NotificationService.showError('Invalid credentials');
            }
          },
          isLoading: _isLoading,
          icon: Icons.login,
        ),
        const SizedBox(height: 16),
        TextButton(
          onPressed: () {
            // TODO: Forgot password
            NotificationService.showInfo('Contact support to reset password');
          },
          child: const Text(
            'Forgot Password?',
            style: TextStyle(color: AppColors.gold),
          ),
        ),
      ],
    );
  }

  Widget _buildRegisterForm() {
    final authProvider = Provider.of<AuthProvider>(context);

    return Column(
      children: [
        TextField(
          controller: _regUsernameController,
          style: const TextStyle(color: AppColors.white),
          decoration: const InputDecoration(
            labelText: 'Username',
            prefixIcon: Icon(Icons.person, color: AppColors.gold),
            hintText: 'Choose a username',
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _regPasswordController,
          obscureText: _obscureRegPassword,
          style: const TextStyle(color: AppColors.white),
          decoration: InputDecoration(
            labelText: 'Password',
            prefixIcon: const Icon(Icons.lock, color: AppColors.gold),
            suffixIcon: IconButton(
              icon: Icon(
                _obscureRegPassword ? Icons.visibility_off : Icons.visibility,
                color: AppColors.gold,
              ),
              onPressed: () =>
                  setState(() => _obscureRegPassword = !_obscureRegPassword),
            ),
            hintText: 'Choose a strong password',
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _confirmPasswordController,
          obscureText: _obscureRegPassword,
          style: const TextStyle(color: AppColors.white),
          decoration: const InputDecoration(
            labelText: 'Confirm Password',
            prefixIcon: Icon(Icons.lock_outline, color: AppColors.gold),
            hintText: 'Confirm your password',
          ),
        ),
        const SizedBox(height: 24),
        CustomButton(
          text: 'Register',
          onPressed: () async {
            final username = _regUsernameController.text.trim();
            final password = _regPasswordController.text;
            final confirm = _confirmPasswordController.text;

            if (username.isEmpty || password.isEmpty) {
              NotificationService.showError('Please fill all fields');
              return;
            }

            if (password.length < 4) {
              NotificationService.showError(
                  'Password must be at least 4 characters');
              return;
            }

            if (password != confirm) {
              NotificationService.showError('Passwords do not match');
              return;
            }

            setState(() => _isLoading = true);
            final success = await authProvider.register(username, password);
            setState(() => _isLoading = false);

            if (success && mounted) {
              NotificationService.showSuccess('Account created! Please login');
              setState(() {
                _isLogin = true;
                _regUsernameController.clear();
                _regPasswordController.clear();
                _confirmPasswordController.clear();
              });
            } else {
              NotificationService.showError(
                  'Registration failed. Username may already exist.');
            }
          },
          isLoading: _isLoading,
          icon: Icons.app_registration,
        ),
      ],
    );
  }
}
