import 'package:flutter/material.dart';

class NumberPicker extends StatefulWidget {
  final int value;
  final ValueChanged<int> onChanged;

  const NumberPicker({
    super.key,
    required this.value,
    required this.onChanged,
  });

  @override
  State<NumberPicker> createState() => _NumberPickerState();
}

class _NumberPickerState extends State<NumberPicker> {
  late int _currentValue;

  @override
  void initState() {
    super.initState();
    _currentValue = widget.value;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          '$_currentValue',
          style: const TextStyle(fontSize: 48, fontWeight: FontWeight.bold),
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            IconButton(
              icon: const Icon(Icons.remove_circle, size: 40),
              onPressed: () {
                if (_currentValue > 1) {
                  setState(() {
                    _currentValue--;
                  });
                  widget.onChanged(_currentValue);
                }
              },
            ),
            const SizedBox(width: 40),
            IconButton(
              icon: const Icon(Icons.add_circle, size: 40),
              onPressed: () {
                if (_currentValue < 100) {
                  setState(() {
                    _currentValue++;
                  });
                  widget.onChanged(_currentValue);
                }
              },
            ),
          ],
        ),
        Slider(
          value: _currentValue.toDouble(),
          min: 1,
          max: 100,
          divisions: 99,
          label: _currentValue.toString(),
          onChanged: (value) {
            setState(() {
              _currentValue = value.round();
            });
            widget.onChanged(_currentValue);
          },
        ),
      ],
    );
  }
}
