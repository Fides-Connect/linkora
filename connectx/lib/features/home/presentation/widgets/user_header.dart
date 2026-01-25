import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import '../../../../services/auth_service.dart';

class UserHeader extends StatelessWidget {
  final User? user;
  final AuthService auth;

  const UserHeader({
    super.key,
    required this.user,
    required this.auth,
  });

  @override
  Widget build(BuildContext context) {
    if (user == null) return const SizedBox.shrink();

    return Positioned(
      top: 20,
      right: 20,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (auth.photoUrl != null &&
              auth.photoUrl!.isNotEmpty &&
              !kIsWeb)
            ClipOval(
              child: Image.network(
                auth.photoUrl!,
                width: 32,
                height: 32,
                fit: BoxFit.cover,
              ),
            )
          else
            CircleAvatar(
              radius: 16,
              backgroundColor: const Color(0xFF6C63FF),
              child: Text(
                (user?.displayName ?? '')
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
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await auth.signOut();
            },
          ),
        ],
      ),
    );
  }
}
