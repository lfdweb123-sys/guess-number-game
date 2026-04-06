class AppValidators {
  // Validate username
  static String? validateUsername(String? value) {
    if (value == null || value.isEmpty) {
      return 'Username is required';
    }
    if (value.length < 3) {
      return 'Username must be at least 3 characters';
    }
    if (value.length > 20) {
      return 'Username must be less than 20 characters';
    }
    if (!RegExp(r'^[a-zA-Z0-9_]+$').hasMatch(value)) {
      return 'Username can only contain letters, numbers, and underscore';
    }
    return null;
  }

  // Validate password
  static String? validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Password is required';
    }
    if (value.length < 4) {
      return 'Password must be at least 4 characters';
    }
    if (value.length > 72) {
      return 'Password must be less than 72 characters';
    }
    return null;
  }

  // Validate confirm password
  static String? validateConfirmPassword(String? value, String password) {
    if (value == null || value.isEmpty) {
      return 'Please confirm your password';
    }
    if (value != password) {
      return 'Passwords do not match';
    }
    return null;
  }

  // Validate phone number
  static String? validatePhoneNumber(String? value) {
    if (value == null || value.isEmpty) {
      return 'Phone number is required';
    }
    if (!RegExp(r'^[0-9]{9,15}$').hasMatch(value)) {
      return 'Enter a valid phone number (9-15 digits)';
    }
    return null;
  }

  // Validate amount
  static String? validateAmount(String? value, {double? min, double? max}) {
    if (value == null || value.isEmpty) {
      return 'Amount is required';
    }
    final amount = double.tryParse(value);
    if (amount == null) {
      return 'Enter a valid number';
    }
    if (amount <= 0) {
      return 'Amount must be greater than 0';
    }
    if (min != null && amount < min) {
      return 'Minimum amount is \$${min.toStringAsFixed(2)}';
    }
    if (max != null && amount > max) {
      return 'Maximum amount is \$${max.toStringAsFixed(2)}';
    }
    return null;
  }

  // Validate bet amount
  static String? validateBetAmount(String? value, double balance) {
    final amountError = validateAmount(value, min: 5, max: 100);
    if (amountError != null) return amountError;

    final amount = double.parse(value!);
    if (amount > balance) {
      return 'Insufficient balance. You have \$${balance.toStringAsFixed(2)}';
    }
    return null;
  }

  // Validate game number
  static String? validateGameNumber(int? value) {
    if (value == null) {
      return 'Please select a number';
    }
    if (value < 1 || value > 100) {
      return 'Number must be between 1 and 100';
    }
    return null;
  }

  // Validate email
  static String? validateEmail(String? value) {
    if (value == null || value.isEmpty) {
      return 'Email is required';
    }
    if (!RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$').hasMatch(value)) {
      return 'Enter a valid email address';
    }
    return null;
  }

  // Validate not empty
  static String? validateNotEmpty(String? value, String fieldName) {
    if (value == null || value.isEmpty) {
      return '$fieldName is required';
    }
    return null;
  }

  // Validate numeric
  static String? validateNumeric(String? value) {
    if (value == null || value.isEmpty) {
      return 'Value is required';
    }
    if (double.tryParse(value) == null) {
      return 'Enter a valid number';
    }
    return null;
  }

  // Validate integer
  static String? validateInteger(String? value) {
    if (value == null || value.isEmpty) {
      return 'Value is required';
    }
    if (int.tryParse(value) == null) {
      return 'Enter a valid integer';
    }
    return null;
  }
}
