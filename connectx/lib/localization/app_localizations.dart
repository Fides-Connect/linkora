import 'package:flutter/material.dart';
import 'messages_de.dart';
import 'messages_en.dart';

/// App localization manager
class AppLocalizations {
  final Locale locale;

  AppLocalizations(this.locale);

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  // Microphone permission messages
  String get microphonePermissionTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.microphonePermissionTitle;
    }
    return MessagesEN.microphonePermissionTitle;
  }

  String get microphonePermissionMessage {
    if (locale.languageCode == 'de') {
      return MessagesDE.microphonePermissionMessage;
    }
    return MessagesEN.microphonePermissionMessage;
  }

  String get microphoneAccessDeniedTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.microphoneAccessDeniedTitle;
    }
    return MessagesEN.microphoneAccessDeniedTitle;
  }

  String get microphoneAccessDeniedMessage {
    if (locale.languageCode == 'de') {
      return MessagesDE.microphoneAccessDeniedMessage;
    }
    return MessagesEN.microphoneAccessDeniedMessage;
  }

  // Notification permission messages
  String get notificationPermissionTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.notificationPermissionTitle;
    }
    return MessagesEN.notificationPermissionTitle;
  }

  String get notificationPermissionMessage {
    if (locale.languageCode == 'de') {
      return MessagesDE.notificationPermissionMessage;
    }
    return MessagesEN.notificationPermissionMessage;
  }

  String get notificationAccessDeniedTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.notificationAccessDeniedTitle;
    }
    return MessagesEN.notificationAccessDeniedTitle;
  }

  String get notificationAccessDeniedMessage {
    if (locale.languageCode == 'de') {
      return MessagesDE.notificationAccessDeniedMessage;
    }
    return MessagesEN.notificationAccessDeniedMessage;
  }

  // Common button labels
  String get okButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.okButton;
    }
    return MessagesEN.okButton;
  }

  String get cancelButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.cancelButton;
    }
    return MessagesEN.cancelButton;
  }

  String get allowButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.allowButton;
    }
    return MessagesEN.allowButton;
  }

  String get denyButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.denyButton;
    }
    return MessagesEN.denyButton;
  }

  // Start page messages
  String get welcomeTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.welcomeTitle;
    }
    return MessagesEN.welcomeTitle;
  }

  String get welcomeMessage {
    if (locale.languageCode == 'de') {
      return MessagesDE.welcomeMessage;
    }
    return MessagesEN.welcomeMessage;
  }

  String get signInButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.signInButton;
    }
    return MessagesEN.signInButton;
  }

  String get selectLanguage {
    if (locale.languageCode == 'de') {
      return MessagesDE.selectLanguage;
    }
    return MessagesEN.selectLanguage;
  }

  // Main page messages
  String get tapMicrophoneToStart {
    if (locale.languageCode == 'de') {
      return MessagesDE.tapMicrophoneToStart;
    }
    return MessagesEN.tapMicrophoneToStart;
  }

  String get connecting {
    if (locale.languageCode == 'de') {
      return MessagesDE.connecting;
    }
    return MessagesEN.connecting;
  }

  String get connected {
    if (locale.languageCode == 'de') {
      return MessagesDE.connected;
    }
    return MessagesEN.connected;
  }

  String get disconnected {
    if (locale.languageCode == 'de') {
      return MessagesDE.disconnected;
    }
    return MessagesEN.disconnected;
  }

  String get connectionClosed {
    if (locale.languageCode == 'de') {
      return MessagesDE.connectionClosed;
    }
    return MessagesEN.connectionClosed;
  }

  String get connectionEstablishedTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.connectionEstablishedTitle;
    }
    return MessagesEN.connectionEstablishedTitle;
  }

  String get connectionEstablishedMessage {
    if (locale.languageCode == 'de') {
      return MessagesDE.connectionEstablishedMessage;
    }
    return MessagesEN.connectionEstablishedMessage;
  }

  String get connectionLostTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.connectionLostTitle;
    }
    return MessagesEN.connectionLostTitle;
  }

  String get connectionLostMessage {
    if (locale.languageCode == 'de') {
      return MessagesDE.connectionLostMessage;
    }
    return MessagesEN.connectionLostMessage;
  }

  String get errorTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.errorTitle;
    }
    return MessagesEN.errorTitle;
  }

  String get errorOccurred {
    if (locale.languageCode == 'de') {
      return MessagesDE.errorOccurred;
    }
    return MessagesEN.errorOccurred;
  }

  // Navigation Bar
  String get navHome {
    if (locale.languageCode == 'de') {
      return MessagesDE.navHome;
    }
    return MessagesEN.navHome;
  }

  String get navSearch {
    if (locale.languageCode == 'de') {
      return MessagesDE.navSearch;
    }
    return MessagesEN.navSearch;
  }

  String get navFavorites {
    if (locale.languageCode == 'de') {
      return MessagesDE.navFavorites;
    }
    return MessagesEN.navFavorites;
  }

  String get navMenu {
    if (locale.languageCode == 'de') {
      return MessagesDE.navMenu;
    }
    return MessagesEN.navMenu;
  }

  // Placeholder pages
  String get homeScreenEmpty {
    if (locale.languageCode == 'de') {
      return MessagesDE.homeScreenEmpty;
    }
    return MessagesEN.homeScreenEmpty;
  }

  String get favoritesScreenEmpty {
    if (locale.languageCode == 'de') {
      return MessagesDE.favoritesScreenEmpty;
    }
    return MessagesEN.favoritesScreenEmpty;
  }

  String get menuScreenEmpty {
    if (locale.languageCode == 'de') {
      return MessagesDE.menuScreenEmpty;
    }
    return MessagesEN.menuScreenEmpty;
  }

  // Menu items
  String get menuLogout {
    if (locale.languageCode == 'de') {
      return MessagesDE.menuLogout;
    }
    return MessagesEN.menuLogout;
  }

  String get menuLanguage {
    if (locale.languageCode == 'de') {
      return MessagesDE.menuLanguage;
    }
    return MessagesEN.menuLanguage;
  }

  String get languageEnglish {
    if (locale.languageCode == 'de') {
      return MessagesDE.languageEnglish;
    }
    return MessagesEN.languageEnglish;
  }

  String get languageGerman {
    if (locale.languageCode == 'de') {
      return MessagesDE.languageGerman;
    }
    return MessagesEN.languageGerman;
  }

  // Supporter Profile
  String get menuSupporterProfile {
    if (locale.languageCode == 'de') {
      return MessagesDE.menuSupporterProfile;
    }
    return MessagesEN.menuSupporterProfile;
  }

  String get competenciesTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.competenciesTitle;
    }
    return MessagesEN.competenciesTitle;
  }

  String get addCompetence {
    if (locale.languageCode == 'de') {
      return MessagesDE.addCompetence;
    }
    return MessagesEN.addCompetence;
  }

  String get enterCompetence {
    if (locale.languageCode == 'de') {
      return MessagesDE.enterCompetence;
    }
    return MessagesEN.enterCompetence;
  }

  String get delete {
    if (locale.languageCode == 'de') {
      return MessagesDE.delete;
    }
    return MessagesEN.delete;
  }

  // Self Introduction
  String get selfIntroductionTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.selfIntroductionTitle;
    }
    return MessagesEN.selfIntroductionTitle;
  }

  String get editIntroduction {
    if (locale.languageCode == 'de') {
      return MessagesDE.editIntroduction;
    }
    return MessagesEN.editIntroduction;
  }

  String get enterIntroduction {
    if (locale.languageCode == 'de') {
      return MessagesDE.enterIntroduction;
    }
    return MessagesEN.enterIntroduction;
  }

  // Feedback
  String get feedbackTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.feedbackTitle;
    }
    return MessagesEN.feedbackTitle;
  }

  String get averageRating {
    if (locale.languageCode == 'de') {
      return MessagesDE.averageRating;
    }
    return MessagesEN.averageRating;
  }

  String get positiveFeedback {
    if (locale.languageCode == 'de') {
      return MessagesDE.positiveFeedback;
    }
    return MessagesEN.positiveFeedback;
  }

  String get negativeFeedback {
    if (locale.languageCode == 'de') {
      return MessagesDE.negativeFeedback;
    }
    return MessagesEN.negativeFeedback;
  }

  String get removeFromFavorites {
    if (locale.languageCode == 'de') {
      return MessagesDE.removeFromFavorites;
    }
    return MessagesEN.removeFromFavorites;
  }
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) {
    return ['en', 'de'].contains(locale.languageCode);
  }

  @override
  Future<AppLocalizations> load(Locale locale) async {
    return AppLocalizations(locale);
  }

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
