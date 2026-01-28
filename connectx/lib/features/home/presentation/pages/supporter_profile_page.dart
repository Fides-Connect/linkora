import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/widgets/app_background.dart';
import '../../../../core/widgets/star_rating.dart';
import '../../../../localization/app_localizations.dart';
import '../viewmodels/home_tab_view_model.dart';

class SupporterProfilePage extends StatefulWidget {
  const SupporterProfilePage({super.key});

  @override
  State<SupporterProfilePage> createState() => _SupporterProfilePageState();
}

class _SupporterProfilePageState extends State<SupporterProfilePage> {
  // Temporary local state for competencies (seeded from mock data)
  late String _introduction;
  late TextEditingController _introController;
  // late List<String> _competencies; // No longer needed as we use provider directly

  @override
  void initState() {
    super.initState();
    final viewModel = context.read<HomeTabViewModel>();
    final profile = viewModel.userProfile;
    
    // Fallback if profile not loaded yet (though it should be)
    _introduction = profile?.introduction ?? '';
    // _competencies = List.from(profile?.competencies ?? []);
    
    _introController = TextEditingController(text: _introduction);
  }

  @override
  void dispose() {
    _introController.dispose();
    super.dispose();
  }

  void _addCompetence(String competence) {
    if (competence.trim().isEmpty) return;
    context.read<HomeTabViewModel>().addCompetence(competence.trim());
  }

  void _removeCompetence(String competence) {
    context.read<HomeTabViewModel>().removeCompetence(competence);
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
    final viewModel = context.watch<HomeTabViewModel>();
    final profile = viewModel.userProfile;

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
                        color: Colors.white.withValues(alpha: 0.1),
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
                  
                  // Save Button for Introduction
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.blueAccent,
                          foregroundColor: Colors.white,
                        ),
                        onPressed: () {
                          viewModel.updateIntroduction(_introduction);
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Profile saved')),
                          );
                        },
                        child: Text(localizations?.saveButton ?? 'Save'),
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
                        ...?profile?.competencies.map((competence) {
                          return InputChip(
                            label: Text(
                              competence,
                              style: const TextStyle(color: Colors.white),
                            ),
                            backgroundColor: Colors.white.withValues(alpha: 0.1),
                            deleteIcon: const Icon(
                              Icons.close,
                              size: 18,
                              color: Colors.white70,
                            ),
                            onDeleted: () => _removeCompetence(competence),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(20),
                              side: BorderSide(
                                color: Colors.white.withValues(alpha: 0.2),
                              ),
                            ),
                          );
                        }),
                        ActionChip(
                          label: const Icon(Icons.add,
                              color: Colors.white, size: 20),
                          backgroundColor: Colors.white.withValues(alpha: 0.1),
                          onPressed: _showAddCompetenceDialog,
                          shape: const CircleBorder(),
                          padding: const EdgeInsets.all(8),
                          side: BorderSide(
                            color: Colors.white.withValues(alpha: 0.2),
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
                        color: Colors.white.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            localizations?.averageRating ?? 'Average Rating',
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.7),
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Text(
                                profile?.rating.toString() ?? '0.0',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 32,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(width: 8),
                              StarRating(
                                rating: profile?.rating ?? 0.0,
                                size: 28,
                              ),
                              const SizedBox(width: 8),
                              Text(
                                '(${profile?.reviewCount ?? 0})', 
                                style: TextStyle(
                                  color: Colors.white.withValues(alpha: 0.5),
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
                          children: (profile?.positiveFeedback ?? []).map((feedback) {
                            return Chip(
                              label: Text(feedback),
                              backgroundColor: const Color(0x3369F0AE),
                              labelStyle: const TextStyle(color: Colors.white),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // Negative Feedback
                  if (profile != null && profile.negativeFeedback.isNotEmpty)
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
                            children: profile.negativeFeedback.map((feedback) {
                              return Chip(
                                label: Text(feedback),
                                backgroundColor: const Color(0x33FF5252),
                                labelStyle: const TextStyle(color: Colors.white),
                              );
                            }).toList(),
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
