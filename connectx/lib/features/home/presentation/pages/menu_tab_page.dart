import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../../core/providers/user_provider.dart';
import '../../../../core/theme/app_theme_colors.dart';
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
    final l10n = AppLocalizations.of(context);
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n?.deleteAccountConfirmTitle ?? 'Delete Account'),
        content: Text(
          l10n?.deleteAccountConfirmMessage ??
              'Are you sure you want to permanently delete your account? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(l10n?.cancelButton ?? 'Cancel'),
          ),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: Colors.redAccent),
            onPressed: () async {
              final userProvider = context.read<UserProvider>();
              final messenger = ScaffoldMessenger.of(context);
              final errorText = l10n?.deleteAccountError ??
                  'Failed to delete account. Please sign in again and retry.';
              Navigator.pop(dialogContext);
              try {
                await userProvider.deleteAccount();
              } catch (e) {
                messenger.showSnackBar(SnackBar(content: Text(errorText)));
              }
            },
            child: Text(l10n?.deleteAccount ?? 'Delete Account'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      body: Stack(
        children: [
          const AppBackground(),
          SafeArea(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 24, 16, 48),
              children: [
                // ── Profile header ──────────────────────────────────────
                Consumer<UserProvider>(
                  builder: (context, userProvider, _) {
                    final user = userProvider.user;
                    if (user == null) return const SizedBox.shrink();
                    return _ProfileCard(
                      displayName: user.displayName ?? 'User',
                      email: user.email,
                      photoURL: user.photoURL,
                      showEdit: showProfileItem,
                      editLabel: l10n?.editProfile ?? 'Edit Profile',
                      onEditTap: showProfileItem
                          ? () {
                              final viewModel =
                                  context.read<HomeTabViewModel>();
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => ChangeNotifierProvider.value(
                                    value: viewModel,
                                    child: const UserPage(),
                                  ),
                                ),
                              );
                            }
                          : null,
                    );
                  },
                ),

                const SizedBox(height: 32),

                // ── Preferences ─────────────────────────────────────────
                _SectionHeader(
                    label: l10n?.preferencesSection ?? 'Preferences'),
                const SizedBox(height: 8),
                _SettingsGroup(children: [
                  _LanguageRow(
                    label: l10n?.menuLanguage ?? 'Language',
                    englishLabel: l10n?.languageEnglish ?? 'English',
                    germanLabel: l10n?.languageGerman ?? 'German',
                  ),
                  _ThemeModeRow(l10n: l10n),
                  if (showNotificationsToggle)
                    _NotificationsRow(
                      title: l10n?.menuNotifications ?? 'Notifications',
                    ),
                ]),
                const SizedBox(height: 32),

                // ── Legal ────────────────────────────────────────────────
                _SectionHeader(label: l10n?.legalSection ?? 'Legal'),
                const SizedBox(height: 8),
                _SettingsGroup(children: [
                  _SettingsRow(
                    icon: Icons.article_outlined,
                    iconColor: const Color(0xFF3B82F6),
                    title: l10n?.menuImpressum ?? 'Legal Notice',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LegalPage(
                          title: l10n?.impressumTitle ?? 'Legal Notice',
                          url: 'https://fides-connect.github.io/linkora/legal/legal-notice.html',
                        ),
                      ),
                    ),
                  ),
                  _SettingsRow(
                    icon: Icons.privacy_tip_outlined,
                    iconColor: const Color(0xFF10B981),
                    title: l10n?.menuPrivacyPolicy ?? 'Privacy Policy',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LegalPage(
                          title: l10n?.privacyPolicyTitle ?? 'Privacy Policy',
                          url: 'https://fides-connect.github.io/linkora/legal/privacy-policy.html',
                        ),
                      ),
                    ),
                  ),
                  _SettingsRow(
                    icon: Icons.gavel_outlined,
                    iconColor: const Color(0xFFF59E0B),
                    title: l10n?.menuTermsOfUse ?? 'Terms of Use',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LegalPage(
                          title: l10n?.termsOfUseTitle ?? 'Terms of Use',
                          url: 'https://fides-connect.github.io/linkora/legal/terms-of-use.html',
                        ),
                      ),
                    ),
                  ),
                  _SettingsRow(
                    icon: Icons.warning_amber_outlined,
                    iconColor: const Color(0xFFEF4444),
                    title: l10n?.menuDisclaimer ?? 'Disclaimer',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LegalPage(
                          title: l10n?.disclaimerTitle ?? 'Disclaimer',
                          url: 'https://fides-connect.github.io/linkora/legal/disclaimer.html',
                        ),
                      ),
                    ),
                  ),
                  _SettingsRow(
                    icon: Icons.code_outlined,
                    iconColor: const Color(0xFF8B5CF6),
                    title: l10n?.menuLicenses ?? 'Licenses',
                    onTap: () => showLicensePage(
                      context: context,
                      applicationName: 'Linkora',
                    ),
                  ),
                  _SettingsRow(
                    icon: Icons.info_outline,
                    iconColor: const Color(0xFF6366F1),
                    title: l10n?.menuInfo ?? 'About',
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const InfoPage()),
                    ),
                  ),
                ]),

                const SizedBox(height: 32),

                // ── Account ──────────────────────────────────────────────
                _SectionHeader(label: l10n?.accountSection ?? 'Account'),
                const SizedBox(height: 8),
                _SettingsGroup(children: [
                  _SettingsRow(
                    icon: Icons.logout_rounded,
                    iconColor: Colors.orange,
                    title: l10n?.menuLogout ?? 'Sign Out',
                    showChevron: false,
                    onTap: () async {
                      await context.read<UserProvider>().signOut();
                    },
                  ),
                  _SettingsRow(
                    icon: Icons.delete_forever_rounded,
                    iconColor: Colors.redAccent,
                    title: l10n?.deleteAccount ?? 'Delete Account',
                    isDestructive: true,
                    showChevron: false,
                    onTap: () => _showDeleteAccountDialog(context),
                  ),
                ]),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Profile card
