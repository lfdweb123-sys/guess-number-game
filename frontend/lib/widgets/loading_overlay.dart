import 'package:flutter/material.dart';
import '../config/colors.dart';

class LoadingOverlay extends StatelessWidget {
  const LoadingOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black.withOpacity(0.7),
      child: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(AppColors.gold),
            ),
            SizedBox(height: 16),
            Text(
              'Loading...',
              style: TextStyle(color: AppColors.gold),
            ),
          ],
        ),
      ),
    );
  }
}
