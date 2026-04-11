import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/theme/app_theme_colors.dart';
import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../models/service_request.dart';
import '../../../../utils/service_request_extensions.dart';
import '../viewmodels/home_tab_view_model.dart';
import 'request_detail_page.dart';

class HomeTabPage extends StatelessWidget {
  const HomeTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);
    final viewModel = context.watch<HomeTabViewModel>();

    final incomingRequests = viewModel.incomingRequests;
    final outgoingRequests = viewModel.outgoingRequests;

    if (viewModel.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return Scaffold(
      body: Stack(
        children: [
          const AppBackground(),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              physics: const AlwaysScrollableScrollPhysics(),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Incoming Requests Section
                  Text(
                    localizations?.incomingRequestsTitle ?? 'Incoming Requests',
                    style: TextStyle(
                      color: context.appPrimaryColor,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (incomingRequests.isEmpty)
                    Text(
                      'No incoming requests',
                      style: TextStyle(
                        color: context.appHintColor,
                      ),
                    )
                  else
                    ...incomingRequests.map(
                      (req) => _buildIncomingRequestCard(
                        context,
                        req,
                        localizations,
                      ),
                    ),

                  const SizedBox(height: 32),

                  // Your Last Requests Section
                  Text(
                    localizations?.yourLastRequestsTitle ??
                        'Your Last Requests',
                    style: TextStyle(
                      color: context.appPrimaryColor,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (outgoingRequests.isEmpty)
                    Text(
                      'No requests yet',
                      style: TextStyle(
                        color: context.appHintColor,
                      ),
                    )
                  else
                    ...outgoingRequests.map(
                      (req) => _buildOutgoingRequestCard(
                        context,
                        req,
                        localizations,
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

  Widget _buildStatusBadge(ServiceRequest request, AppLocalizations? localizations, {bool isIncoming = false}) {
    final Color color;
    final String text;
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
      case RequestStatus.completed:
        color = Colors.green;
        text = localizations?.completed ?? 'Completed';
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
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.bold,
          fontSize: 12,
        ),
      ),
    );
  }

  Widget _buildIncomingRequestCard(
    BuildContext context,
    ServiceRequest request,
    AppLocalizations? localizations,
  ) {
    return GestureDetector(
      onTap: () {
        final viewModel = context.read<HomeTabViewModel>();
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => ChangeNotifierProvider.value(
              value: viewModel,
              child: RequestDetailPage(request: request),
            ),
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: context.appSurface1,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.blue,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(request.icon, color: Colors.white),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Text(
                    request.title,
                    style: TextStyle(
                      color: context.appPrimaryColor,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Column(
                  children: [
                    CircleAvatar(
                      radius: 20,
                      backgroundColor: context.appSurface3,
                      child: Text(
                        request.seekerUserInitials,
                        style: TextStyle(color: context.appPrimaryColor),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      request.seekerUserName,
                      style: TextStyle(
                        color: context.appSecondaryColor,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 8),
            Builder(
              builder: (context) {
                final viewModel = context.read<HomeTabViewModel>();
                final currentUserId = viewModel.user?.id ?? '';
                return Text(
                  request.getAmount(currentUserId),
                  style: TextStyle(color: context.appPrimaryColor, fontSize: 16),
                );
              },
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  request.getDate(localizations),
                  style: TextStyle(
                    color: context.appHintColor,
                    fontSize: 14,
                  ),
                ),
                _buildStatusBadge(request, localizations, isIncoming: true),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOutgoingRequestCard(
    BuildContext context,
    ServiceRequest request,
    AppLocalizations? localizations,
  ) {

    return GestureDetector(
      onTap: () {
        final viewModel = context.read<HomeTabViewModel>();
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => ChangeNotifierProvider.value(
              value: viewModel,
              child: RequestDetailPage(request: request),
            ),
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: context.appSurface1,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.blue,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(request.icon, color: Colors.white),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        request.title,
                        style: TextStyle(
                          color: context.appPrimaryColor,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (request.updateText != null)
                        Text(
                          request.updateText!,
                          style: TextStyle(
                            color: context.appHintColor,
                            fontSize: 12,
                          ),
                        ),
                    ],
                  ),
                ),
                Column(
                  children: [
                    CircleAvatar(
                      radius: 20,
                      backgroundColor: context.appSurface3,
                      child: Text(
                        request.selectedProviderUserInitials,
                        style: TextStyle(color: context.appPrimaryColor),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      request.selectedProviderUserName,
                      style: TextStyle(
                        color: context.appSecondaryColor,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 8),
            Builder(
              builder: (context) {
                final viewModel = context.read<HomeTabViewModel>();
                final currentUserId = viewModel.user?.id ?? '';
                return Text(
                  request.getAmount(currentUserId),
                  style: TextStyle(color: context.appPrimaryColor, fontSize: 16),
                );
              },
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      request.getDate(localizations),
                      style: TextStyle(
                        color: context.appHintColor,
                        fontSize: 14,
                      ),
                    ),
                    if (request.getSecondDateLine(localizations) != null)
                      Text(
                        request.getSecondDateLine(localizations)!,
                        style: TextStyle(
                          color: context.appHintColor,
                          fontSize: 14,
                        ),
                      ),
                  ],
                ),
                _buildStatusBadge(request, localizations),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
