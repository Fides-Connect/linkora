import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/providers/user_provider.dart';
import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../main.dart';
import '../../../../services/notification_service.dart';
import '../../../../services/user_service.dart';
import '../viewmodels/home_tab_view_model.dart';
import 'user_page.dart';

class MenuTabPage extends StatelessWidget {
  const MenuTabPage({super.key});

  void _showLanguageDialog(BuildContext context) {
    final localizations = AppLocalizations.of(context);
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text(localizations?.menuLanguage ?? 'Language'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                title: Text(localizations?.languageEnglish ?? 'English'),
                onTap: () {
                  ConnectXApp.setLocale(context, const Locale('en', ''));
                  UserService().updateSettings(language: 'en');
                  Navigator.pop(context);
                },
              ),
              ListTile(
                title: Text(localizations?.languageGerman ?? 'German'),
                onTap: () {
                  ConnectXApp.setLocale(context, const Locale('de', ''));
                  UserService().updateSettings(language: 'de');
                  Navigator.pop(context);
                },
              ),
            ],
          ),
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
                  _MenuItem(
                    icon: Icons.language,
                    title: localizations?.menuLanguage ?? 'Language',
                    onTap: () => _showLanguageDialog(context),
                  ),
                  const SizedBox(height: 16),
                  _NotificationsToggleItem(
                    title: localizations?.menuNotifications ?? 'Notifications',
                  ),
                  const SizedBox(height: 16),
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
    UserService().updateSettings(notificationsEnabled: value);
    setState(() => _enabled = value);
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
