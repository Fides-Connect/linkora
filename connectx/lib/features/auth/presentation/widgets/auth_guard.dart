import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/providers/user_provider.dart';

// A widget that guards its child by checking if the user is authenticated.
// If not authenticated, it redirects to the /start page.
class AuthGuard extends StatefulWidget {
  final Widget child;

  const AuthGuard({required this.child, super.key});

  @override
  State<AuthGuard> createState() => _AuthGuardState();
}

class _AuthGuardState extends State<AuthGuard> {
  bool _isNavigating = false;

  @override
  Widget build(BuildContext context) {
    return Consumer<UserProvider>(
      builder: (context, userProvider, _) {
        if (!userProvider.isAuthenticated && !userProvider.isLoading) {
          if (!_isNavigating) {
            _isNavigating = true;
            debugPrint('AuthGuard: No user logged in, redirecting to /start');
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) {
                Navigator.of(context).pushNamedAndRemoveUntil('/start', (route) => false);
              }
            });
          }
          return const SizedBox();
        }

        // Reset the flag if the user becomes authenticated
        if (userProvider.isAuthenticated) {
          _isNavigating = false;
        }
        
        if (userProvider.isLoading && !userProvider.isAuthenticated) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }

        return widget.child;
      },
    );
  }
}
