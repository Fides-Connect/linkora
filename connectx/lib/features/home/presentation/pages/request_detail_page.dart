import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/theme/app_theme_colors.dart';
import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../models/service_request.dart';
import '../../../../utils/service_request_extensions.dart';
import '../viewmodels/home_tab_view_model.dart';
import 'user_detail_page.dart';

class RequestDetailPage extends StatefulWidget {
  final ServiceRequest request;

  const RequestDetailPage({super.key, required this.request});

  @override
  State<RequestDetailPage> createState() => _RequestDetailPageState();
}

class _RequestDetailPageState extends State<RequestDetailPage> {
  // Tracks which status transition is in-flight. Non-null while the backend
  // call is pending — disables all buttons and shows a spinner on the
  // button that was pressed.
  RequestStatus? _pendingStatus;

  @override
  Widget build(BuildContext context) {
    final request = widget.request;
    final localizations = AppLocalizations.of(context);
    // Watch the ViewModel so this page rebuilds whenever [_reloadRequests]
    // fires (triggered by the Firestore real-time listener).
    // Fall back to the constructor argument if the request is not in the lists.
    final viewModel = context.watch<HomeTabViewModel>();
    final liveRequest =
        viewModel.findRequest(request.serviceRequestId) ?? request;

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Text(liveRequest.title, style: TextStyle(color: context.appPrimaryColor)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: context.appPrimaryColor),
      ),
      body: Stack(
        children: [
          const AppBackground(),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header Card
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: context.appSurface1,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Column(
                      children: [
                        CircleAvatar(
                          radius: 30,
                          backgroundColor: Colors.blue,
                          child: Icon(
                            liveRequest.icon,
                            color: Colors.white,
                            size: 30,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          liveRequest.title,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: context.appPrimaryColor,
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Builder(
                          builder: (context) {
                            final currentUserId = viewModel.user?.id ?? '';
                            final amount = liveRequest.getAmount(currentUserId);
                            return Text(
                              amount,
                              style: TextStyle(
                                color: amount.startsWith('+')
                                    ? Colors.greenAccent
                                    : context.appPrimaryColor,
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                              ),
                            );
                          },
                        ),
                        const SizedBox(height: 16),
                        // Status
                        _buildStatusChip(context, liveRequest,
                            isIncoming: liveRequest.getType(
                                    viewModel.user?.id ?? '') ==
                                RequestType.incoming),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // User Info
                  InkWell(
                    onTap: () async {
                      // Show loading indicator
                      showDialog(
                        context: context,
                        barrierDismissible: false,
                        builder: (context) =>
                            const Center(child: CircularProgressIndicator()),
                      );

                      try {
                        // Get the other user's ID based on request type
                        final currentUserId = viewModel.user?.id ?? '';
                        final requestType = liveRequest.getType(currentUserId);

                        String otherUserId;
                        if (requestType == RequestType.incoming) {
                          otherUserId = liveRequest.seekerUserId;
                        } else if (requestType == RequestType.outgoing) {
                          otherUserId = liveRequest.selectedProviderUserId;
                        } else {
                          // Handle unknown request type (e.g. ID mismatch)
                          if (context.mounted) {
                            Navigator.pop(context); // Close loading
                          }
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                  localizations?.errorOccurred ??
                                      'Unknown request type',
                                ),
                              ),
                            );
                          }
                          return;
                        }

                        if (otherUserId.isEmpty) {
                          if (context.mounted) {
                            Navigator.pop(context); // Close loading
                          }
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                  localizations?.featureNotAvailable ??
                                      'User not found',
                                ),
                              ),
                            );
                          }
                          return;
                        }

                        final user = await viewModel.getOtherUser(otherUserId);

                        // Close loading indicator
                        if (context.mounted) Navigator.pop(context);

                        if (user != null && context.mounted) {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => ChangeNotifierProvider.value(
                                value: viewModel,
                                child: UserDetailPage(user: user),
                              ),
                            ),
                          );
                        } else if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                localizations?.featureNotAvailable ??
                                    'User not found',
                              ),
                            ),
                          );
                        }
                      } catch (e) {
                        // Close loading indicator
                        if (context.mounted) Navigator.pop(context);
                        if (context.mounted) {
                          ScaffoldMessenger.of(
                            context,
                          ).showSnackBar(SnackBar(content: Text('Error: $e')));
                        }
                      }
                    },
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        vertical: 8.0,
                        horizontal: 4.0,
                      ),
                      child: Row(
                        children: [
                          CircleAvatar(
                            radius: 25,
                            backgroundColor: context.appSurface3,
                            child: Builder(
                              builder: (context) {
                                final currentUserId =
                                    viewModel.user?.id ?? '';
                                final isIncoming =
                                    liveRequest.getType(currentUserId) ==
                                    RequestType.incoming;
                                return Text(
                                  isIncoming
                                      ? liveRequest.seekerUserInitials
                                      : liveRequest.selectedProviderUserInitials,
                                  style: TextStyle(
                                    color: context.appPrimaryColor,
                                    fontWeight: FontWeight.bold,
                                  ),
                                );
                              },
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Builder(
                              builder: (context) {
                                final currentUserId =
                                    viewModel.user?.id ?? '';
                                final isIncoming =
                                    liveRequest.getType(currentUserId) ==
                                    RequestType.incoming;
                                return Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      isIncoming
                                          ? liveRequest.seekerUserName
                                          : liveRequest.selectedProviderUserName,
                                      style: TextStyle(
                                        color: context.appPrimaryColor,
                                        fontSize: 18,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    Text(
                                      isIncoming
                                          ? (localizations?.requester ??
                                                'Requester')
                                          : (localizations?.provider ??
                                                'Provider'),
                                      style: TextStyle(
                                        color: context.appSecondaryColor,
                                      ),
                                    ),
                                  ],
                                );
                              },
                            ),
                          ),
                          const Icon(
                            Icons.arrow_forward_ios,
                            color: Colors.grey,
                            size: 16,
                          ),
                        ],
                      ),
                    ),
                  ),

                  Divider(color: context.appDivider, height: 32),

                  // Details
                  _buildDetailRow(
                    context,
                    localizations?.date ?? 'Date',
                    liveRequest.getDate(localizations),
                  ),
                  if (liveRequest.getSecondDateLine(localizations) != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4.0),
                      child: _buildDetailRow(
                        context,
                        '',
                        liveRequest.getSecondDateLine(localizations)!,
                      ),
                    ),

                  const SizedBox(height: 16),
                  _buildDetailRow(
                    context,
                    localizations?.location ?? 'Location',
                    liveRequest.location,
                  ),

                  Divider(color: context.appDivider, height: 32),

                  // Description
                  Text(
                    localizations?.description ?? 'Description',
                    style: TextStyle(
                      color: context.appPrimaryColor,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    liveRequest.description,
                    style: TextStyle(
                      color: context.appSecondaryColor,
                      fontSize: 16,
                      height: 1.5,
                    ),
                  ),

                  const SizedBox(height: 48),

                  // Actions
                  Builder(
                    builder: (context) {
                      final currentUserId = viewModel.user?.id ?? '';
                      final requestType = liveRequest.getType(currentUserId);

                      Future<void> doUpdate(RequestStatus newStatus) async {
                        setState(() => _pendingStatus = newStatus);
                        try {
                          await viewModel.updateServiceRequestStatus(
                            liveRequest,
                            newStatus,
                          );
                        } catch (e) {
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text('Error: $e')),
                            );
                          }
                        } finally {
                          if (mounted) setState(() => _pendingStatus = null);
                        }
                      }

                      // Returns a spinner for the in-flight button, plain
                      // text otherwise.
                      Widget buttonChild(RequestStatus forStatus, String label) {
                        if (_pendingStatus == forStatus) {
                          return const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          );
                        }
                        return Text(
                          label,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                          ),
                        );
                      }

                      if (requestType == RequestType.incoming) {
                        final canRespond =
                            liveRequest.status == RequestStatus.pending ||
                            liveRequest.status == RequestStatus.waitingForAnswer;
                        final canMarkProvided =
                            liveRequest.status == RequestStatus.accepted;

                        if (canRespond) {
                          return Row(
                            children: [
                              Expanded(
                                child: ElevatedButton(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.redAccent.withValues(
                                      alpha: 0.8,
                                    ),
                                    padding: const EdgeInsets.symmetric(
                                      vertical: 16,
                                    ),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                  ),
                                  onPressed: _pendingStatus != null
                                      ? null
                                      : () => doUpdate(RequestStatus.rejected),
                                  child: buttonChild(
                                    RequestStatus.rejected,
                                    localizations?.rejectButton ?? 'Reject',
                                  ),
                                ),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: ElevatedButton(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.blueAccent,
                                    padding: const EdgeInsets.symmetric(
                                      vertical: 16,
                                    ),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                  ),
                                  onPressed: _pendingStatus != null
                                      ? null
                                      : () => doUpdate(RequestStatus.accepted),
                                  child: buttonChild(
                                    RequestStatus.accepted,
                                    localizations?.acceptButton ?? 'Accept',
                                  ),
                                ),
                              ),
                            ],
                          );
                        }

                        if (canMarkProvided) {
                          return SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.green,
                                padding: const EdgeInsets.symmetric(
                                  vertical: 16,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                              ),
                              onPressed: _pendingStatus != null
                                  ? null
                                  : () => doUpdate(RequestStatus.serviceProvided),
                              child: buttonChild(
                                RequestStatus.serviceProvided,
                                localizations?.markServiceProvidedButton ??
                                    'Mark Service as Provided',
                              ),
                            ),
                          );
                        }
                      }

                      if (requestType == RequestType.outgoing) {
                        final canCancel =
                            liveRequest.status == RequestStatus.pending ||
                            liveRequest.status == RequestStatus.waitingForAnswer ||
                            liveRequest.status == RequestStatus.accepted;
                        final canConfirmPayment =
                            liveRequest.status == RequestStatus.serviceProvided;

                        if (canCancel) {
                          return SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.redAccent.withValues(
                                  alpha: 0.8,
                                ),
                                padding: const EdgeInsets.symmetric(
                                  vertical: 16,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                              ),
                              onPressed: _pendingStatus != null
                                  ? null
                                  : () => doUpdate(RequestStatus.cancelled),
                              child: buttonChild(
                                RequestStatus.cancelled,
                                localizations?.cancelRequestButton ??
                                    'Cancel Request',
                              ),
                            ),
                          );
                        }

                        if (canConfirmPayment) {
                          return SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.green,
                                padding: const EdgeInsets.symmetric(
                                  vertical: 16,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                              ),
                              onPressed: _pendingStatus != null
                                  ? null
                                  : () => doUpdate(RequestStatus.completed),
                              child: buttonChild(
                                RequestStatus.completed,
                                localizations?.paymentButton ??
                                    'Confirm Payment',
                              ),
                            ),
                          );
                        }
                      }

                      return const SizedBox.shrink();
                    },
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusChip(BuildContext context, ServiceRequest request, {bool isIncoming = false}) {
    Color color;
    String text;
    final localizations = AppLocalizations.of(context);

    switch (request.status) {
      case RequestStatus.pending:
        color = Colors.orange;
        text = localizations?.pending ?? 'Pending';
        break;
      case RequestStatus.waitingForAnswer:
        color = Colors.blue;
        text = isIncoming
            ? (localizations?.actionNeededButton ?? 'Action Required')
            : (localizations?.waitingForAnswer ?? 'Waiting for Answer');
        break;
      case RequestStatus.completed:
        color = Colors.green;
        text = localizations?.completed ?? 'Completed';
        break;
      case RequestStatus.accepted:
        color = Colors.green;
        text = localizations?.accepted ?? 'Accepted';
        break;
      case RequestStatus.rejected:
        color = Colors.red;
        text = localizations?.rejected ?? 'Rejected';
        break;
      case RequestStatus.serviceProvided:
        color = Colors.teal;
        text = localizations?.serviceProvided ?? 'Service Provided';
        break;

      case RequestStatus.cancelled:
        color = Colors.grey;
        text = localizations?.cancelled ?? 'Cancelled';
        break;
      default:
        color = Colors.grey;
        text = localizations?.unknown ?? 'Unknown';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _buildDetailRow(BuildContext context, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 100,
          child: Text(
            label,
            style: TextStyle(
              color: context.appHintColor,
              fontSize: 16,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              color: context.appPrimaryColor,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
      ],
    );
  }
}
