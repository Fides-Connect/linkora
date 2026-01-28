import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../models/service_request.dart';
import '../viewmodels/home_tab_view_model.dart';
import 'profile_detail_page.dart';

class RequestDetailPage extends StatelessWidget {
  final ServiceRequest request;

  const RequestDetailPage({
    super.key,
    required this.request,
  });

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Text(
          request.title,
          style: const TextStyle(color: Colors.white),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
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
                      color: Colors.white.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Column(
                      children: [
                        CircleAvatar(
                          radius: 30,
                          backgroundColor: Colors.blue,
                          child: Icon(request.icon, color: Colors.white, size: 30),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          request.title,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          request.amount,
                          style: TextStyle(
                            color: request.amount.startsWith('+') ? Colors.greenAccent : Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 16),
                        // Status
                         _buildStatusChip(context, request),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // User Info
                  InkWell(
                    onTap: () async {
                      final viewModel = context.read<HomeTabViewModel>();
                      
                      // Show loading indicator
                      showDialog(
                        context: context,
                        barrierDismissible: false,
                        builder: (context) => const Center(child: CircularProgressIndicator()),
                      );
                      
                      try {
                        final profile = await viewModel.getOtherProfile(request.userName);
                        
                        // Close loading indicator
                        if (context.mounted) Navigator.pop(context);
                        
                        if (profile != null && context.mounted) {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => ChangeNotifierProvider.value(
                                value: viewModel,
                                child: ProfileDetailPage(profile: profile),
                              ),
                            ),
                          );
                        } else if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(localizations?.featureNotAvailable ?? 'Profile not found')),
                          );
                        }
                      } catch (e) {
                        // Close loading indicator
                        if (context.mounted) Navigator.pop(context);
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Error: $e')),
                          );
                        }
                      }
                    },
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
                      child: Row(
                        children: [
                          CircleAvatar(
                            radius: 25,
                            backgroundColor: Colors.white.withValues(alpha: 0.2),
                            child: Text(
                              request.userInitials,
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  request.userName,
                                  style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                                ),
                                Text(
                                  request.type == RequestType.incoming ? 'Requester' : 'Provider',
                                  style: TextStyle(color: Colors.white.withValues(alpha: 0.7)),
                                ),
                              ],
                            ),
                          ),
                          const Icon(Icons.arrow_forward_ios, color: Colors.white54, size: 16),
                        ],
                      ),
                    ),
                  ),

                  const Divider(color: Colors.white24, height: 32),

                  // Details
                  _buildDetailRow(context, localizations?.date ?? 'Date', request.getDate(localizations)),
                   if (request.getSecondDateLine(localizations) != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4.0),
                      child: _buildDetailRow(context, '', request.getSecondDateLine(localizations)!),
                    ),
                  
                  const SizedBox(height: 16),
                  _buildDetailRow(context, localizations?.location ?? 'Location', request.location),

                  const Divider(color: Colors.white24, height: 32),

                  // Description
                  Text(
                    localizations?.description ?? 'Description',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    request.description,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.9),
                      fontSize: 16,
                      height: 1.5,
                    ),
                  ),

                  const SizedBox(height: 48),

                  // Actions
                  if (request.type == RequestType.incoming)
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.redAccent.withValues(alpha: 0.8),
                              padding: const EdgeInsets.symmetric(vertical: 16),
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12)),
                            ),
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                    content: Text(
                                        localizations?.featureNotAvailable ??
                                            'N/A')),
                              );
                            },
                            child: Text(
                              localizations?.rejectButton ?? 'Reject',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 16),
                            ),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: ElevatedButton(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.blueAccent,
                              padding: const EdgeInsets.symmetric(vertical: 16),
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12)),
                            ),
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                    content: Text(
                                        localizations?.featureNotAvailable ??
                                            'N/A')),
                              );
                            },
                            child: Text(
                              localizations?.acceptButton ?? 'Accept',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 16),
                            ),
                          ),
                        ),
                      ],
                    ),
                  if (request.type == RequestType.outgoing &&
                      request.status == RequestStatus.waitingForAnswer)
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.redAccent.withValues(alpha: 0.8),
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12)),
                        ),
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                                content: Text(localizations?.featureNotAvailable ??
                                    'Feature not available')),
                          );
                        },
                        child: Text(
                          localizations?.cancelRequestButton ?? 'Cancel Request',
                          style: const TextStyle(
                              color: Colors.white, fontSize: 16),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusChip(BuildContext context, ServiceRequest request) {
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
        text = localizations?.waitingForAnswer ?? 'Waiting for Answer';
        break;
      case RequestStatus.completed:
        color = Colors.green;
        text = localizations?.completed ?? 'Completed';
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
              color: Colors.white.withValues(alpha: 0.6),
              fontSize: 16,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
      ],
    );
  }
}
