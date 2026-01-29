import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/service_request.dart';
import '../localization/app_localizations.dart';
import '../models/service_category.dart';

extension ServiceRequestFormatting on ServiceRequest {
  String get amount {
    final prefix = type == RequestType.incoming ? '+ ' : '- ';
    return '$prefix${amountValue.toStringAsFixed(2)} $currency';
  }

  String getDate(AppLocalizations? localizations) {
    if (endDate == null) {
      return _formatDate(startDate);
    }
    final from = localizations?.dateFrom ?? 'From';
    return '$from: ${_formatDate(startDate)}';
  }

  String? getSecondDateLine(AppLocalizations? localizations) {
    if (endDate == null) return null;
    final to = localizations?.dateTo ?? 'To';
    return '$to: ${_formatDate(endDate!)}';
  }

  String _formatDate(DateTime dt) {
    // Uses the default locale which is set by the app (flutter_localizations)
    // Ensures month names and format structure respect the user's language setting.
    return DateFormat.yMMMMd().format(dt);
  }
}

extension ServiceRequestUI on ServiceRequest {
  IconData get icon => category.icon;
}
