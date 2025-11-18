import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../services/auth_service.dart';

// A widget that guards its child by checking if the user is authenticated.
// If not authenticated, it redirects to the /start page.
class AuthGuard extends StatelessWidget {
  final Widget child;
  final AuthService auth;

  const AuthGuard({required this.child, required this.auth});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<GoogleSignInAccount?>(
      stream: auth.onCurrentUserChanged,
      initialData: auth.currentUser,
      builder: (context, snapshot) {
        final user = snapshot.data;

        if (user == null) {
          // Redirect to /start if the user is not logged in
          WidgetsBinding.instance.addPostFrameCallback((_) {
            Navigator.of(context).pushNamedAndRemoveUntil('/start', (route) => false);
          });
          return const SizedBox(); // Return an empty widget while redirecting
        }

        // If the user is logged in, show the child widget
        return child;
      },
    );
  }
}