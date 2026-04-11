import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:provider/provider.dart';

import '../../../../localization/app_localizations.dart';
import '../../../../utils/constants.dart';
import '../viewmodels/assistant_tab_view_model.dart';
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
  late AssistantTabViewModel _assistantViewModel;
  late HomeTabViewModel _homeTabViewModel;

  late final bool _isLiteMode;
  late final List<Widget> _pages;

  static bool _readLiteMode() {
    try {
      return dotenv.env['APP_MODE']?.toLowerCase() == 'lite';
    } catch (_) {
      return false;
    }
  }

  @override
  void initState() {
    super.initState();
    _isLiteMode = _readLiteMode();
    _assistantViewModel = AssistantTabViewModel();
    _homeTabViewModel = HomeTabViewModel();

    if (_isLiteMode) {
      _pages = [
        const AssistantTabPage(),
        const MenuTabPage(showProfileItem: false, showNotificationsToggle: false),
      ];
    } else {
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
  }

  Future<void> _loadInitialData() async {
    debugPrint('[HomePage] _loadInitialData() called');
    try {
      await _homeTabViewModel.loadData();
      debugPrint('[HomePage] _loadInitialData() completed');
    } catch (e) {
      debugPrint('Error loading initial data: $e');
    }
  }

  @override
  void dispose() {
    _assistantViewModel.dispose();
    _homeTabViewModel.dispose();
    super.dispose();
  }

  void _onItemTapped(int index) {
    // Session and chat history are preserved across tab switches.
    // The session ends only via the stop button, app dispose, or 10-min idle timeout.
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final localizations = AppLocalizations.of(context);

    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: _assistantViewModel),
        ChangeNotifierProvider.value(value: _homeTabViewModel),
      ],
      child: Scaffold(
        body: IndexedStack(index: _selectedIndex, children: _pages),
        bottomNavigationBar: _isLiteMode
            ? BottomNavigationBar(
                items: <BottomNavigationBarItem>[
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.auto_awesome),
                    label: localizations?.navAssistant ?? 'Assistant',
                  ),
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.menu),
                    label: localizations?.navMenu ?? 'Menu',
                  ),
                ],
                currentIndex: _selectedIndex,
                selectedItemColor: AppConstants.primaryCyan,
                onTap: _onItemTapped,
              )
            : BottomNavigationBar(
                type: BottomNavigationBarType.fixed,
                items: <BottomNavigationBarItem>[
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.home),
                    label: localizations?.navHome ?? 'Home',
                  ),
                  BottomNavigationBarItem(
                    icon: const Icon(Icons.auto_awesome),
                    label: localizations?.navAssistant ?? 'Assistant',
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
