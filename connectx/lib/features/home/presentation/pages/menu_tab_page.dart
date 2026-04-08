import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/providers/user_provider.dart';
import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../main.dart';
import '../../../../services/notification_service.dart';
import '../../../../services/user_service.dart';
import '../viewmodels/home_tab_view_model.dart';
import 'info_page.dart';
import 'legal_page.dart';
import 'user_page.dart';

class MenuTabPage extends StatelessWidget {
  final bool showProfileItem;
  final bool showNotificationsToggle;

  const MenuTabPage({
    super.key,
    this.showProfileItem = true,
    this.showNotificationsToggle = true,
  });

  void _showDeleteAccountDialog(BuildContext context) {
    final localizations = AppLocalizations.of(context);
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: Text(localizations?.deleteAccountConfirmTitle ?? 'Delete Account'),
          content: Text(
            localizations?.deleteAccountConfirmMessage ??
                'Are you sure you want to permanently delete your account? This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: Text(localizations?.cancelButton ?? 'Cancel'),
            ),
            TextButton(
              style: TextButton.styleFrom(foregroundColor: Colors.redAccent),
              onPressed: () async {
                final userProvider = context.read<UserProvider>();
                final messenger = ScaffoldMessenger.of(context);
                final errorText = localizations?.deleteAccountError ??
                    'Failed to delete account. Please sign in again and retry.';
                Navigator.pop(dialogContext);
                try {
                  await userProvider.deleteAccount();
                } catch (e) {
                  messenger.showSnackBar(
                    SnackBar(content: Text(errorText)),
                  );
                }
              },
              child: Text(localizations?.deleteAccount ?? 'Delete Account'),
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
      body: SafeArea(
        child: Stack(
          children: [
            const AppBackground(),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: ListView(
                children: [
                   const SizedBox(height: 20),
                   // User Section
                   Consumer<UserProvider>(
                    builder: (context, userProvider, _) {
                      final user = userProvider.user;
                      if (user == null) return const SizedBox.shrink();
                      
                      return Column(
                        children: [
                          CircleAvatar(
                            radius: 50,
                            backgroundColor: Colors.white.withValues(alpha: 0.1),
                            backgroundImage: user.photoURL != null 
                              ? NetworkImage(user.photoURL!) 
                              : null,
                            child: user.photoURL == null
                              ? const Icon(Icons.person, size: 50, color: Colors.white)
                              : null,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            user.displayName ?? 'User',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          if (user.email != null) ...[
                            const SizedBox(height: 4),
                            Text(
                              user.email!,
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.7),
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ],
                      );
                    },
                   ),
                  const SizedBox(height: 40),
                  if (showProfileItem) ...[
                    _MenuItem(
                      icon: Icons.person_outline,
                      title: localizations?.menuUser ?? 'User',
                      onTap: () {
                        final viewModel = context.read<HomeTabViewModel>();
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => ChangeNotifierProvider.value(
                              value: viewModel,
                              child: const UserPage(),
                            ),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 16),
                  ],
                  _LanguageMenuItem(
                    label: localizations?.menuLanguage ?? 'Language',
                    englishLabel: localizations?.languageEnglish ?? 'English',
                    germanLabel: localizations?.languageGerman ?? 'German',
                  ),
                  const SizedBox(height: 16),
                  if (showNotificationsToggle) ...[  
                    _NotificationsToggleItem(
                      title: localizations?.menuNotifications ?? 'Notifications',
                    ),
                    const SizedBox(height: 16),
                  ],
                  // ── Legal section ─────────────────────────────────────────
                  const Divider(color: Colors.white24, height: 1),
                  const SizedBox(height: 16),
                  _MenuItem(
                    icon: Icons.article_outlined,
                    title: localizations?.menuImpressum ?? 'Legal Notice',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LegalPage(
                          title: localizations?.impressumTitle ?? 'Legal Notice',
                          content: localizations?.impressumContent ?? '',
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  _MenuItem(
                    icon: Icons.privacy_tip_outlined,
                    title: localizations?.menuPrivacyPolicy ?? 'Privacy Policy',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LegalPage(
                          title: localizations?.privacyPolicyTitle ?? 'Privacy Policy',
                          content: localizations?.privacyPolicyContent ?? '',
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  _MenuItem(
                    icon: Icons.gavel_outlined,
                    title: localizations?.menuTermsOfUse ?? 'Terms of Use',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LegalPage(
                          title: localizations?.termsOfUseTitle ?? 'Terms of Use',
                          content: localizations?.termsOfUseContent ?? '',
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  _MenuItem(
                    icon: Icons.warning_amber_outlined,
                    title: localizations?.menuDisclaimer ?? 'Disclaimer',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LegalPage(
                          title: localizations?.disclaimerTitle ?? 'Disclaimer',
                          content: localizations?.disclaimerContent ?? '',
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  _MenuItem(
                    icon: Icons.code_outlined,
                    title: localizations?.menuLicenses ?? 'Licenses',
                    onTap: () => showLicensePage(
                      context: context,
                      applicationName: 'Linkora',
                    ),
                  ),
                  const SizedBox(height: 16),
                  _MenuItem(
                    icon: Icons.info_outline,
                    title: localizations?.menuInfo ?? 'About',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const InfoPage()),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Divider(color: Colors.white24, height: 1),
                  const SizedBox(height: 16),
                  // ── Destructive actions ───────────────────────────────────
                  _MenuItem(
                    icon: Icons.logout,
                    title: localizations?.menuLogout ?? 'Logout',
                    onTap: () async {
                      await context.read<UserProvider>().signOut();
                    },
                    isDestructive: true,
                    showArrow: false,
                    centered: true,
                  ),
                  const SizedBox(height: 16),
                  _MenuItem(
                    icon: Icons.delete_forever,
                    title: localizations?.deleteAccount ?? 'Delete Account',
                    onTap: () => _showDeleteAccountDialog(context),
                    isDestructive: true,
                    showArrow: false,
                    centered: true,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MenuItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final bool isDestructive;
  final bool showArrow;
  final bool centered;

  const _MenuItem({
    required this.icon,
    required this.title,
    required this.onTap,
    this.isDestructive = false,
    this.showArrow = true,
    this.centered = false,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            mainAxisAlignment: centered ? MainAxisAlignment.center : MainAxisAlignment.start,
            children: [
              Icon(
                icon,
                color: isDestructive ? Colors.redAccent : Colors.white,
              ),
              const SizedBox(width: 16),
              Text(
                title,
                style: TextStyle(
                  color: isDestructive ? Colors.redAccent : Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
              if (showArrow) ...[
                const Spacer(),
                Icon(
                  Icons.arrow_forward_ios,
                  color: isDestructive ? Colors.redAccent : Colors.white70,
                  size: 16,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _NotificationsToggleItem extends StatefulWidget {
  final String title;
  const _NotificationsToggleItem({required this.title});

  @override
  State<_NotificationsToggleItem> createState() => _NotificationsToggleItemState();
}

class _NotificationsToggleItemState extends State<_NotificationsToggleItem> {
  late bool _enabled;
  final _notificationService = NotificationService();

  @override
  void initState() {
    super.initState();
    _enabled = _notificationService.notificationsEnabled;
  }

  Future<void> _toggle(bool value) async {
    await _notificationService.setNotificationsEnabled(value);
    setState(() => _enabled = value);
    final success = await UserService().updateSettings(notificationsEnabled: value);
    if (!success) {
      // Revert local state if backend update failed.
      await _notificationService.setNotificationsEnabled(!value);
      if (!mounted) return;
      setState(() => _enabled = !value);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Failed to update notification settings. Please try again.'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Icon(
              _enabled ? Icons.notifications_active : Icons.notifications_off,
              color: Colors.white,
            ),
            const SizedBox(width: 16),
            Text(
              widget.title,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
            const Spacer(),
            Switch(
              value: _enabled,
              onChanged: _toggle,
              activeThumbColor: Colors.white,
              activeTrackColor: Colors.blueAccent,
            ),
          ],
        ),
      ),
    );
  }
}

/// Inline language selector that shows the active language without a dialog.
///
/// Renders a card with a label on the left and a segmented EN / DE toggle on
/// the right.  The selected language is highlighted; tapping the other option
/// updates the locale and persists the preference immediately.
class _LanguageMenuItem extends StatelessWidget {
  final String label;
  final String englishLabel;
  final String germanLabel;

  const _LanguageMenuItem({
    required this.label,
    required this.englishLabel,
    required this.germanLabel,
  });

  Future<void> _select(BuildContext context, String langCode) async {
    ConnectXApp.setLocale(context, Locale(langCode, ''));
    await UserService().updateSettings(language: langCode);
  }

  @override
  Widget build(BuildContext context) {
    final currentCode = Localizations.localeOf(context).languageCode;

    return Material(
      color: Colors.white.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            const Icon(Icons.language, color: Colors.white),
            const SizedBox(width: 16),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
            const Spacer(),
            // Segmented toggle
            Container(
              height: 34,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _LangChip(
                    label: englishLabel,
                    shortLabel: 'EN',
                    selected: currentCode == 'en',
                    onTap: () => _select(context, 'en'),
                  ),
                  _LangChip(
                    label: germanLabel,
                    shortLabel: 'DE',
                    selected: currentCode == 'de',
                    onTap: () => _select(context, 'de'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LangChip extends StatelessWidget {
  final String label;
  final String shortLabel;
  final bool selected;
  final VoidCallback onTap;

  const _LangChip({
    required this.label,
    required this.shortLabel,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      child: GestureDetector(
        onTap: selected ? null : onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            color: selected ? Colors.white : Colors.transparent,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            shortLabel,
            style: TextStyle(
              color: selected ? Colors.black87 : Colors.white,
              fontWeight: selected ? FontWeight.bold : FontWeight.normal,
              fontSize: 13,
            ),
          ),
        ),
      ),
    );
  }
}
