import 'package:web/web.dart' as web;

class FallbackStorage {
  static Future<void> saveString(String key, String value) async {
    try {
      web.window.localStorage.setItem(key, value);
    } catch (_) {}
  }

  static Future<String?> getString(String key) async {
    try {
      return web.window.localStorage.getItem(key);
    } catch (_) {}
    return null;
  }

  static Future<void> remove(String key) async {
    try {
      web.window.localStorage.removeItem(key);
    } catch (_) {}
  }
}
