import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';
import 'package:sqflite_common_ffi_web/sqflite_ffi_web.dart';
import 'package:path/path.dart' as p;

import '../models/patient_user.dart';

class DatabaseHelper {
  static final DatabaseHelper instance = DatabaseHelper._internal();
  factory DatabaseHelper() => instance;
  DatabaseHelper._internal();

  Database? _db;
  bool _useInMemoryFallback = false;

  final Map<String, Map<String, dynamic>> _memAccounts = {};
  final Map<String, PatientUser> _memPatients = {};
  final Map<String, MedicalHistory> _memMedicalHistory = {};
  final Map<String, DateTime> _memRecoveryStarts = {};
  final Map<String, List<Map<String, dynamic>>> _memChatMessages = {};

  Future<Database?> get database async {
    if (_useInMemoryFallback) return null;
    if (_db != null) return _db!;
    try {
      _db = await _initDatabase();
      return _db!;
    } catch (e) {
      debugPrint(
        'Database initialization failed ($e). Switching to safe fallback.',
      );
      _useInMemoryFallback = true;
      _seedMemoryData();
      return null;
    }
  }

  Future<Database> _initDatabase() async {
    if (kIsWeb) {
      databaseFactory = databaseFactoryFfiWeb;
      return await openDatabase(
        'postop_recovery.db',
        version: 3,
        onCreate: _createTables,
        onUpgrade: _upgradeDatabase,
      );
    }

    final dbPath = await getDatabasesPath();
    final path = p.join(dbPath, 'postop_recovery.db');
    return await openDatabase(
      path,
      version: 3,
      onCreate: _createTables,
      onUpgrade: _upgradeDatabase,
    );
  }

  Future<void> _createTables(Database db, int version) async {
    await db.execute('''
      CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE patients (
        patient_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        surgery_type TEXT NOT NULL,
        affected_limb TEXT NOT NULL,
        surgery_date TEXT NOT NULL,
        postop_day_count INTEGER NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE medical_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        allergies TEXT,
        chronic_conditions TEXT,
        past_surgeries TEXT,
        current_medications TEXT,
        implant_details TEXT,
        emergency_contact_name TEXT,
        emergency_contact_phone TEXT,
        notes TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES patients (patient_id) ON DELETE CASCADE
      )
    ''');

    await _createRecoveryTables(db);
    await _seedInitialData(db);
  }

  Future<void> _upgradeDatabase(
    Database db,
    int oldVersion,
    int newVersion,
  ) async {
    if (oldVersion < 2) {
      await _createRecoveryTables(db);
    }

    if (oldVersion < 3) {
      await db.execute(
        'ALTER TABLE chat_messages ADD COLUMN conversation_index INTEGER NOT NULL DEFAULT 0',
      );
      await db.execute(
        'CREATE INDEX IF NOT EXISTS idx_chat_messages_patient_day_chat '
        'ON chat_messages(patient_id, recovery_day, conversation_index, id)',
      );
    }
  }

