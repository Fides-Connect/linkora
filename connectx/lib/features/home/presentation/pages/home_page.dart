import 'package:flutter/material.dart';

import '../../../../localization/app_localizations.dart';
import '../../../../utils/constants.dart';
import 'ai_assistant_page.dart';

import 'favorites_tab_page.dart';
import 'home_tab_page.dart';
import 'menu_tab_page.dart';

class ConnectXHomePage extends StatefulWidget {
  const ConnectXHomePage({super.key});

  @override
  State<ConnectXHomePage> createState() => _ConnectXHomePageState();
}

class _ConnectXHomePageState extends State<ConnectXHomePage> {
  int _selectedIndex = 0;

  final List<Widget> _pages = [
    const HomeTabPage(),
    const AiAssistantPage(),
    const FavoritesTabPage(),
    const MenuTabPage(),
  ];

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);

    return Scaffold(
      body: IndexedStack(
        index: _selectedIndex,
        children: _pages,
      ),
      bottomNavigationBar: BottomNavigationBar(
        type: BottomNavigationBarType.fixed, // Needed for 4+ items
        items: <BottomNavigationBarItem>[
          BottomNavigationBarItem(
            icon: const Icon(Icons.home),
            label: localizations?.navHome ?? 'Home',
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.search),
            label: localizations?.navSearch ?? 'Search',
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.favorite),
            label: localizations?.navFavorites ?? 'Favorites',
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.menu),
            label: localizations?.navMenu ?? 'Menu',
          ),
        ],
        currentIndex: _selectedIndex,
        selectedItemColor: AppConstants.primaryCyan,
        onTap: _onItemTapped,
      ),
    );
  }
}
