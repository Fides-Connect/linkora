import 'package:flutter/material.dart';

// This is a stub implementation for non-web platforms as the real
// implementation is only available on the web (package:google_sign_in_web/web_only.dart). 
// This prevents // import errors on other platforms. On Android/iOS/Desktop, we use
// the standard SignInButton from flutter_signin_button package. Basically,
// this is widget does nothing and just serves as a placeholder.
Widget renderButton({GSIButtonConfiguration? configuration}) {
  return const SizedBox.shrink();
}

// Stub Button configuration class for non-web platforms. The real
// implementation is only available on the web.
class GSIButtonConfiguration {
  GSIButtonConfiguration({
    this.theme,
  });

  final GSIButtonTheme? theme;
}

// Styles for the Google Sign-In button.
enum GSIButtonTheme {
  /// A standard button theme.
  outline,

  /// A blue-filled button theme.
  filledBlue,

  /// A black-filled button theme.
  filledBlack,
}
