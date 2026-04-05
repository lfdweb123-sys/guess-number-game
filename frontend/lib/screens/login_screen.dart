import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../screens/home_screen.dart';

class LoginScreen extends StatelessWidget {
  final TextEditingController usernameController = TextEditingController();
  final TextEditingController passwordController = TextEditingController();
  final TextEditingController registerUsernameController =
      TextEditingController();
  final TextEditingController registerPasswordController =
      TextEditingController();

  LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Colors.blue, Colors.purple],
            ),
          ),
          child: Center(
            child: Card(
              margin: const EdgeInsets.all(20),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'Guess Number Game',
                      style:
                          TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 20),
                    const TabBar(
                      tabs: [
                        Tab(text: 'Login'),
                        Tab(text: 'Register'),
                      ],
                    ),
                    const SizedBox(height: 20),
                    SizedBox(
                      height: 200,
                      child: TabBarView(
                        children: [
                          _buildLoginForm(context),
                          _buildRegisterForm(context),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLoginForm(BuildContext context) {
    return Column(
      children: [
        TextField(
          controller: usernameController,
          decoration: const InputDecoration(
            labelText: 'Username',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: passwordController,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'Password',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 20),
        ElevatedButton(
          onPressed: () async {
            final authProvider =
                Provider.of<AuthProvider>(context, listen: false);
            final success = await authProvider.login(
              usernameController.text,
              passwordController.text,
            );
            if (success && context.mounted) {
              Navigator.pushReplacement(
                context,
                MaterialPageRoute(builder: (_) => const HomeScreen()),
              );
            } else {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Login failed')),
              );
            }
          },
          style: ElevatedButton.styleFrom(
              minimumSize: const Size(double.infinity, 45)),
          child: const Text('Login'),
        ),
      ],
    );
  }

  Widget _buildRegisterForm(BuildContext context) {
    return Column(
      children: [
        TextField(
          controller: registerUsernameController,
          decoration: const InputDecoration(
            labelText: 'Username',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: registerPasswordController,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'Password',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 20),
        ElevatedButton(
          onPressed: () async {
            final authProvider =
                Provider.of<AuthProvider>(context, listen: false);
            final success = await authProvider.register(
              registerUsernameController.text,
              registerPasswordController.text,
            );
            if (success && context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                    content: Text('Registration successful! Please login.')),
              );
              registerUsernameController.clear();
              registerPasswordController.clear();
            } else {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Registration failed')),
              );
            }
          },
          style: ElevatedButton.styleFrom(
              minimumSize: const Size(double.infinity, 45)),
          child: const Text('Register'),
        ),
      ],
    );
  }
}
