import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:intl/date_symbol_data_local.dart';
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

  String get saveButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.saveButton;
    }
    return MessagesEN.saveButton;
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

  String get typeMessageHint {
    if (locale.languageCode == 'de') {
      return MessagesDE.typeMessageHint;
    }
    return MessagesEN.typeMessageHint;
  }

  String get sessionEndedBanner {
    if (locale.languageCode == 'de') {
      return MessagesDE.sessionEndedBanner;
    }
    return MessagesEN.sessionEndedBanner;
  }

  String get newSessionButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.newSessionButton;
    }
    return MessagesEN.newSessionButton;
  }

  String get deleteAccount {
    if (locale.languageCode == 'de') {
      return MessagesDE.deleteAccount;
    }
    return MessagesEN.deleteAccount;
  }

  String get deleteAccountConfirmTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.deleteAccountConfirmTitle;
    }
    return MessagesEN.deleteAccountConfirmTitle;
  }

  String get deleteAccountConfirmMessage {
    if (locale.languageCode == 'de') {
      return MessagesDE.deleteAccountConfirmMessage;
    }
    return MessagesEN.deleteAccountConfirmMessage;
  }

  String get deleteAccountError {
    if (locale.languageCode == 'de') {
      return MessagesDE.deleteAccountError;
    }
    return MessagesEN.deleteAccountError;
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

  String get navAssistant {
    if (locale.languageCode == 'de') {
      return MessagesDE.navAssistant;
    }
    return MessagesEN.navAssistant;
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

  String get menuNotifications {
    if (locale.languageCode == 'de') {
      return MessagesDE.menuNotifications;
    }
    return MessagesEN.menuNotifications;
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

  // Theme / Appearance
  String get menuTheme {
    if (locale.languageCode == 'de') return MessagesDE.menuTheme;
    return MessagesEN.menuTheme;
  }

  String get themeDark {
    if (locale.languageCode == 'de') return MessagesDE.themeDark;
    return MessagesEN.themeDark;
  }

  String get themeLight {
    if (locale.languageCode == 'de') return MessagesDE.themeLight;
    return MessagesEN.themeLight;
  }

  String get themeSystem {
    if (locale.languageCode == 'de') return MessagesDE.themeSystem;
    return MessagesEN.themeSystem;
  }

  // Settings section headers
  String get preferencesSection {
    if (locale.languageCode == 'de') return MessagesDE.preferencesSection;
    return MessagesEN.preferencesSection;
  }

  String get legalSection {
    if (locale.languageCode == 'de') return MessagesDE.legalSection;
    return MessagesEN.legalSection;
  }

  String get accountSection {
    if (locale.languageCode == 'de') return MessagesDE.accountSection;
    return MessagesEN.accountSection;
  }

  String get editProfile {
    if (locale.languageCode == 'de') return MessagesDE.editProfile;
    return MessagesEN.editProfile;
  }

  // Profile
  String get menuUser {
    if (locale.languageCode == 'de') {
      return MessagesDE.menuProfile;
    }
    return MessagesEN.menuProfile;
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

  String get requestServiceButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.requestServiceButton;
    }
    return MessagesEN.requestServiceButton;
  }

  String get featureNotAvailable {
    if (locale.languageCode == 'de') {
      return MessagesDE.featureNotAvailable;
    }
    return MessagesEN.featureNotAvailable;
  }

  // Requests
  String get incomingRequestsTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.incomingRequestsTitle;
    }
    return MessagesEN.incomingRequestsTitle;
  }

  String get yourLastRequestsTitle {
    if (locale.languageCode == 'de') {
      return MessagesDE.yourLastRequestsTitle;
    }
    return MessagesEN.yourLastRequestsTitle;
  }

  String get openDetailsButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.openDetailsButton;
    }
    return MessagesEN.openDetailsButton;
  }

  String get actionNeededButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.actionRequired;
    }
    return MessagesEN.actionRequired;
  }

  String get pending {
    if (locale.languageCode == 'de') {
      return MessagesDE.pending;
    }
    return MessagesEN.pending;
  }

  String get waitingForAnswer {
    if (locale.languageCode == 'de') {
      return MessagesDE.waitingForAnswer;
    }
    return MessagesEN.waitingForAnswer;
  }

  String get completed {
    if (locale.languageCode == 'de') {
      return MessagesDE.completed;
    }
    return MessagesEN.completed;
  }

  String get accepted {
    if (locale.languageCode == 'de') {
      return MessagesDE.accepted;
    }
    return MessagesEN.accepted;
  }

  String get rejected {
    if (locale.languageCode == 'de') {
      return MessagesDE.rejected;
    }
    return MessagesEN.rejected;
  }

  String get unknown {
    if (locale.languageCode == 'de') {
      return MessagesDE.unknown;
    }
    return MessagesEN.unknown;
  }

  String get acceptButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.acceptButton;
    }
    return MessagesEN.acceptButton;
  }

  String get rejectButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.rejectButton;
    }
    return MessagesEN.rejectButton;
  }

  String get cancelRequestButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.cancelRequestButton;
    }
    return MessagesEN.cancelRequestButton;
  }

  String get serviceProvided {
    if (locale.languageCode == 'de') {
      return MessagesDE.serviceProvided;
    }
    return MessagesEN.serviceProvided;
  }


  String get cancelled {
    if (locale.languageCode == 'de') {
      return MessagesDE.cancelled;
    }
    return MessagesEN.cancelled;
  }

  String get markServiceProvidedButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.markServiceProvidedButton;
    }
    return MessagesEN.markServiceProvidedButton;
  }

  String get paymentButton {
    if (locale.languageCode == 'de') {
      return MessagesDE.paymentButton;
    }
    return MessagesEN.paymentButton;
  }

  String get location {
    if (locale.languageCode == 'de') {
      return MessagesDE.location;
    }
    return MessagesEN.location;
  }
  
  String get dateFrom {
    if (locale.languageCode == 'de') {
      return MessagesDE.dateFrom;
    }
    return MessagesEN.dateFrom;
  }
  
  String get dateTo {
    if (locale.languageCode == 'de') {
      return MessagesDE.dateTo;
    }
    return MessagesEN.dateTo;
  }

  String get date {
    if (locale.languageCode == 'de') {
      return MessagesDE.date;
    }
    return MessagesEN.date;
  }

  String get amount {
    if (locale.languageCode == 'de') {
      return MessagesDE.amount;
    }
    return MessagesEN.amount;
  }

  String get description {
    if (locale.languageCode == 'de') {
      return MessagesDE.description;
    }
    return MessagesEN.description;
  }

  String get requester {
    if (locale.languageCode == 'de') {
      return MessagesDE.requester;
    }
    return MessagesEN.requester;
  }

  String get provider {
    if (locale.languageCode == 'de') {
      return MessagesDE.provider;
    }
    return MessagesEN.provider;
  }

  String get addToFavorites {
    if (locale.languageCode == 'de') {
      return MessagesDE.addToFavorites;
    }
    return MessagesEN.addToFavorites;
  }

  // ── Legal pages ──────────────────────────────────────────────────────────────
  String get menuImpressum {
    if (locale.languageCode == 'de') return MessagesDE.menuImpressum;
    return MessagesEN.menuImpressum;
  }

  String get menuPrivacyPolicy {
    if (locale.languageCode == 'de') return MessagesDE.menuPrivacyPolicy;
    return MessagesEN.menuPrivacyPolicy;
  }

  String get menuTermsOfUse {
    if (locale.languageCode == 'de') return MessagesDE.menuTermsOfUse;
    return MessagesEN.menuTermsOfUse;
  }

  String get menuDisclaimer {
    if (locale.languageCode == 'de') return MessagesDE.menuDisclaimer;
    return MessagesEN.menuDisclaimer;
  }

  String get menuLicenses {
    if (locale.languageCode == 'de') return MessagesDE.menuLicenses;
    return MessagesEN.menuLicenses;
  }

  // Info / About page
  String get menuInfo {
    if (locale.languageCode == 'de') return MessagesDE.menuInfo;
    return MessagesEN.menuInfo;
  }

  String get infoVersion {
    if (locale.languageCode == 'de') return MessagesDE.infoVersion;
    return MessagesEN.infoVersion;
  }

  String get infoBuild {
    if (locale.languageCode == 'de') return MessagesDE.infoBuild;
    return MessagesEN.infoBuild;
  }

  String get infoCreditsTitle {
    if (locale.languageCode == 'de') return MessagesDE.infoCreditsTitle;
    return MessagesEN.infoCreditsTitle;
  }

  String get infoLinksTitle {
    if (locale.languageCode == 'de') return MessagesDE.infoLinksTitle;
    return MessagesEN.infoLinksTitle;
  }

  String get infoGithubLabel {
    if (locale.languageCode == 'de') return MessagesDE.infoGithubLabel;
    return MessagesEN.infoGithubLabel;
  }

  String get impressumTitle {
    if (locale.languageCode == 'de') return MessagesDE.impressumTitle;
    return MessagesEN.impressumTitle;
  }

  String get impressumContent {
    if (locale.languageCode == 'de') return MessagesDE.impressumContent;
    return MessagesEN.impressumContent;
  }

  String get privacyPolicyTitle {
    if (locale.languageCode == 'de') return MessagesDE.privacyPolicyTitle;
    return MessagesEN.privacyPolicyTitle;
  }

  String get privacyPolicyContent {
    if (locale.languageCode == 'de') return MessagesEN.privacyPolicyContent;
    return MessagesEN.privacyPolicyContent;
  }

  String get termsOfUseTitle {
    if (locale.languageCode == 'de') return MessagesDE.termsOfUseTitle;
    return MessagesEN.termsOfUseTitle;
  }

  String get termsOfUseContent {
    if (locale.languageCode == 'de') return MessagesEN.termsOfUseContent;
    return MessagesEN.termsOfUseContent;
  }

  String get disclaimerTitle {
    if (locale.languageCode == 'de') return MessagesDE.disclaimerTitle;
    return MessagesEN.disclaimerTitle;
  }

  String get disclaimerContent {
    if (locale.languageCode == 'de') return MessagesEN.disclaimerContent;
    return MessagesEN.disclaimerContent;
  }

  String get licensesTitle {
    if (locale.languageCode == 'de') return MessagesDE.licensesTitle;
    return MessagesEN.licensesTitle;
  }

  /// Returns a map of English label key → localized label for all AI processing
  /// status messages shown under the "..." animation.  The ViewModel uses this
  /// to translate both client-generated runtime state labels and server-sent
  /// tool-status strings without requiring a Flutter BuildContext.
  Map<String, String> get aiStatusLabels {
    if (locale.languageCode == 'de') {
      return {
        MessagesEN.aiStatusThinking: MessagesDE.aiStatusThinking,
        MessagesEN.aiStatusComposing: MessagesDE.aiStatusComposing,
        MessagesEN.aiStatusWorking: MessagesDE.aiStatusWorking,
        MessagesEN.aiStatusSearchingProviders: MessagesDE.aiStatusSearchingProviders,
        MessagesEN.aiStatusLoadingFavorites: MessagesDE.aiStatusLoadingFavorites,
        MessagesEN.aiStatusLoadingRequests: MessagesDE.aiStatusLoadingRequests,
        MessagesEN.aiStatusSubmittingRequest: MessagesDE.aiStatusSubmittingRequest,
        MessagesEN.aiStatusCancellingRequest: MessagesDE.aiStatusCancellingRequest,
        MessagesEN.aiStatusSavingPreferences: MessagesDE.aiStatusSavingPreferences,
        MessagesEN.aiStatusLoadingSkills: MessagesDE.aiStatusLoadingSkills,
        MessagesEN.aiStatusSavingSkills: MessagesDE.aiStatusSavingSkills,
        MessagesEN.aiStatusRemovingSkills: MessagesDE.aiStatusRemovingSkills,
        MessagesEN.aiStatusConfirmingChoice: MessagesDE.aiStatusConfirmingChoice,
        MessagesEN.aiStatusFindingNextMatch: MessagesDE.aiStatusFindingNextMatch,
        MessagesEN.aiStatusCancellingSearch: MessagesDE.aiStatusCancellingSearch,
        MessagesEN.aiStatusSearchingAgain: MessagesDE.aiStatusSearchingAgain,
        MessagesEN.aiStatusPreparingContact: MessagesDE.aiStatusPreparingContact,
        MessagesEN.aiStatusFindingMoreResults: MessagesDE.aiStatusFindingMoreResults,
      };
    }
    return {};
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
    final String localeName = locale.countryCode == null || locale.countryCode!.isEmpty
        ? locale.languageCode
        : locale.toString();
    
    // Initialize date formatting for the active locale
    await initializeDateFormatting(localeName);
    
    // Set the default locale for Intl (DateFormat uses this by default)
    Intl.defaultLocale = localeName;
    
    return AppLocalizations(locale);
  }

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
