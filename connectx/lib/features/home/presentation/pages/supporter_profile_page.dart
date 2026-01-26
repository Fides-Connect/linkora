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
  final List<String> _competencies = [
    'Flutter Development',
    'Dart',
    'Firebase',
    'UI/UX Design',
  ];

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
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddCompetenceDialog,
        child: const Icon(Icons.add),
      ),
      body: Stack(
        children: [
          const AppBackground(),
          SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
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
                Expanded(
                  child: ListView.builder(
                    itemCount: _competencies.length,
                    itemBuilder: (context, index) {
                      final competence = _competencies[index];
                      return Dismissible(
                        key: Key(competence),
                        background: Container(
                          color: Colors.red,
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: 20),
                          child: const Icon(Icons.delete, color: Colors.white),
                        ),
                        direction: DismissDirection.endToStart,
                        onDismissed: (direction) {
                          _removeCompetence(index);
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('${localizations?.delete} $competence'),
                            ),
                          );
                        },
                        child: Card(
                          margin: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 8,
                          ),
                          color: Colors.white.withOpacity(0.1),
                          child: ListTile(
                            title: Text(
                              competence,
                              style: const TextStyle(color: Colors.white),
                            ),
                            trailing: IconButton(
                              icon: const Icon(Icons.delete, color: Colors.white70),
                              onPressed: () => _removeCompetence(index),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
