import 'package:flutter/material.dart';
import '../config/theme.dart';
import '../config/colors.dart';

class ThemeProvider extends ChangeNotifier {
  ThemeMode _themeMode = ThemeMode.dark;

  ThemeMode get themeMode => _themeMode;

  void toggleTheme() {
    _themeMode =
        _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    notifyListeners();
  }

  ThemeData getTheme() {
    return AppTheme.darkTheme;
  }
}
