/// English localization messages for ConnectX app
class MessagesEN {
  // Microphone permission messages
  static const String microphonePermissionTitle = 'Microphone Permission Required';
  static const String microphonePermissionMessage =
      'Microphone access is required to enable speech communication with the AI assistant. Please allow microphone access.';
  static const String microphoneAccessDeniedTitle = 'Microphone Access Denied';
  static const String microphoneAccessDeniedMessage =
      'Speech features will not be available without microphone permission.';

  // Notification permission messages
  static const String notificationPermissionTitle = 'Notification Permission Required';
  static const String notificationPermissionMessage =
      'Notifications are required to keep you up-to-date about service request status or new service requests. Please allow notifications.';
  static const String notificationAccessDeniedTitle = 'Notifications Denied';
  static const String notificationAccessDeniedMessage =
      'You will not receive notifications about service requests without this permission.';

  // Common button labels
  static const String okButton = 'OK';
  static const String requestServiceButton = 'Request Service';
  static const String featureNotAvailable = 'This feature is not available yet';
  
  // Requests
  static const String incomingRequestsTitle = 'Incoming Requests';
  static const String yourLastRequestsTitle = 'Your Last Requests';
  static const String openDetailsButton = 'Open Details';
  static const String actionRequired = 'Action Required';
  static const String pending = 'Pending';
  static const String waitingForAnswer = 'Waiting for Answer';
  static const String completed = 'Completed';
  static const String accepted = 'Accepted';
  static const String rejected = 'Rejected';
  static const String unknown = 'Unknown';
  static const String acceptButton = 'Accept';
  static const String rejectButton = 'Reject';
  static const String cancelRequestButton = 'Cancel Request';
  static const String serviceProvided = 'Service Provided';

  static const String cancelled = 'Cancelled';
  static const String markServiceProvidedButton = 'Mark Service as Provided';
  static const String paymentButton = 'Pay';
  static const String location = 'Location';
  static const String dateFrom = 'From';
  static const String dateTo = 'To';
  static const String date = 'Date';
  static const String amount = 'Amount';
  static const String description = 'Description';
  static const String requester = 'Requester';
  static const String provider = 'Provider';
  
  static const String saveButton = 'Save';

  static const String addToFavorites = 'Add to Favorites';
  static const String removeFromFavorites = 'Remove from Favorites';

  static const String cancelButton = 'Cancel';
  static const String allowButton = 'Allow';
  static const String denyButton = 'Deny';

  // Start page messages
  static const String welcomeTitle = 'Welcome to Linkora';
  static const String welcomeMessage = 'Sign in to start communicating with Elin and searching for services';
  static const String signInButton = 'Sign in with Google';
  static const String selectLanguage = 'Select Language';

  // Main page messages
  static const String tapMicrophoneToStart = 'Tap the microphone to start speaking';
  static const String typeMessageHint = 'Type a message...';
  static const String connecting = 'Connecting to Elin...';
  static const String connected = 'Connected! Elin is listening and responding...';
  static const String disconnected = 'Disconnected';
  static const String connectionClosed = 'Connection closed';

  // Connection status dialog messages
  static const String connectionEstablishedTitle = 'Connection Established';
  static const String connectionEstablishedMessage = 'Successfully connected to Elin. You can now speak.';
  static const String connectionLostTitle = 'Connection Closed';
  static const String connectionLostMessage = 'The connection to Elin has been closed.';
  static const String errorTitle = 'Error';
  static const String errorOccurred = 'An error occurred while connecting to Elin.';

  // Navigation Bar
  static const String navHome = 'Home';
  static const String navAssistant = 'Assistant';
  static const String navFavorites = 'Favorites';
  static const String navMenu = 'Menu';

  // Placeholder pages
  static const String homeScreenEmpty = 'Home Screen (Empty)';
  static const String favoritesScreenEmpty = 'Favorites Screen (Empty)';
  static const String menuScreenEmpty = 'Menu Screen (Empty)';

  // Menu items
  static const String menuLogout = 'Logout';
  static const String menuLanguage = 'Language';
  static const String menuNotifications = 'Notifications';
  static const String languageEnglish = 'English';
  static const String languageGerman = 'German';

  // Theme / Appearance
  static const String menuTheme = 'Appearance';
  static const String themeDark = 'Dark';
  static const String themeLight = 'Light';
  static const String themeSystem = 'System';

