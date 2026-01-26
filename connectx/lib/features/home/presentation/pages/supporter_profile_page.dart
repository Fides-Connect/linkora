import 'package:flutter/material.dart';

import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';

class SupporterProfilePage extends StatefulWidget {
  const SupporterProfilePage({super.key});

  @override
  State<SupporterProfilePage> createState() => _SupporterProfilePageState();
}

class _SupporterProfilePageState extends State<SupporterProfilePage> {
  // Temporary local state for competencies (ideally this would come from a backend)
  String _introduction = "Hello, I'm Thomas! I have a deep passion for Japanese culture and helpful technology. In my free time, you can find me tending to my garden, fixing smaller things around the house, or relaxing with my cats.";
  late TextEditingController _introController;

  final List<String> _competencies = [
    'Japanese Culture',
    'Computer',
    'Cats',
    'Home Repair',
    'Gardening',
  ];

  @override
  void initState() {
    super.initState();
    _introController = TextEditingController(text: _introduction);
  }

  @override
  void dispose() {
    _introController.dispose();
    super.dispose();
  }

  void _addCompetence(String competence) {
    if (competence.trim().isEmpty) return;
    setState(() {
      _competencies.add(competence.trim());
    });
  }

  void _removeCompetence(int index) {
    setState(() {
      _competencies.removeAt(index);
    });
  }

  Future<void> _showAddCompetenceDialog() async {
    final TextEditingController controller = TextEditingController();
    final localizations = AppLocalizations.of(context);

    return showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text(localizations?.addCompetence ?? 'Add Competence'),
          content: TextField(
            controller: controller,
            decoration: InputDecoration(
              hintText: localizations?.enterCompetence ?? 'Enter competence',
            ),
            autofocus: true,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(localizations?.cancelButton ?? 'Cancel'),
            ),
            TextButton(
              onPressed: () {
                _addCompetence(controller.text);
                Navigator.pop(context);
              },
              child: Text(localizations?.okButton ?? 'OK'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Text(
          localizations?.menuSupporterProfile ?? 'Supporter Profile',
          style: const TextStyle(color: Colors.white),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: Stack(
        children: [
          const AppBackground(),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.only(bottom: 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Self Introduction Section
                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Text(
                      localizations?.selfIntroductionTitle ?? 'Self Introduction',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: TextField(
                        controller: _introController,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          height: 1.5,
                        ),
                        maxLines: null,
                        keyboardType: TextInputType.multiline,
                        decoration: const InputDecoration(
                          border: InputBorder.none,
                          isDense: true,
                          contentPadding: EdgeInsets.zero,
                        ),
                        onChanged: (value) {
                          _introduction = value;
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Text(
                      localizations?.competenciesTitle ?? 'Competencies',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Wrap(
                      spacing: 8.0,
                      runSpacing: 8.0,
                      children: [
                        ..._competencies.asMap().entries.map((entry) {
                          final index = entry.key;
                          final competence = entry.value;
                          return InputChip(
                            label: Text(
                              competence,
                              style: const TextStyle(color: Colors.white),
                            ),
                            backgroundColor: Colors.white.withOpacity(0.1),
                            deleteIcon: const Icon(
                              Icons.close,
                              size: 18,
                              color: Colors.white70,
                            ),
                            onDeleted: () => _removeCompetence(index),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(20),
                              side: BorderSide(
                                color: Colors.white.withOpacity(0.2),
                              ),
                            ),
                          );
                        }),
                        ActionChip(
                          label: const Icon(Icons.add,
                              color: Colors.white, size: 20),
                          backgroundColor: Colors.white.withOpacity(0.1),
                          onPressed: _showAddCompetenceDialog,
                          shape: const CircleBorder(),
                          padding: const EdgeInsets.all(8),
                          side: BorderSide(
                            color: Colors.white.withOpacity(0.2),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Feedback Section
                  const SizedBox(height: 32),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Text(
                      localizations?.feedbackTitle ?? 'Feedback',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  
                  // Average Rating
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            localizations?.averageRating ?? 'Average Rating',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.7),
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              const Text(
                                '4.8',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 32,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(width: 8),
                              const Icon(Icons.star, color: Colors.amber, size: 28),
                              const Icon(Icons.star, color: Colors.amber, size: 28),
                              const Icon(Icons.star, color: Colors.amber, size: 28),
                              const Icon(Icons.star, color: Colors.amber, size: 28),
                              const Icon(Icons.star_half, color: Colors.amber, size: 28),
                              const SizedBox(width: 8),
                              Text(
                                '(124)', // Hardcoded review count
                                style: TextStyle(
                                  color: Colors.white.withOpacity(0.5),
                                  fontSize: 14,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 24),
                  
                  // Positive Feedback
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          localizations?.positiveFeedback ?? 'Positive Feedback',
                          style: const TextStyle(
                            color: Colors.greenAccent,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: const [
                            Chip(
                              label: Text('Friendly'),
                              backgroundColor: Color(0x3369F0AE),
                              labelStyle: TextStyle(color: Colors.white),
                            ),
                            Chip(
                              label: Text('Patient'),
                              backgroundColor: Color(0x3369F0AE),
                              labelStyle: TextStyle(color: Colors.white),
                            ),
                            Chip(
                              label: Text('Calm'),
                              backgroundColor: Color(0x3369F0AE),
                              labelStyle: TextStyle(color: Colors.white),
                            ),
                            Chip(
                              label: Text('Awesome Cat Sitter'),
                              backgroundColor: Color(0x3369F0AE),
                              labelStyle: TextStyle(color: Colors.white),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // Negative Feedback
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                         Text(
                          localizations?.negativeFeedback ?? 'Negative Feedback',
                          style: const TextStyle(
                            color: Colors.redAccent,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: const [
                            Chip(
                              label: Text('Too Late'),
                              backgroundColor: Color(0x33FF5252),
                              labelStyle: TextStyle(color: Colors.white),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
