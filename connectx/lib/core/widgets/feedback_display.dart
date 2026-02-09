import 'package:flutter/material.dart';

class FeedbackDisplay extends StatelessWidget {
  final String title;
  final List<String> feedbackItems;
  final Color titleColor;
  final Color chipColor;

  const FeedbackDisplay({
    super.key,
    required this.title,
    required this.feedbackItems,
    required this.titleColor,
    required this.chipColor,
  });

  @override
  Widget build(BuildContext context) {
    if (feedbackItems.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 24),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(
                  color: titleColor,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: feedbackItems.map((item) {
                  return Chip(
                    label: Text(item),
                    backgroundColor: chipColor,
                    labelStyle: const TextStyle(color: Colors.white),
                  );
                }).toList(),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
