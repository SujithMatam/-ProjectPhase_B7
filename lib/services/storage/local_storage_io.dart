import 'dart:io';

class FallbackStorage {
  static File _getFile(String key) {
    try {
      String basePath = '';
      if (Platform.isWindows) {
        basePath = Platform.environment['LOCALAPPDATA'] ??
            Platform.environment['APPDATA'] ??
            Directory.current.path;
      } else {
        basePath = Platform.environment['HOME'] ?? Directory.current.path;
      }
      final dir = Directory('$basePath/OrthoSync');
      if (!dir.existsSync()) {
        dir.createSync(recursive: true);
      }
      return File('${dir.path}/$key.json');
    } catch (_) {
      return File('$key.json');
    }
  }

  static Future<void> saveString(String key, String value) async {
    try {
      final file = _getFile(key);
      await file.writeAsString(value, flush: true);
    } catch (_) {
      try {
        final fallbackFile = File('$key.json');
        await fallbackFile.writeAsString(value, flush: true);
      } catch (_) {}
    }
  }

  static Future<String?> getString(String key) async {
    try {
      final file = _getFile(key);
      if (await file.exists()) {
        return await file.readAsString();
      }
      final fallbackFile = File('$key.json');
      if (await fallbackFile.exists()) {
        return await fallbackFile.readAsString();
      }
    } catch (_) {}
    return null;
  }

  static Future<void> remove(String key) async {
    try {
      final file = _getFile(key);
      if (await file.exists()) {
        await file.delete();
      }
      final fallbackFile = File('$key.json');
      if (await fallbackFile.exists()) {
        await fallbackFile.delete();
      }
    } catch (_) {}
  }
}
