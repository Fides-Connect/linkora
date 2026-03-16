import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/service_request.dart';
import '../localization/app_localizations.dart';
import '../models/service_category.dart';

extension ServiceRequestFormatting on ServiceRequest {
  String getAmount(String currentUserId) {
    final requestType = getType(currentUserId);
    // final prefix = requestType == RequestType.incoming ? '+ ' : '- ';
    if (requestType == RequestType.incoming) {
      return '+ ${amountValue.toStringAsFixed(2)} $currency';
    } else if (requestType == RequestType.outgoing) {
      return '- ${amountValue.toStringAsFixed(2)} $currency';
    } else {
      return '? ${amountValue.toStringAsFixed(2)} $currency';
    }
  }

  String getDate(AppLocalizations? localizations) {
    final locale = localizations?.locale.toString();
    if (endDate == null) {
      return startDate != null ? _formatDate(startDate!, locale) : '';
    }
    final from = localizations?.dateFrom ?? 'From';
    return startDate != null ? '$from: ${_formatDate(startDate!, locale)}' : '';
  }

  String? getSecondDateLine(AppLocalizations? localizations) {
    if (endDate == null) return null;
    final locale = localizations?.locale.toString();
    final to = localizations?.dateTo ?? 'To';
    return '$to: ${_formatDate(endDate!, locale)}';
  }

  String _formatDate(DateTime dt, [String? locale]) {
    // Uses the provided locale if available, otherwise falls back to system default.
    // ensures month names and format structure respect the passed user's language setting.
    return DateFormat.yMMMMd(locale).format(dt);
  }
}

extension ServiceRequestUI on ServiceRequest {
  IconData get icon => category.icon;
}
