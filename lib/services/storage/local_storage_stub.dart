class FallbackStorage {
  static Future<void> saveString(String key, String value) async {}
  static Future<String?> getString(String key) async => null;
  static Future<void> remove(String key) async {}
}
