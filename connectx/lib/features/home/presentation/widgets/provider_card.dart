import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../models/provider_card_data.dart';

/// A rich card widget that displays a single provider result from Google Places.
class ProviderCard extends StatelessWidget {
  final ProviderCardData card;

  const ProviderCard({super.key, required this.card});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.12),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Photo header (if available)
          if (card.photoUrl != null && card.photoUrl!.isNotEmpty)
            ClipRRect(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(16)),
              child: Image.network(
                card.photoUrl!,
                height: 120,
                width: double.infinity,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) =>
                    const SizedBox.shrink(),
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Name + rating row
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        card.name,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    if (card.rating != null) ...[
                      const SizedBox(width: 8),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.star_rounded,
                              color: Color(0xFFFFC107), size: 16),
                          const SizedBox(width: 2),
                          Text(
                            card.ratingCount != null
                                ? '${card.rating!.toStringAsFixed(1)} (${card.ratingCount})'
                                : card.rating!.toStringAsFixed(1),
                            style: const TextStyle(
                              color: Colors.white70,
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
                // Reasoning (match justification)
                if (card.reasoning.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    card.reasoning,
                    style: TextStyle(
                      color: Colors.greenAccent.shade100,
                      fontSize: 13,
                      fontStyle: FontStyle.italic,
                      height: 1.3,
                    ),
                  ),
                ],
                // Description — only shown when the supplier wrote it themselves
                if (card.source != 'google_places' && card.description.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    card.description,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 13,
                      height: 1.4,
                    ),
                  ),
                ],
                // Contact row
                const SizedBox(height: 10),
                const Divider(color: Colors.white12, height: 1),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    if (card.phone != null && card.phone!.isNotEmpty)
                      _ContactChip(
                        icon: Icons.phone_rounded,
                        label: card.phone!,
                        onTap: () => _launch('tel:${card.phone}'),
                      ),
                    if (card.website != null && card.website!.isNotEmpty)
                      _ContactChip(
                        icon: Icons.language_rounded,
                        label: 'Website',
                        onTap: () => _launch(card.website!),
                      ),
                    if (card.address != null && card.address!.isNotEmpty)
                      _ContactChip(
                        icon: Icons.location_on_rounded,
                        label: card.address!,
                        onTap: () {
                          // Use the Maps place deep link when available so the
                          // user arrives directly at the place card, not a search.
                          final url = (card.mapsUrl != null && card.mapsUrl!.isNotEmpty)
                              ? card.mapsUrl!
                              : 'https://www.google.com/maps/search/?api=1&query=${Uri.encodeComponent(card.address!)}';
                          _launch(url);
                        },
                      ),
                    // Email enquiry — always shown so the user can send a
                    // pre-filled request even when no email address is known.
                    if (card.emailBody.isNotEmpty)
                      _ContactChip(
                        icon: Icons.mail_outline_rounded,
                        label: card.language == 'de' ? 'Anfrage senden' : 'Send request',
                        onTap: () {
                          final to = Uri.encodeComponent(card.email ?? '');
                          final subject = Uri.encodeComponent(card.emailSubject);
                          final body = Uri.encodeComponent(card.emailBody);
                          _launch('mailto:$to?subject=$subject&body=$body');
                        },
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _launch(String url) async {
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}

class _ContactChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _ContactChip({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: Colors.white54, size: 13),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
