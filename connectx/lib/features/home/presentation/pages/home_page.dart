import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../localization/app_localizations.dart';
import '../../../../utils/constants.dart';
import '../viewmodels/search_tab_view_model.dart';
import '../viewmodels/home_tab_view_model.dart';
import 'assistant_tab_page.dart';

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
  late SearchTabViewModel _searchViewModel;
  late HomeTabViewModel _homeTabViewModel;

  late final List<Widget> _pages;

  @override
  void initState() {
    super.initState();
    _searchViewModel = SearchTabViewModel();
    _homeTabViewModel = HomeTabViewModel();

    _pages = [
      const HomeTabPage(),
      const AssistantTabPage(),
      const FavoritesTabPage(),
      const MenuTabPage(),
    ];
    
    // Explicitly handle async initialization
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadInitialData();
    });
  }

  Future<void> _loadInitialData() async {
    try {
      await _homeTabViewModel.loadData();
    } catch (e) {
      debugPrint('Error loading initial data: $e');
    }
  }

  @override
  void dispose() {
    _searchViewModel.dispose();
    _homeTabViewModel.dispose();
    super.dispose();
  }

  void _onItemTapped(int index) async {
    // If leaving the Search page (index 1), stop the chat
    if (_selectedIndex == 1 && index != 1) {
      final localizations = AppLocalizations.of(context);
      await _searchViewModel.stopChat(
          localizations?.tapMicrophoneToStart ?? 'Tap microphone to start');
    }

    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);

    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: _searchViewModel),
        ChangeNotifierProvider.value(value: _homeTabViewModel),
      ],
      child: Scaffold(
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
              icon: const Icon(Icons.auto_awesome),
              label: localizations?.navSearch ?? 'Assistant',
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
      ),
    );
  }
}