  // Settings section headers
  static const String preferencesSection = 'Preferences';
  static const String legalSection = 'Legal';
  static const String accountSection = 'Account';
  static const String editProfile = 'Edit Profile';

  // Profile
  static const String menuProfile = 'Profile';
  static const String competenciesTitle = 'Competencies';
  static const String addCompetence = 'Add Competence';
  static const String enterCompetence = 'Enter competence';
  static const String delete = 'Delete';

  // Self Introduction
  static const String selfIntroductionTitle = 'Self Introduction';
  static const String editIntroduction = 'Edit Introduction';
  static const String enterIntroduction = 'Enter your introduction';

  // Feedback
  static const String feedbackTitle = 'Feedback';
  static const String averageRating = 'Average Rating';
  static const String positiveFeedback = 'Positive Feedback';
  static const String negativeFeedback = 'Negative Feedback';

  // Delete account
  static const String deleteAccount = 'Delete Account';
  static const String deleteAccountConfirmTitle = 'Delete Account';
  static const String deleteAccountConfirmMessage = 'Are you sure you want to permanently delete your account? This action cannot be undone.';
  static const String deleteAccountError = 'Failed to delete account. Please sign in again and retry.';

  // Session ended banner
  static const String sessionEndedBanner = 'Session ended due to inactivity';
  static const String newSessionButton = 'New Session';

  // Reconnecting banner (shown when connection dropped while app was in background)
  static const String reconnectingBanner = 'Reconnecting to Elin...';
  static const String reconnectedBanner = 'Reconnected — you can continue the conversation';

  // AI processing status labels — shown under the "..." animation while the assistant works.
  // Client-generated (runtime state):
  static const String aiStatusThinking = 'Thinking...';
  static const String aiStatusComposing = 'Composing response...';
  static const String aiStatusWorking = 'Working...';
  // Server-sent tool status labels (must exactly match _TOOL_STATUS_LABELS in response_orchestrator.py):
  static const String aiStatusSearchingProviders = 'Searching for providers';
  static const String aiStatusLoadingFavorites = 'Loading your favorites';
  static const String aiStatusLoadingRequests = 'Loading your requests';
  static const String aiStatusSubmittingRequest = 'Submitting your request';
  static const String aiStatusCancellingRequest = 'Cancelling your request';
  static const String aiStatusSavingPreferences = 'Saving your preferences';
  static const String aiStatusLoadingSkills = 'Loading your skills';
  static const String aiStatusSavingSkills = 'Saving your skills';
  static const String aiStatusRemovingSkills = 'Removing skills';
  static const String aiStatusConfirmingChoice = 'Confirming your choice';
  static const String aiStatusFindingNextMatch = 'Finding the next match';
  static const String aiStatusCancellingSearch = 'Cancelling search';
  static const String aiStatusSearchingAgain = 'Searching again';
  static const String aiStatusPreparingContact = 'Preparing contact details';
  static const String aiStatusFindingMoreResults = 'Finding more results';

  // ── Provider results note ─────────────────────────────────────────────────────
  static const String providerCardNoteTitle = 'How to contact providers';
  static const String providerCardNoteBody =
      'Tap "Send request" to email your full request details directly to the provider. '
      'Note: email addresses are not always found automatically. In that case the mail will be generated without a recipient address and you can fill it in manually.';

  // ── Legal pages ──────────────────────────────────────────────────────────────
  // Menu entry labels
  static const String menuImpressum = 'Legal Notice';
  static const String menuPrivacyPolicy = 'Privacy Policy';
  static const String menuTermsOfUse = 'Terms of Use';
  static const String menuDisclaimer = 'Disclaimer';
  static const String menuLicenses = 'Licenses';

  // Info / About page
  static const String menuInfo = 'About';
  static const String infoVersion = 'Version';
  static const String infoBuild = 'Build';
  static const String infoCreditsTitle = 'Credits';
  static const String infoLinksTitle = 'Links';
  static const String infoGithubLabel = 'GitHub Project';

  // Page titles
  static const String impressumTitle = 'Legal Notice';
  static const String privacyPolicyTitle = 'Privacy Policy';
  static const String termsOfUseTitle = 'Terms of Use';
  static const String disclaimerTitle = 'Disclaimer';
  static const String licensesTitle = 'Licenses';

}
