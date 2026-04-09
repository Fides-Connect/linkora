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
  static const String sessionEndedBanner = 'Session ended after 10 minutes of inactivity';
  static const String newSessionButton = 'New Session';

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

  // Page content — replace the placeholder blocks with your actual text.
  static const String impressumContent = '''
Information pursuant to § 5 DDG

Thomas Bretthauer-Weber  
Schweiggerweg 20
13627 Berlin
Germany

Contact  
Email: thomas.bretthauer-weber@allinked.org

VAT ID  
Value Added Tax Identification Number pursuant to § 27a of the German Value Added Tax Act: DE460374834''';

  static const String privacyPolicyContent = '''
Last updated April 08, 2026

This Privacy Notice for the Linkora application, operated by Thomas Bretthauer‑Weber (“we,” “us,” or “our”), describes how and why we might access, collect, store, use, and/or share ("process") your personal information when you use our services ("Services"), including when you:

- Download and use our mobile application (Linkora), or any other application of ours that links to this Privacy Notice
- Use Linkora. Linkora is an AI-powered chat assistant that helps you find suitable service providers for everyday needs such as tradespeople, cleaners, tutors, or other local professionals. You describe your request in everyday language; the AI assistant, named Elin, guides you through a short conversation to understand your needs and then presents a list of matching providers sourced from Google Maps. All communication is text-based. No audio is recorded or processed. Conversation data is held in memory only for the duration of your session and is permanently discarded when the session ends. No conversation history is written to any database.
- Engage with us in other related ways, including any marketing or events

Questions or concerns? Reading this Privacy Notice will help you understand your privacy rights and choices. We are responsible for making decisions about how your personal information is processed. If you do not agree with our policies and practices, please do not use our Services. If you still have any questions or concerns, please contact us at thomas.bretthauer-weber@allinked.org.


SUMMARY OF KEY POINTS

This summary provides key points from our Privacy Notice, but you can find out more details about any of these topics in the table of contents below.

What personal information do we process? When you visit, use, or navigate our Services, we may process personal information depending on how you interact with us and the Services, the choices you make, and the products and features you use.

Do we process any sensitive personal information? We do not process sensitive personal information.

Do we collect any information from third parties? We do not collect any information from third parties.

How do we process your information? We process your information to provide, improve, and administer our Services, communicate with you, for security and fraud prevention, and to comply with law. We may also process your information for other purposes with your consent. We process your information only when we have a valid legal reason to do so.

In what situations and with which parties do we share personal information? We may share information in specific situations and with specific third parties.

How do we keep your information safe? We have adequate organizational and technical processes and procedures in place to protect your personal information. However, no electronic transmission over the internet or information storage technology can be guaranteed to be 100% secure, so we cannot promise or guarantee that hackers, cybercriminals, or other unauthorized third parties will not be able to defeat our security and improperly collect, access, steal, or modify your information.

What are your rights? Depending on where you are located geographically, the applicable privacy law may mean you have certain rights regarding your personal information.

How do you exercise your rights? The easiest way to exercise your rights is by submitting a data subject access request at https://app.termly.io/dsar/01db769c-cafd-411c-a0df-0d8b92e6b52d, or by contacting us. We will consider and act upon any request in accordance with applicable data protection laws.


TABLE OF CONTENTS

1. WHAT INFORMATION DO WE COLLECT?
2. HOW DO WE PROCESS YOUR INFORMATION?
3. WHAT LEGAL BASES DO WE RELY ON TO PROCESS YOUR PERSONAL INFORMATION?
4. WHEN AND WITH WHOM DO WE SHARE YOUR PERSONAL INFORMATION?
5. DO WE USE COOKIES AND OTHER TRACKING TECHNOLOGIES?
6. DO WE OFFER ARTIFICIAL INTELLIGENCE-BASED PRODUCTS?
7. HOW DO WE HANDLE YOUR SOCIAL LOGINS?
8. IS YOUR INFORMATION TRANSFERRED INTERNATIONALLY?
9. HOW LONG DO WE KEEP YOUR INFORMATION?
10. HOW DO WE KEEP YOUR INFORMATION SAFE?
11. DO WE COLLECT INFORMATION FROM MINORS?
12. WHAT ARE YOUR PRIVACY RIGHTS?
13. CONTROLS FOR DO-NOT-TRACK FEATURES
14. DO WE MAKE UPDATES TO THIS NOTICE?
15. HOW CAN YOU CONTACT US ABOUT THIS NOTICE?
16. HOW CAN YOU REVIEW, UPDATE, OR DELETE THE DATA WE COLLECT FROM YOU?


1. WHAT INFORMATION DO WE COLLECT?

Personal information you disclose to us

In Short: We collect personal information that you provide to us.

We collect personal information that you voluntarily provide to us when you register on the Services, express an interest in obtaining information about us or our products and Services, when you participate in activities on the Services, or otherwise when you contact us.

Personal Information Provided by You. The personal information that we collect depends on the context of your interactions with us and the Services, the choices you make, and the products and features you use. The personal information we collect may include the following:

- names
- email addresses
- usernames

Sensitive Information. We do not process sensitive information.

Social Media Login Data. We may provide you with the option to register with us using your existing social media account details, like your Facebook, X, or other social media account. If you choose to register in this way, we will collect certain profile information about you from the social media provider, as described in the section called "HOW DO WE HANDLE YOUR SOCIAL LOGINS?" below.

All personal information that you provide to us must be true, complete, and accurate, and you must notify us of any changes to such personal information.

Google API

Our use of information received from Google APIs will adhere to the Google API Services User Data Policy (https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.


2. HOW DO WE PROCESS YOUR INFORMATION?

In Short: We process your information to provide, improve, and administer our Services, communicate with you, for security and fraud prevention, and to comply with law. We may also process your information for other purposes with your consent.

We process your personal information for a variety of reasons, depending on how you interact with our Services, including:

- To facilitate account creation and authentication and otherwise manage user accounts. We may process your information so you can create and log in to your account, as well as keep your account in working order.
- To deliver and facilitate delivery of services to the user. We may process your information to provide you with the requested service.
- To respond to user inquiries/offer support to users. We may process your information to respond to your inquiries and solve any potential issues you might have with the requested service.
- To save or protect an individual's vital interest. We may process your information when necessary to save or protect an individual's vital interest, such as to prevent harm.


3. WHAT LEGAL BASES DO WE RELY ON TO PROCESS YOUR PERSONAL INFORMATION?

In Short: We only process your personal information when we believe it is necessary and we have a valid legal reason (i.e., legal basis) to do so under applicable law, like with your consent, to comply with laws, to provide you with services to enter into or fulfill our contractual obligations, to protect your rights, or to fulfill our legitimate business interests.

The General Data Protection Regulation (GDPR) and UK GDPR require us to explain the valid legal bases we rely on in order to process your personal information. As such, we may rely on the following legal bases to process your personal information:

- Consent. We may process your information if you have given us permission (i.e., consent) to use your personal information for a specific purpose. You can withdraw your consent at any time.
- Performance of a Contract. We may process your personal information when we believe it is necessary to fulfill our contractual obligations to you, including providing our Services or at your request prior to entering into a contract with you.
- Legal Obligations. We may process your information where we believe it is necessary for compliance with our legal obligations, such as to cooperate with a law enforcement body or regulatory agency, exercise or defend our legal rights, or disclose your information as evidence in litigation in which we are involved.
- Vital Interests. We may process your information where we believe it is necessary to protect your vital interests or the vital interests of a third party, such as situations involving potential threats to the safety of any person.


4. WHEN AND WITH WHOM DO WE SHARE YOUR PERSONAL INFORMATION?

In Short: We may share information in specific situations described in this section and/or with the following third parties.

We may need to share your personal information in the following situations:

- Business Transfers. We may share or transfer your information in connection with, or during negotiations of, any merger, sale of company assets, financing, or acquisition of all or a portion of our business to another company.
- When we use Google Maps Platform APIs. We may share your information with certain Google Maps Platform APIs (e.g., Google Maps API, Places API). Google Maps uses GPS, Wi-Fi, and cell towers to estimate your location. GPS is accurate to about 20 meters, while Wi-Fi and cell towers help improve accuracy when GPS signals are weak, like indoors. This data helps Google Maps provide directions, but it is not always perfectly precise.


5. DO WE USE COOKIES AND OTHER TRACKING TECHNOLOGIES?

In Short: We may use cookies and other tracking technologies to collect and store your information.

We may use cookies and similar tracking technologies (like web beacons and pixels) to gather information when you interact with our Services. Some online tracking technologies help us maintain the security of our Services and your account, prevent crashes, fix bugs, save your preferences, and assist with basic site functions.

We also permit third parties and service providers to use online tracking technologies on our Services for analytics and advertising, including to help manage and display advertisements, to tailor advertisements to your interests, or to send abandoned shopping cart reminders (depending on your communication preferences). The third parties and service providers use their technology to provide advertising about products and services tailored to your interests which may appear either on our Services or on other websites.

Specific information about how we use such technologies and how you can refuse certain cookies is set out in our Cookie Notice.


6. DO WE OFFER ARTIFICIAL INTELLIGENCE-BASED PRODUCTS?

In Short: We offer products, features, or tools powered by artificial intelligence, machine learning, or similar technologies.

As part of our Services, we offer products, features, or tools powered by artificial intelligence, machine learning, or similar technologies (collectively, "AI Products"). These tools are designed to enhance your experience and provide you with innovative solutions. The terms in this Privacy Notice govern your use of the AI Products within our Services.

Use of AI Technologies

We provide the AI Products through third-party service providers ("AI Service Providers"), including Google Cloud AI. As outlined in this Privacy Notice, your input, output, and personal information will be shared with and processed by these AI Service Providers to enable your use of our AI Products for purposes outlined in "WHAT LEGAL BASES DO WE RELY ON TO PROCESS YOUR PERSONAL INFORMATION?" You must not use the AI Products in any way that violates the terms or policies of any AI Service Provider.

Our AI Products

Our AI Products are designed for the following functions:
- AI bots

How We Process Your Data Using AI

All personal information processed using our AI Products is handled in line with our Privacy Notice and our agreement with third parties. This ensures high security and safeguards your personal information throughout the process, giving you peace of mind about your data's safety.


7. HOW DO WE HANDLE YOUR SOCIAL LOGINS?

In Short: If you choose to register or log in to our Services using a social media account, we may have access to certain information about you.

Our Services offer you the ability to register and log in using your third-party social media account details (like your Facebook or X logins). Where you choose to do this, we will receive certain profile information about you from your social media provider. The profile information we receive may vary depending on the social media provider concerned, but will often include your name, email address, friends list, and profile picture, as well as other information you choose to make public on such a social media platform.

We will use the information we receive only for the purposes that are described in this Privacy Notice or that are otherwise made clear to you on the relevant Services. Please note that we do not control, and are not responsible for, other uses of your personal information by your third-party social media provider. We recommend that you review their privacy notice to understand how they collect, use, and share your personal information, and how you can set your privacy preferences on their sites and apps.


8. IS YOUR INFORMATION TRANSFERRED INTERNATIONALLY?

In Short: We may transfer, store, and process your information in countries other than your own.

Our servers are located in the United States. Regardless of your location, please be aware that your information may be transferred to, stored by, and processed by us in our facilities and in the facilities of the third parties with whom we may share your personal information (see "WHEN AND WITH WHOM DO WE SHARE YOUR PERSONAL INFORMATION?" above), including facilities in the United States, and other countries.

If you are a resident in the European Economic Area (EEA), United Kingdom (UK), or Switzerland, then these countries may not necessarily have data protection laws or other similar laws as comprehensive as those in your country. However, we will take all necessary measures to protect your personal information in accordance with this Privacy Notice and applicable law.

European Commission's Standard Contractual Clauses:

We have implemented measures to protect your personal information, including by using the European Commission's Standard Contractual Clauses for transfers of personal information between our group companies and between us and our third-party providers. These clauses require all recipients to protect all personal information that they process originating from the EEA or UK in accordance with European data protection laws and regulations. Our Standard Contractual Clauses can be provided upon request. We have implemented similar appropriate safeguards with our third-party service providers and partners and further details can be provided upon request.


9. HOW LONG DO WE KEEP YOUR INFORMATION?

In Short: We keep your information for as long as necessary to fulfill the purposes outlined in this Privacy Notice unless otherwise required by law.

We will only keep your personal information for as long as it is necessary for the purposes set out in this Privacy Notice, unless a longer retention period is required or permitted by law (such as tax, accounting, or other legal requirements). No purpose in this notice will require us keeping your personal information for longer than the period of time in which users have an account with us.

When we have no ongoing legitimate business need to process your personal information, we will either delete or anonymize such information, or, if this is not possible (for example, because your personal information has been stored in backup archives), then we will securely store your personal information and isolate it from any further processing until deletion is possible.


10. HOW DO WE KEEP YOUR INFORMATION SAFE?

In Short: We aim to protect your personal information through a system of organizational and technical security measures.

We have implemented appropriate and reasonable technical and organizational security measures designed to protect the security of any personal information we process. However, despite our safeguards and efforts to secure your information, no electronic transmission over the Internet or information storage technology can be guaranteed to be 100% secure, so we cannot promise or guarantee that hackers, cybercriminals, or other unauthorized third parties will not be able to defeat our security and improperly collect, access, steal, or modify your information. Although we will do our best to protect your personal information, transmission of personal information to and from our Services is at your own risk. You should only access the Services within a secure environment.


11. DO WE COLLECT INFORMATION FROM MINORS?

In Short: We do not knowingly collect data from or market to children under 18 years of age.

We do not knowingly collect, solicit data from, or market to children under 18 years of age, nor do we knowingly sell such personal information. By using the Services, you represent that you are at least 18 or that you are the parent or guardian of such a minor and consent to such minor dependent's use of the Services. If we learn that personal information from users less than 18 years of age has been collected, we will deactivate the account and take reasonable measures to promptly delete such data from our records. If you become aware of any data we may have collected from children under age 18, please contact us at thomas.bretthauer-weber@allinked.org.


12. WHAT ARE YOUR PRIVACY RIGHTS?

In Short: In some regions, such as the European Economic Area (EEA), United Kingdom (UK), and Switzerland, you have rights that allow you greater access to and control over your personal information. You may review, change, or terminate your account at any time, depending on your country, province, or state of residence.

In some regions (like the EEA, UK, and Switzerland), you have certain rights under applicable data protection laws. These may include the right (i) to request access and obtain a copy of your personal information, (ii) to request rectification or erasure; (iii) to restrict the processing of your personal information; (iv) if applicable, to data portability; and (v) not to be subject to automated decision-making. In certain circumstances, you may also have the right to object to the processing of your personal information. You can make such a request by contacting us by using the contact details provided in the section "HOW CAN YOU CONTACT US ABOUT THIS NOTICE?" below.

We will consider and act upon any request in accordance with applicable data protection laws.

If you are located in the EEA or UK and you believe we are unlawfully processing your personal information, you also have the right to complain to your Member State data protection authority (https://ec.europa.eu/justice/data-protection/bodies/authorities/index_en.htm) or UK data protection authority (https://ico.org.uk/make-a-complaint/data-protection-complaints/data-protection-complaints/).

If you are located in Switzerland, you may contact the Federal Data Protection and Information Commissioner (https://www.edoeb.admin.ch/edoeb/en/home.html).

Withdrawing your consent: If we are relying on your consent to process your personal information, you have the right to withdraw your consent at any time. You can withdraw your consent at any time by contacting us by using the contact details provided in the section "HOW CAN YOU CONTACT US ABOUT THIS NOTICE?" below.

However, please note that this will not affect the lawfulness of the processing before its withdrawal nor, will it affect the processing of your personal information conducted in reliance on lawful processing grounds other than consent.

Account Information

If you would at any time like to review or change the information in your account or terminate your account, you can:
- Log in to your account settings and update your user account.

Upon your request to terminate your account, we will deactivate or delete your account and information from our active databases. However, we may retain some information in our files to prevent fraud, troubleshoot problems, assist with any investigations, enforce our legal terms and/or comply with applicable legal requirements.

If you have questions or comments about your privacy rights, you may email us at thomas.bretthauer-weber@allinked.org.


13. CONTROLS FOR DO-NOT-TRACK FEATURES

Most web browsers and some mobile operating systems and mobile applications include a Do-Not-Track ("DNT") feature or setting you can activate to signal your privacy preference not to have data about your online browsing activities monitored and collected. At this stage, no uniform technology standard for recognizing and implementing DNT signals has been finalized. As such, we do not currently respond to DNT browser signals or any other mechanism that automatically communicates your choice not to be tracked online. If a standard for online tracking is adopted that we must follow in the future, we will inform you about that practice in a revised version of this Privacy Notice.


14. DO WE MAKE UPDATES TO THIS NOTICE?

In Short: Yes, we will update this notice as necessary to stay compliant with relevant laws.

We may update this Privacy Notice from time to time. The updated version will be indicated by an updated "Revised" date at the top of this Privacy Notice. If we make material changes to this Privacy Notice, we may notify you either by prominently posting a notice of such changes or by directly sending you a notification. We encourage you to review this Privacy Notice frequently to be informed of how we are protecting your information.


15. HOW CAN YOU CONTACT US ABOUT THIS NOTICE?

If you have questions or comments about this notice, you may email us at thomas.bretthauer-weber@allinked.org or contact us by post at:

Thomas Bretthauer-Weber
Schweiggerweg 20
Berlin, Berlin 13627
Germany


16. HOW CAN YOU REVIEW, UPDATE, OR DELETE THE DATA WE COLLECT FROM YOU?

Based on the applicable laws of your country, you may have the right to request access to the personal information we collect from you, details about how we have processed it, correct inaccuracies, or delete your personal information. You may also have the right to withdraw your consent to our processing of your personal information. These rights may be limited in some circumstances by applicable law. To request to review, update, or delete your personal information, please fill out and submit a data subject access request at:
https://app.termly.io/dsar/01db769c-cafd-411c-a0df-0d8b92e6b52d

This Privacy Policy was created using Termly's Privacy Policy Generator''';

  static const String termsOfUseContent = '''
Last updated April 08, 2026

This Acceptable Use Policy (“Policy”) applies to your use of the Linkora mobile application (“Services”). By using the Services, you agree to comply with this Policy. If you do not agree, please refrain from using the Services.

Please carefully review this Policy, which applies to any and all:
(a) use of our Services
(b) forms, materials, content, and any other features available within the Services (“Content”)

WHO WE ARE
We are Thomas Bretthauer‑Weber, operating the Linkora mobile application (“Company,” “we,” “us,” or “our”). We are based in Berlin, Germany. This Policy applies to Linkora and any related features or services that refer or link to this Policy (collectively, the “Services”).

USE OF THE SERVICES
When you use the Services, you warrant that you will comply with this Policy and with all applicable laws.
You also acknowledge that you may not:
• Systematically retrieve data or other content from the Services to create or compile, directly or indirectly, a collection, compilation, database, or directory without written permission from us.
• Make any unauthorized use of the Services, including collecting usernames and/or email addresses of users by electronic or other means for the purpose of sending unsolicited email, or creating user accounts by automated means or under false pretenses.
• Circumvent, disable, or otherwise interfere with security-related features of the Services, including features that prevent or restrict the use or copying of any Content or enforce limitations on the use of the Services and/or the Content contained therein.
• Engage in unauthorized framing of or linking to the Services.
• Trick, defraud, or mislead us and other users, especially in any attempt to learn sensitive account information such as user passwords.
• Make improper use of our Services, including our support services or submit false reports of abuse or misconduct.
• Engage in any automated use of the Services, such as using scripts to send comments or messages, or using any data mining, robots, or similar data gathering and extraction tools.
• Interfere with, disrupt, or create an undue burden on the Services or the networks or the Services connected.
• Attempt to impersonate another user or person or use the username of another user.
• Use any information obtained from the Services in order to harass, abuse, or harm another person.
• Use the Services as part of any effort to compete with us or otherwise use the Services and/or the Content for any revenue-generating endeavor or commercial enterprise.
• Decipher, decompile, disassemble, or reverse engineer any of the software comprising or in any way making up a part of the Services, except as expressly permitted by applicable law.
• Attempt to bypass any measures of the Services designed to prevent or restrict access to the Services, or any portion of the Services.
• Harass, annoy, intimidate, or threaten any of our employees or agents engaged in providing any portion of the Services to you.
• Delete the copyright or other proprietary rights notice from any Content.
• Copy or adapt the Services’ software, including but not limited to Flash, PHP, HTML, JavaScript, or other code.
• Upload or transmit (or attempt to upload or to transmit) viruses, Trojan horses, or other material, including excessive use of capital letters and spamming (continuous posting of repetitive text), that interferes with any party’s uninterrupted use and enjoyment of the Services or modifies, impairs, disrupts, alters, or interferes with the use, features, functions, operation, or maintenance of the Services.
• Upload or transmit (or attempt to upload or to transmit) any material that acts as a passive or active information collection or transmission mechanism, including without limitation, clear graphics interchange formats ("gifs"), 1×1 pixels, web bugs, cookies, or other similar devices (sometimes referred to as "spyware" or "passive collection mechanisms" or "pcms").
• Except as may be the result of standard search engine or Internet browser usage, use, launch, develop, or distribute any automated system, including without limitation, any spider, robot, cheat utility, scraper, or offline reader that accesses the Services, or using or launching any unauthorized script or other software.
• Disparage, tarnish, or otherwise harm, in our opinion, us and/or the Services.
• Use the Services in a manner inconsistent with any applicable laws or regulations.

CONSEQUENCES OF BREACHING THIS POLICY
The consequences for violating our Policy will vary depending on the severity of the breach and the user's history on the Services, by way of example:
We may, in some cases, give you a warning, however, if your breach is serious or if you continue to breach our Legal Terms and this Policy, we have the right to suspend or terminate your access to and use of our Services and, if applicable, disable your account. We may also notify law enforcement or issue legal proceedings against you when we believe that there is a genuine risk to an individual or a threat to public safety. We exclude our liability for all action we may take in response to any of your breaches of this Policy.

HOW CAN YOU CONTACT US ABOUT THIS POLICY?
If you have any further questions or comments, you may contact us by: thomas.bretthauer-weber@allinked.org

This Acceptable Use Policy was created using Termly's Use Policy Generator''';

  static const String disclaimerContent = '''
Last updated April 08, 2026

The information provided for the Linkora application, operated by Thomas Bretthauer‑Weber ("we," "us," or "our"), is for general informational purposes only. All information on our mobile application is provided in good faith, however we make no representation or warranty of any kind, express or implied, regarding the accuracy, adequacy, validity, reliability, availability, or completeness of any information on our mobile application.

UNDER NO CIRCUMSTANCE SHALL WE HAVE ANY LIABILITY TO YOU FOR ANY LOSS OR DAMAGE OF ANY KIND INCURRED AS A RESULT OF THE USE OF OUR MOBILE APPLICATION OR RELIANCE ON ANY INFORMATION PROVIDED ON OUR MOBILE APPLICATION. YOUR USE OF OUR MOBILE APPLICATION AND YOUR RELIANCE ON ANY INFORMATION ON OUR MOBILE APPLICATION IS SOLELY AT YOUR OWN RISK.

This Disclaimer was created using Termly's Disclaimer Generator''';

}
