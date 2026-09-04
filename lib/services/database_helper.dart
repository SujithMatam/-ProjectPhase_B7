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

  // In-memory fallback if browser worker is blocked
  final Map<String, Map<String, dynamic>> _memAccounts = {};
  final Map<String, PatientUser> _memPatients = {};
  final Map<String, MedicalHistory> _memMedicalHistory = {};

  Future<Database?> get database async {
    if (_useInMemoryFallback) return null;
    if (_db != null) return _db!;
    try {
      _db = await _initDatabase();
      return _db!;
    } catch (e) {
      debugPrint('Database initialization failed ($e). Switching to safe fallback.');
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
        version: 1,
        onCreate: _createTables,
      );
    } else {
      final dbPath = await getDatabasesPath();
      final path = p.join(dbPath, 'postop_recovery.db');
      return await openDatabase(
        path,
        version: 1,
        onCreate: _createTables,
      );
    }
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

    await _seedInitialData(db);
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
    });
    await db.insert('patients', {
      'patient_id': 'PT-B7-8921',
      'full_name': 'Rishi Priyan V N',
      'email': 'b7@amrita.edu',
      'phone_number': '+91 98765 43210',
      'surgery_type': 'Total Knee Arthroplasty (TKA)',
      'affected_limb': 'Right',
      'surgery_date': DateTime.now().subtract(const Duration(days: 3)).toIso8601String(),
      'postop_day_count': 3,
    });
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
    });

    await db.insert('accounts', {
      'email': 'sujith@amrita.edu',
      'password_hash': 'password123',
      'created_at': DateTime.now().toIso8601String(),
    });
    await db.insert('patients', {
      'patient_id': 'PT-B7-8922',
      'full_name': 'Sujith Matam',
      'email': 'sujith@amrita.edu',
      'phone_number': '+91 98765 43211',
      'surgery_type': 'Total Hip Arthroplasty (THA)',
      'affected_limb': 'Left',
      'surgery_date': DateTime.now().subtract(const Duration(days: 7)).toIso8601String(),
      'postop_day_count': 7,
    });
  }

  // --- Account CRUD ---
  Future<int> insertAccount(String email, String password) async {
    final cleanEmail = email.trim().toLowerCase();
    final db = await database;
    if (db != null) {
      return await db.insert(
        'accounts',
        {
          'email': cleanEmail,
          'password_hash': password,
          'created_at': DateTime.now().toIso8601String(),
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    } else {
      _memAccounts[cleanEmail] = {
        'id': _memAccounts.length + 1,
        'email': cleanEmail,
        'password_hash': password,
        'created_at': DateTime.now().toIso8601String(),
      };
      return _memAccounts.length;
    }
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
    } else {
      return _memAccounts[cleanEmail];
    }
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
    } else {
      if (_memAccounts.containsKey(cleanEmail)) {
        _memAccounts[cleanEmail]!['password_hash'] = newPassword;
        return 1;
      }
      return 0;
    }
  }

  // --- Patient CRUD ---
  Future<int> insertPatient(PatientUser user) async {
    final db = await database;
    if (db != null) {
      return await db.insert(
        'patients',
        user.toMap(),
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    } else {
      _memPatients[user.patientId] = user;
      return 1;
    }
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
      if (res.isNotEmpty) {
        return PatientUser.fromMap(res.first);
      }
      return null;
    } else {
      for (final p in _memPatients.values) {
        if (p.patientId.toLowerCase() == cleanId || p.email.toLowerCase() == cleanId) {
          return p;
        }
      }
      return null;
    }
  }

  Future<List<PatientUser>> getAllPatients() async {
    final db = await database;
    if (db != null) {
      final res = await db.query('patients');
      return res.map((m) => PatientUser.fromMap(m)).toList();
    } else {
      return _memPatients.values.toList();
    }
  }

  // --- Medical History CRUD ---
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
      } else {
        return await db.insert(
          'medical_history',
          history.toMap(),
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }
    } else {
      _memMedicalHistory[history.patientId] = history;
      return 1;
    }
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
      if (res.isNotEmpty) {
        return MedicalHistory.fromMap(res.first);
      }
      return null;
    } else {
      return _memMedicalHistory[patientId];
    }
  }

  // --- Debug / Viewer Queries ---
  Future<List<Map<String, dynamic>>> queryTable(String tableName) async {
    final db = await database;
    if (db != null) {
      return await db.query(tableName);
    } else {
      if (tableName == 'patients') {
        return _memPatients.values.map((p) => p.toMap()).toList();
      } else if (tableName == 'accounts') {
        return _memAccounts.values.toList();
      } else if (tableName == 'medical_history') {
        return _memMedicalHistory.values.map((h) => h.toMap()).toList();
      }
      return [];
    }
  }

  Future<void> clearAndReseed() async {
    final db = await database;
    if (db != null) {
      await db.delete('medical_history');
      await db.delete('patients');
      await db.delete('accounts');
      await _seedInitialData(db);
    } else {
      _memAccounts.clear();
      _memPatients.clear();
      _memMedicalHistory.clear();
      _seedMemoryData();
    }
  }
}
