import 'package:flutter/material.dart';
import '../config/colors.dart';

class ToastNotification {
  static OverlayEntry? _currentOverlay;

  static void show({
    required BuildContext context,
    required String message,
    required IconData icon,
    required Color backgroundColor,
    Duration duration = const Duration(seconds: 3),
  }) {
    // Remove existing toast
    _currentOverlay?.remove();

    final overlayState = Overlay.of(context);
    final entry = OverlayEntry(
      builder: (context) => Positioned(
        top: MediaQuery.of(context).padding.top + 60,
        left: 16,
        right: 16,
        child: Material(
          color: Colors.transparent,
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.0, end: 1.0),
            duration: const Duration(milliseconds: 300),
            builder: (context, value, child) {
              return Opacity(
                opacity: value,
                child: Transform.translate(
                  offset: Offset(0, -20 * (1 - value)),
                  child: child,
                ),
              );
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: backgroundColor,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.3),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Icon(icon, color: Colors.white, size: 20),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      message,
                      style: const TextStyle(color: Colors.white, fontSize: 14),
                    ),
                  ),
                  GestureDetector(
                    onTap: () => _currentOverlay?.remove(),
                    child:
                        const Icon(Icons.close, color: Colors.white, size: 16),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );

    _currentOverlay = entry;
    overlayState.insert(entry);

    Future.delayed(duration, () {
      if (_currentOverlay == entry) {
        entry.remove();
        _currentOverlay = null;
      }
    });
  }

  static void showSuccess(BuildContext context, String message) {
    show(
      context: context,
      message: message,
      icon: Icons.check_circle,
      backgroundColor: AppColors.green,
    );
  }

  static void showError(BuildContext context, String message) {
    show(
      context: context,
      message: message,
      icon: Icons.error,
      backgroundColor: AppColors.red,
    );
  }

  static void showInfo(BuildContext context, String message) {
    show(
      context: context,
      message: message,
      icon: Icons.info,
      backgroundColor: AppColors.orange,
    );
  }

  static void showWarning(BuildContext context, String message) {
    show(
      context: context,
      message: message,
      icon: Icons.warning,
      backgroundColor: Colors.orange.shade700,
    );
  }
}
