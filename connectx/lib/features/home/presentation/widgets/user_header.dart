import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:provider/provider.dart';
import '../../../../core/providers/user_provider.dart';
import '../../../../localization/app_localizations.dart';

class UserHeader extends StatelessWidget {
  const UserHeader({super.key});

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);
    return Consumer<UserProvider>(
      builder: (context, userProvider, _) {
        final user = userProvider.user;
        if (user == null) return const SizedBox.shrink();

        Widget buildFallback() {
          return Semantics(
            label: user.displayName ?? localizations?.menuSupporterProfile ?? 'User Profile',
            child: CircleAvatar(
              radius: 16,
              backgroundColor: const Color(0xFF6C63FF),
              child: Text(
                (user.displayName ?? '')
                    .split(' ')
                    .where((s) => s.isNotEmpty)
                    .map((s) => s[0])
                    .take(2)
                    .join()
                    .toUpperCase(),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                ),
              ),
            ),
          );
        }

        return Positioned(
          top: 20,
          right: 20,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (user.photoURL != null &&
                  user.photoURL!.isNotEmpty &&
                  !kIsWeb)
                Semantics(
                  label: user.displayName ?? localizations?.menuSupporterProfile ?? 'User Profile',
                  child: ClipOval(
                    child: Image.network(
                      user.photoURL!,
                      width: 32,
                      height: 32,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) =>
                          buildFallback(),
                    ),
                  ),
                )
              else
                buildFallback(),
              IconButton(
                icon: const Icon(Icons.logout),
                tooltip: localizations?.menuLogout ?? 'Logout',
                onPressed: () async {
                  await userProvider.signOut();
                },
              ),
            ],
          ),
        );
      },
    );
  }
}
