import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';

/// About / Info page.
///
/// Shows the app version (read at runtime), a credits section, and a link to
/// the GitHub project.  Edit [_credits] below to update the listed people.
/// Replace [_githubUrl] with the public project URL when ready.
class InfoPage extends StatefulWidget {
  const InfoPage({super.key});

  @override
  State<InfoPage> createState() => _InfoPageState();
}

class _InfoPageState extends State<InfoPage> {
  // ── Customise these ────────────────────────────────────────────────────────

  /// GitHub (or any public project) URL shown on the page.
  static const String _githubUrl = 'https://github.com/Fides-Connect/Fides';

  /// People / teams to credit.  Add or remove entries freely.
  static const List<_CreditEntry> _credits = [
    _CreditEntry(name: '[Your name here]', role: '[Role / Contribution]'),
    _CreditEntry(name: '[Contributor]',    role: '[Role / Contribution]'),
  ];

  // ── State ──────────────────────────────────────────────────────────────────

  String _version = '—';
  String _buildNumber = '—';

  @override
  void initState() {
    super.initState();
    PackageInfo.fromPlatform().then((info) {
      if (mounted) {
        setState(() {
          _version     = info.version;
          _buildNumber = info.buildNumber;
        });
      }
    });
  }

  Future<void> _openUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Text(localizations?.menuInfo ?? 'About'),
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: Colors.white,
      ),
      body: Stack(
        children: [
          const AppBackground(),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // ── App identity ──────────────────────────────────────────
                  Center(
                    child: SizedBox(
                      width: 80,
                      height: 80,
                      child: Image.asset(
                        'assets/images/LinkoraLogo.png',
                        fit: BoxFit.contain,
                        semanticLabel: 'Linkora Logo',
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Center(
                    child: Text(
                      'Linkora',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Center(
                    child: Text(
                      '${localizations?.infoVersion ?? 'Version'} $_version (${localizations?.infoBuild ?? 'Build'} $_buildNumber)',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.7),
                        fontSize: 14,
                      ),
                    ),
                  ),

                  const SizedBox(height: 32),
                  _SectionHeader(localizations?.infoCreditsTitle ?? 'Credits'),
                  const SizedBox(height: 12),

                  // ── Credits list ──────────────────────────────────────────
                  ..._credits.map(
                    (e) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _InfoCard(
                        child: Row(
                          children: [
                            const Icon(Icons.person_outline, color: Colors.white70, size: 20),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    e.name,
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15,
                                    ),
                                  ),
                                  Text(
                                    e.role,
                                    style: TextStyle(
                                      color: Colors.white.withValues(alpha: 0.65),
                                      fontSize: 13,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 24),
                  _SectionHeader(localizations?.infoLinksTitle ?? 'Links'),
                  const SizedBox(height: 12),

                  // ── GitHub link ───────────────────────────────────────────
                  _InfoCard(
                    onTap: () => _openUrl(_githubUrl),
                    child: Row(
                      children: [
                        const Icon(Icons.code, color: Colors.white70, size: 20),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                localizations?.infoGithubLabel ?? 'GitHub Project',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w600,
                                  fontSize: 15,
                                ),
                              ),
                              Text(
                                _githubUrl,
                                style: TextStyle(
                                  color: Colors.white.withValues(alpha: 0.65),
                                  fontSize: 12,
                                  decoration: TextDecoration.underline,
                                  decorationColor: Colors.white54,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const Icon(Icons.open_in_new, color: Colors.white54, size: 16),
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

// ── Helpers ──────────────────────────────────────────────────────────────────

class _CreditEntry {
  final String name;
  final String role;
  const _CreditEntry({required this.name, required this.role});
}

class _SectionHeader extends StatelessWidget {
  final String text;
  const _SectionHeader(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: TextStyle(
        color: Colors.white.withValues(alpha: 0.5),
        fontSize: 11,
        fontWeight: FontWeight.w700,
        letterSpacing: 1.2,
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;
  const _InfoCard({required this.child, this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: child,
        ),
      ),
    );
  }
}
