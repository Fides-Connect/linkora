import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/theme/app_theme_colors.dart';
import '../../../../core/widgets/app_background.dart';
import '../../../../localization/app_localizations.dart';
import '../../../../models/user.dart';
import '../viewmodels/home_tab_view_model.dart';
import 'user_detail_page.dart';

class FavoritesTabPage extends StatelessWidget {
  const FavoritesTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    final viewModel = context.watch<HomeTabViewModel>();
    final favorites = viewModel.favorites;

    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            const AppBackground(),
            if (viewModel.isLoading)
              const Center(child: CircularProgressIndicator())
            else if (favorites.isEmpty)
              Center(
                child: Text(
                  AppLocalizations.of(context)?.favoritesScreenEmpty ??
                      'Favorites Screen (Empty)',
                  style: TextStyle(color: context.appPrimaryColor),
                ),
              )
            else
              ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: favorites.length,
                separatorBuilder: (context, index) => const SizedBox(height: 16),
                itemBuilder: (context, index) {
                  final user = favorites[index];
                  return _buildFavoriteCard(context, user);
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildFavoriteCard(BuildContext context, User user) {
    return Card(
      color: context.appSurface1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          final viewModel = context.read<HomeTabViewModel>();
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => ChangeNotifierProvider.value(
                value: viewModel,
                child: UserDetailPage(user: user),
              ),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 30,
                backgroundColor: context.appSurface3,
                child: Text(
                  user.name.isNotEmpty ? user.name[0] : '?',
                  style: TextStyle(
                    fontSize: 24,
                    color: context.appPrimaryColor,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      user.name,
                      style: TextStyle(
                        color: context.appPrimaryColor,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      user.selfIntroduction,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: context.appSecondaryColor,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 4,
                      runSpacing: 4,
                      children: user.competencies.take(3).map((comp) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                                color: context.appSurface2,
                                borderRadius: BorderRadius.circular(4),
                              ),
                          child: Text(
                            comp.title,
                            style: TextStyle(
                              color: context.appSecondaryColor,
                              fontSize: 11,
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