// ─────────────────────────────────────────────────────────────────────────────

class _ProfileCard extends StatelessWidget {
  final String displayName;
  final String? email;
  final String? photoURL;
  final bool showEdit;
  final String editLabel;
  final VoidCallback? onEditTap;

  const _ProfileCard({
    required this.displayName,
    this.email,
    this.photoURL,
    required this.showEdit,
    required this.editLabel,
    this.onEditTap,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        color: context.appSurface1,
        borderRadius: BorderRadius.circular(20),
        boxShadow: isDark
            ? null
            : [
                BoxShadow(
                  color: const Color(0xFF6366F1).withValues(alpha: 0.10),
                  blurRadius: 32,
                  offset: const Offset(0, 6),
                ),
              ],
      ),
      child: Column(
        children: [
          // Accent gradient banner
          Container(
            height: 72,
            decoration: BoxDecoration(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(20)),
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF6366F1)
                      .withValues(alpha: isDark ? 0.45 : 0.28),
                  const Color(0xFF22D3EE)
                      .withValues(alpha: isDark ? 0.20 : 0.15),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
          ),
          // Avatar + info (overlaps the banner)
          Transform.translate(
            offset: const Offset(0, -36),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(
                children: [
                  Container(
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: context.appSurface1,
                        width: 3,
                      ),
                    ),
                    child: CircleAvatar(
                      radius: 38,
                      backgroundColor: context.appSurface2,
                      backgroundImage:
                          photoURL != null ? NetworkImage(photoURL!) : null,
                      child: photoURL == null
                          ? Icon(
                              Icons.person_rounded,
                              size: 42,
                              color: context.appAccent,
                            )
                          : null,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    displayName,
                    style: GoogleFonts.plusJakartaSans(
                      color: context.appPrimaryColor,
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  if (email != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      email!,
                      style: TextStyle(
                        color: context.appSecondaryColor,
                        fontSize: 13,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                  if (showEdit) ...[
                    const SizedBox(height: 14),
                    GestureDetector(
                      onTap: onEditTap,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 18, vertical: 7),
                        decoration: BoxDecoration(
                          color: context.appAccent.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.edit_outlined,
                                color: context.appAccent, size: 14),
                            const SizedBox(width: 5),
                            Text(
                              editLabel,
                              style: TextStyle(
                                color: context.appAccent,
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Section header — PREFERENCES, LEGAL, ACCOUNT labels
// ─────────────────────────────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String label;
  const _SectionHeader({required this.label});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Text(
        label.toUpperCase(),
        style: GoogleFonts.inter(
          color: context.appHintColor,
          fontSize: 11,
          fontWeight: FontWeight.w600,
          letterSpacing: 1.3,
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Settings group — shared rounded container, children separated by dividers
// ─────────────────────────────────────────────────────────────────────────────

class _SettingsGroup extends StatelessWidget {
  final List<Widget> children;
  const _SettingsGroup({required this.children});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        color: context.appSurface1,
        borderRadius: BorderRadius.circular(16),
        boxShadow: isDark
            ? null
            : [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  blurRadius: 16,
                  offset: const Offset(0, 2),
                ),
              ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Column(
          children: [
            for (int i = 0; i < children.length; i++) ...[
              children[i],
              if (i < children.length - 1)
                Divider(
                  height: 1,
                  thickness: 1,
                  color: context.appDivider,
                  indent: 54,
                  endIndent: 0,
                ),
            ],
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Settings row — colored icon tile + title + optional trailing widget
// ─────────────────────────────────────────────────────────────────────────────

class _SettingsRow extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool isDestructive;
  final bool showChevron;

  const _SettingsRow({
    required this.icon,
    required this.iconColor,
    required this.title,
    this.trailing,
    this.onTap,
    this.isDestructive = false,
    this.showChevron = true,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveIconColor =
        isDestructive ? Colors.redAccent : iconColor;
    final textColor =
        isDestructive ? Colors.redAccent : context.appPrimaryColor;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
          child: Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: effectiveIconColor.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(icon, size: 18, color: effectiveIconColor),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    color: textColor,
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              if (trailing != null)
                trailing!
              else if (showChevron)
                Icon(
                  Icons.chevron_right_rounded,
                  color: context.appHintColor,
                  size: 20,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Notifications row
// ─────────────────────────────────────────────────────────────────────────────

class _NotificationsRow extends StatefulWidget {
  final String title;
  const _NotificationsRow({required this.title});

  @override
  State<_NotificationsRow> createState() => _NotificationsRowState();
}

class _NotificationsRowState extends State<_NotificationsRow> {
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
    final success =
        await UserService().updateSettings(notificationsEnabled: value);
    if (!success) {
      await _notificationService.setNotificationsEnabled(!value);
      if (!mounted) return;
      setState(() => _enabled = !value);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
              'Failed to update notification settings. Please try again.'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return _SettingsRow(
      icon: _enabled
          ? Icons.notifications_active_rounded
          : Icons.notifications_off_rounded,
      iconColor: _enabled ? const Color(0xFF6366F1) : const Color(0xFF94A3B8),
      title: widget.title,
      showChevron: false,
      onTap: () => _toggle(!_enabled),
      trailing: Switch(
        value: _enabled,
        onChanged: _toggle,
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Language row
// ─────────────────────────────────────────────────────────────────────────────

class _LanguageRow extends StatelessWidget {
  final String label;
  final String englishLabel;
  final String germanLabel;

  const _LanguageRow({
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
    return _SettingsRow(
      icon: Icons.language_rounded,
      iconColor: const Color(0xFF3B82F6),
      title: label,
      showChevron: false,
      trailing: _SegmentControl(
        options: const ['EN', 'DE'],
        tooltips: [englishLabel, germanLabel],
        selected: currentCode == 'de' ? 1 : 0,
        onSelect: (i) => _select(context, i == 0 ? 'en' : 'de'),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Theme mode row
// ─────────────────────────────────────────────────────────────────────────────

class _ThemeModeRow extends StatefulWidget {
  final AppLocalizations? l10n;
  const _ThemeModeRow({this.l10n});

  @override
  State<_ThemeModeRow> createState() => _ThemeModeRowState();
}

class _ThemeModeRowState extends State<_ThemeModeRow> {
  ThemeMode _selected = ThemeMode.system;
  static const _kThemeModeKey = 'theme_mode';

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_kThemeModeKey);
    ThemeMode mode = ThemeMode.system;
    if (raw == 'dark') mode = ThemeMode.dark;
    if (raw == 'light') mode = ThemeMode.light;
    if (mounted) setState(() => _selected = mode);
  }

  void _select(ThemeMode mode) {
    setState(() => _selected = mode);
    ConnectXApp.setThemeMode(context, mode);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = widget.l10n;
    return _SettingsRow(
      icon: Icons.contrast_rounded,
      iconColor: const Color(0xFF8B5CF6),
      title: l10n?.menuTheme ?? 'Appearance',
      showChevron: false,
      trailing: _SegmentControl(
        options: const ['', '', ''],
        icons: const [
          Icons.nights_stay_rounded,
          Icons.wb_sunny_rounded,
          Icons.phone_android_rounded,
        ],
        tooltips: [
          l10n?.themeDark ?? 'Dark',
          l10n?.themeLight ?? 'Light',
          l10n?.themeSystem ?? 'System',
        ],
        selected: _selected == ThemeMode.dark
            ? 0
            : _selected == ThemeMode.light
                ? 1
                : 2,
        onSelect: (i) => _select(
          i == 0
              ? ThemeMode.dark
              : i == 1
                  ? ThemeMode.light
                  : ThemeMode.system,
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Segment control — compact pill-style multi-option toggle
// ─────────────────────────────────────────────────────────────────────────────

class _SegmentControl extends StatelessWidget {
  final List<String> options;
  final List<String> tooltips;
  final List<IconData>? icons;
  final int selected;
  final ValueChanged<int> onSelect;

  const _SegmentControl({
    required this.options,
    required this.tooltips,
    required this.selected,
    required this.onSelect,
    this.icons,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      height: 32,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: context.appSurface2,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(options.length, (i) {
          final isSelected = selected == i;
          final icon = icons != null ? icons![i] : null;
          final label = options[i];
          return Tooltip(
            message: tooltips[i],
            child: GestureDetector(
              onTap: isSelected ? null : () => onSelect(i),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                padding: const EdgeInsets.symmetric(horizontal: 9),
                decoration: BoxDecoration(
                  color: isSelected
                      ? (isDark
                          ? const Color(0xFFF1F5F9)
                          : const Color(0xFF0F172A))
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(7),
                  boxShadow: isSelected
                      ? [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.12),
                            blurRadius: 4,
                            offset: const Offset(0, 1),
                          ),
                        ]
                      : null,
                ),
                child: Center(
                  child: icon != null
                      ? Icon(
                          icon,
                          size: 14,
                          color: isSelected
                              ? (isDark ? Colors.black87 : Colors.white)
                              : context.appSecondaryColor,
                        )
                      : Text(
                          label,
                          style: TextStyle(
                            color: isSelected
                                ? (isDark ? Colors.black87 : Colors.white)
                                : context.appSecondaryColor,
                            fontSize: 12,
                            fontWeight: isSelected
                                ? FontWeight.w700
                                : FontWeight.w500,
                          ),
                        ),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}