  Future<void> _createRecoveryTables(Database db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS recovery_sessions (
        patient_id TEXT PRIMARY KEY,
        first_login_at TEXT NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES patients (patient_id) ON DELETE CASCADE
      )
    ''');

    await db.execute('''
      CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        recovery_day INTEGER NOT NULL,
        sender TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        is_key INTEGER NOT NULL DEFAULT 0,
        image_path TEXT,
        triage_level TEXT,
        is_escalated INTEGER NOT NULL DEFAULT 0,
        intent TEXT,
        target_agent TEXT,
        action TEXT,
        scope_status TEXT,
        sources TEXT,
        conversation_index INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (patient_id) REFERENCES patients (patient_id) ON DELETE CASCADE
      )
    ''');

    await db.execute(
      'CREATE INDEX IF NOT EXISTS idx_chat_messages_patient_day '
      'ON chat_messages(patient_id, recovery_day, id)',
    );

    await db.execute(
      'CREATE INDEX IF NOT EXISTS idx_chat_messages_patient_day_chat '
      'ON chat_messages(patient_id, recovery_day, conversation_index, id)',
    );
  }

  void _seedMemoryData() {
    _memAccounts['b7@amrita.edu'] = {
      'id': 1,
      'email': 'b7@amrita.edu',
      'password_hash': 'password123',
      'created_at': DateTime.now().toIso8601String(),
    };
    _memPatients['PT-B7-8921'] = PatientUser(
      patientId: 'PT-B7-8921',
      fullName: 'Rishi Priyan V N',
      email: 'b7@amrita.edu',
      phoneNumber: '+91 98765 43210',
      surgeryType: 'Total Knee Arthroplasty (TKA)',
      affectedLimb: 'Right',
      surgeryDate: DateTime.now().subtract(const Duration(days: 3)),
      postopDayCount: 3,
    );
    _memMedicalHistory['PT-B7-8921'] = MedicalHistory(
      patientId: 'PT-B7-8921',
      allergies: 'Penicillin, NSAIDs (mild rash)',
      chronicConditions: 'Stage 2 Osteoarthritis',
      pastSurgeries: 'Right Knee Arthroscopy (2023)',
      currentMedications: 'Paracetamol 650mg TDS, Enoxaparin 40mg SC OD',
      implantDetails: 'Zimmer Biomet Persona PS TKA (Right)',
      emergencyContactName: 'V N Sridhar',
      emergencyContactPhone: '+91 94440 12345',
      notes: 'Post-op Day 3: Ambulating with walker, 45 deg passive flexion.',
    );

    _memAccounts['sujith@amrita.edu'] = {
      'id': 2,
      'email': 'sujith@amrita.edu',
      'password_hash': 'password123',
      'created_at': DateTime.now().toIso8601String(),
    };
    _memPatients['PT-B7-8922'] = PatientUser(
      patientId: 'PT-B7-8922',
      fullName: 'Sujith Matam',
      email: 'sujith@amrita.edu',
      phoneNumber: '+91 98765 43211',
      surgeryType: 'Total Hip Arthroplasty (THA)',
      affectedLimb: 'Left',
      surgeryDate: DateTime.now().subtract(const Duration(days: 7)),
      postopDayCount: 7,
    );
  }

  Future<void> _seedInitialData(Database db) async {
    await db.insert('accounts', {
      'email': 'b7@amrita.edu',
      'password_hash': 'password123',
      'created_at': DateTime.now().toIso8601String(),
    }, conflictAlgorithm: ConflictAlgorithm.ignore);

    await db.insert('patients', {
      'patient_id': 'PT-B7-8921',
      'full_name': 'Rishi Priyan V N',
      'email': 'b7@amrita.edu',
      'phone_number': '+91 98765 43210',
      'surgery_type': 'Total Knee Arthroplasty (TKA)',
      'affected_limb': 'Right',
      'surgery_date': DateTime.now()
          .subtract(const Duration(days: 3))
          .toIso8601String(),
      'postop_day_count': 3,
    }, conflictAlgorithm: ConflictAlgorithm.ignore);

    await db.insert('medical_history', {
      'patient_id': 'PT-B7-8921',
      'allergies': 'Penicillin, NSAIDs (mild rash)',
      'chronic_conditions': 'Stage 2 Osteoarthritis',
      'past_surgeries': 'Right Knee Arthroscopy (2023)',
      'current_medications': 'Paracetamol 650mg TDS, Enoxaparin 40mg SC OD',
      'implant_details': 'Zimmer Biomet Persona PS TKA (Right)',
      'emergency_contact_name': 'V N Sridhar',
      'emergency_contact_phone': '+91 94440 12345',
      'notes': 'Post-op Day 3: Ambulating with walker, 45 deg passive flexion.',
      'updated_at': DateTime.now().toIso8601String(),
    }, conflictAlgorithm: ConflictAlgorithm.ignore);

    await db.insert('accounts', {
      'email': 'sujith@amrita.edu',
      'password_hash': 'password123',
      'created_at': DateTime.now().toIso8601String(),
    }, conflictAlgorithm: ConflictAlgorithm.ignore);

    await db.insert('patients', {
      'patient_id': 'PT-B7-8922',
      'full_name': 'Sujith Matam',
      'email': 'sujith@amrita.edu',
      'phone_number': '+91 98765 43211',
      'surgery_type': 'Total Hip Arthroplasty (THA)',
      'affected_limb': 'Left',
      'surgery_date': DateTime.now()
          .subtract(const Duration(days: 7))
          .toIso8601String(),
      'postop_day_count': 7,
    }, conflictAlgorithm: ConflictAlgorithm.ignore);
  }

  Future<int> insertAccount(String email, String password) async {
    final cleanEmail = email.trim().toLowerCase();
    final db = await database;
    if (db != null) {
      return await db.insert('accounts', {
        'email': cleanEmail,
        'password_hash': password,
        'created_at': DateTime.now().toIso8601String(),
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }

    _memAccounts[cleanEmail] = {
      'id': _memAccounts.length + 1,
      'email': cleanEmail,
      'password_hash': password,
      'created_at': DateTime.now().toIso8601String(),
    };
    return _memAccounts.length;
  }

  Future<Map<String, dynamic>?> getAccountByEmail(String email) async {
    final cleanEmail = email.trim().toLowerCase();
    final db = await database;
    if (db != null) {
      final res = await db.query(
        'accounts',
        where: 'LOWER(email) = ?',
        whereArgs: [cleanEmail],
        limit: 1,
      );
      return res.isNotEmpty ? res.first : null;
    }
    return _memAccounts[cleanEmail];
  }

  Future<int> updatePassword(String email, String newPassword) async {
    final cleanEmail = email.trim().toLowerCase();
    final db = await database;
    if (db != null) {
      return await db.update(
        'accounts',
        {'password_hash': newPassword},
        where: 'LOWER(email) = ?',
        whereArgs: [cleanEmail],
      );
    }
    if (_memAccounts.containsKey(cleanEmail)) {
      _memAccounts[cleanEmail]!['password_hash'] = newPassword;
      return 1;
    }
    return 0;
  }

  Future<int> insertPatient(PatientUser user) async {
    final db = await database;
    if (db != null) {
      return await db.insert(
        'patients',
        user.toMap(),
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    _memPatients[user.patientId] = user;
    return 1;
  }

  Future<PatientUser?> getPatientByIdOrEmail(String identifier) async {
    final cleanId = identifier.trim().toLowerCase();
    final db = await database;
    if (db != null) {
      final res = await db.query(
        'patients',
        where: 'LOWER(patient_id) = ? OR LOWER(email) = ?',
        whereArgs: [cleanId, cleanId],
        limit: 1,
      );
      if (res.isNotEmpty) return PatientUser.fromMap(res.first);
      return null;
    }

    for (final p in _memPatients.values) {
      if (p.patientId.toLowerCase() == cleanId ||
          p.email.toLowerCase() == cleanId) {
        return p;
      }
    }
    return null;
  }

  Future<List<PatientUser>> getAllPatients() async {
    final db = await database;
    if (db != null) {
      final res = await db.query('patients');
      return res.map((m) => PatientUser.fromMap(m)).toList();
    }
    return _memPatients.values.toList();
  }

  Future<int> saveMedicalHistory(MedicalHistory history) async {
    final db = await database;
    if (db != null) {
      final existing = await getMedicalHistory(history.patientId);
      if (existing != null) {
        return await db.update(
          'medical_history',
          history.toMap(),
          where: 'patient_id = ?',
          whereArgs: [history.patientId],
        );
      }
      return await db.insert(
        'medical_history',
        history.toMap(),
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    _memMedicalHistory[history.patientId] = history;
    return 1;
  }

  Future<MedicalHistory?> getMedicalHistory(String patientId) async {
    final db = await database;
    if (db != null) {
      final res = await db.query(
        'medical_history',
        where: 'patient_id = ?',
        whereArgs: [patientId],
        limit: 1,
      );
      if (res.isNotEmpty) return MedicalHistory.fromMap(res.first);
      return null;
    }
    return _memMedicalHistory[patientId];
  }

  Future<DateTime?> getRecoveryStart(String patientId) async {
    final db = await database;
    if (db != null) {
      final res = await db.query(
        'recovery_sessions',
        where: 'patient_id = ?',
        whereArgs: [patientId],
        limit: 1,
      );
      if (res.isNotEmpty) {
        return DateTime.tryParse(res.first['first_login_at'].toString());
      }
      return null;
    }
    return _memRecoveryStarts[patientId];
  }

  Future<DateTime> createRecoveryStart(String patientId) async {
    final existing = await getRecoveryStart(patientId);
    if (existing != null) return existing;

    final now = DateTime.now();
    final db = await database;
    if (db != null) {
      await db.insert('recovery_sessions', {
        'patient_id': patientId,
        'first_login_at': now.toIso8601String(),
      }, conflictAlgorithm: ConflictAlgorithm.ignore);
      final saved = await getRecoveryStart(patientId);
      return saved ?? now;
    }

    _memRecoveryStarts[patientId] = now;
    return now;
  }

  Future<DateTime> ensureRecoveryStart(String patientId) =>
      createRecoveryStart(patientId);

  Future<int> insertChatMessage({
    required String patientId,
    required int recoveryDay,
    required int conversationIndex,
    required String sender,
    required String message,
    required DateTime timestamp,
    bool isKey = false,
    String? imagePath,
    String? triageLevel,
    bool isEscalated = false,
    String? intent,
    String? targetAgent,
    String? action,
    String? scopeStatus,
    dynamic sources,
  }) async {
    final encodedSources = sources == null
        ? null
        : jsonEncode(sources is List ? sources : [sources]);

    final row = <String, dynamic>{
      'patient_id': patientId,
      'recovery_day': recoveryDay,
      'conversation_index': conversationIndex,
      'sender': sender,
      'message': message,
      'timestamp': timestamp.toIso8601String(),
      'is_key': isKey ? 1 : 0,
      'image_path': imagePath,
      'triage_level': triageLevel,
      'is_escalated': isEscalated ? 1 : 0,
      'intent': intent,
      'target_agent': targetAgent,
      'action': action,
      'scope_status': scopeStatus,
      'sources': encodedSources,
    };

    final db = await database;
    if (db != null) return await db.insert('chat_messages', row);

    final list = _memChatMessages.putIfAbsent(patientId, () => []);
    row['id'] = list.length + 1;
    list.add(row);
    return list.length;
  }

  Future<List<Map<String, dynamic>>> getChatMessages(
    String patientId,
    int recoveryDay,
    int conversationIndex,
  ) async {
    final db = await database;
    if (db != null) {
      final rows = await db.query(
        'chat_messages',
        where: 'patient_id = ? AND recovery_day = ? AND conversation_index = ?',
        whereArgs: [patientId, recoveryDay, conversationIndex],
        orderBy: 'id ASC',
      );
      return rows.map((row) {
        final copy = Map<String, dynamic>.from(row);
        final rawSources = copy['sources'];
        if (rawSources != null && rawSources.toString().isNotEmpty) {
          try {
            copy['sources'] = jsonDecode(rawSources.toString());
          } catch (_) {}
        }
        return copy;
      }).toList();
    }

    return List<Map<String, dynamic>>.from(
      _memChatMessages[patientId] ?? const [],
    )..removeWhere(
      (row) =>
          row['recovery_day'] != recoveryDay ||
          row['conversation_index'] != conversationIndex,
    );
  }

  Future<int> getNextConversationIndex(
    String patientId,
    int recoveryDay,
  ) async {
    final db = await database;
    if (db != null) {
      final rows = await db.rawQuery(
        'SELECT MAX(conversation_index) AS max_index '
        'FROM chat_messages WHERE patient_id = ? AND recovery_day = ?',
        [patientId, recoveryDay],
      );

      final value = rows.first['max_index'];
      final maxIndex = value == null
          ? -1
          : int.tryParse(value.toString()) ?? -1;
      return maxIndex + 1;
    }

    final rows = _memChatMessages[patientId] ?? const [];
    final indexes = rows
        .where((row) => row['recovery_day'] == recoveryDay)
        .map((row) => row['conversation_index'])
        .whereType<int>()
        .toList();

    if (indexes.isEmpty) return 0;
    return indexes.reduce((a, b) => a > b ? a : b) + 1;
  }

  Future<List<Map<String, int>>> getChatSessions(String patientId) async {
    final db = await database;

    if (db != null) {
      final rows = await db.rawQuery(
        'SELECT recovery_day, conversation_index '
        'FROM chat_messages '
        'WHERE patient_id = ? '
        'GROUP BY recovery_day, conversation_index '
        'ORDER BY recovery_day DESC, conversation_index DESC',
        [patientId],
      );

      return rows
          .map(
            (row) => {
              'recovery_day': int.tryParse(row['recovery_day'].toString()) ?? 1,
              'conversation_index':
                  int.tryParse(row['conversation_index'].toString()) ?? 0,
            },
          )
          .toList();
    }

    final rows = _memChatMessages[patientId] ?? const [];
    final seen = <String>{};
    final result = <Map<String, int>>[];

    for (final row in rows) {
      final day = row['recovery_day'] as int? ?? 1;
      final index = row['conversation_index'] as int? ?? 0;
      final key = '$day:$index';

      if (seen.add(key)) {
        result.add({'recovery_day': day, 'conversation_index': index});
      }
    }

    result.sort((a, b) {
      final dayCompare = (b['recovery_day'] ?? 0).compareTo(
        a['recovery_day'] ?? 0,
      );
      if (dayCompare != 0) return dayCompare;
      return (b['conversation_index'] ?? 0).compareTo(
        a['conversation_index'] ?? 0,
      );
    });

    return result;
  }

  Future<List<int>> getChatDays(String patientId) async {
    final db = await database;
    if (db != null) {
      final rows = await db.rawQuery(
        'SELECT DISTINCT recovery_day FROM chat_messages WHERE patient_id = ? ORDER BY recovery_day DESC',
        [patientId],
      );
      return rows
          .map((row) => int.tryParse(row['recovery_day'].toString()))
          .whereType<int>()
          .toList();
    }

    final rows = _memChatMessages[patientId] ?? const [];
    final days = rows
        .map((row) => row['recovery_day'])
        .whereType<int>()
        .toSet()
        .toList();
    days.sort((a, b) => b.compareTo(a));
    return days;
  }

  Future<List<Map<String, dynamic>>> queryTable(String tableName) async {
    final db = await database;
    if (db != null) return await db.query(tableName);

    if (tableName == 'patients') {
      return _memPatients.values.map((p) => p.toMap()).toList();
    }
    if (tableName == 'accounts') {
      return _memAccounts.values.toList();
    }
    if (tableName == 'medical_history') {
      return _memMedicalHistory.values.map((h) => h.toMap()).toList();
    }
    if (tableName == 'recovery_sessions') {
      return _memRecoveryStarts.entries
          .map(
            (e) => {
              'patient_id': e.key,
              'first_login_at': e.value.toIso8601String(),
            },
          )
          .toList();
    }
    if (tableName == 'chat_messages') {
      return _memChatMessages.values.expand((x) => x).toList();
    }
    return [];
  }

  Future<void> clearAndReseed() async {
    final db = await database;
    if (db != null) {
      await db.delete('chat_messages');
      await db.delete('recovery_sessions');
      await db.delete('medical_history');
      await db.delete('patients');
      await db.delete('accounts');
      await _seedInitialData(db);
      return;
    }

    _memAccounts.clear();
    _memPatients.clear();
    _memMedicalHistory.clear();
    _memRecoveryStarts.clear();
    _memChatMessages.clear();
    _seedMemoryData();
  }
}
