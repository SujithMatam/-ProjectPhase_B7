import 'dart:math';

import '../models/patient_user.dart';
import 'database_helper.dart';
import 'ai_backend_service.dart';

class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  final DatabaseHelper _dbHelper = DatabaseHelper.instance;
  final Map<String, String> _activeOtps = {};

  PatientUser? _currentUser;
  PatientUser? get currentUser => _currentUser;
  bool get isAuthenticated => _currentUser != null;

  Future<PatientUser?> login(String identifier, String password) async {
    final cleanId = identifier.trim().toLowerCase();

    final patient = await _dbHelper.getPatientByIdOrEmail(cleanId);
    if (patient != null) {
      final account = await _dbHelper.getAccountByEmail(patient.email);
      if (account != null && account['password_hash'] == password) {
        _currentUser = patient;
        await _dbHelper.ensureRecoveryStart(patient.patientId);
        return _currentUser;
      }
    }

    final account = await _dbHelper.getAccountByEmail(cleanId);
    if (account != null && account['password_hash'] == password) {
      final pat = await _dbHelper.getPatientByIdOrEmail(
        account['email'] as String,
      );
      if (pat != null) {
        _currentUser = pat;
        await _dbHelper.ensureRecoveryStart(pat.patientId);
        return _currentUser;
      }
    }

    final backendResult = await AiBackendService.instance.patientLogin(
      identifier: identifier,
      password: password,
    );
    final backendPatient = backendResult?['patient'];
    if (backendPatient is Map<String, dynamic>) {
      final patientUser = PatientUser(
        patientId: backendPatient['patient_id']?.toString() ?? '',
        fullName: backendPatient['full_name']?.toString() ?? identifier.trim(),
        email: '${(backendPatient['patient_id'] ?? 'patient').toString().toLowerCase()}@orthosync.local',
        phoneNumber: backendPatient['phone_number']?.toString() ?? '',
        surgeryType: backendPatient['surgery_type']?.toString() ??
            'Total Knee Arthroplasty (TKA)',
        affectedLimb: backendPatient['affected_limb']?.toString() ?? 'Right',
        surgeryDate: DateTime.tryParse(
              backendPatient['surgery_date']?.toString() ?? '',
            ) ??
            DateTime.now(),
        postopDayCount: int.tryParse(
          backendPatient['postop_day']?.toString() ?? '1',
        ),
      );
      await _dbHelper.insertPatient(patientUser);
      _currentUser = patientUser;
      return _currentUser;
    }

    return null;
  }

  Future<bool> register(PatientUser user, String password) async {
    final cleanEmail = user.email.trim().toLowerCase();

    final existingAccount = await _dbHelper.getAccountByEmail(cleanEmail);
    if (existingAccount != null) return false;

    await _dbHelper.insertAccount(cleanEmail, password);
    await _dbHelper.insertPatient(user);

    final defaultHistory = MedicalHistory(
      patientId: user.patientId,
      allergies: 'None reported',
      chronicConditions: 'None',
      pastSurgeries: '${user.surgeryType} (${user.affectedLimb})',
      currentMedications: 'Prescribed post-op analgesics',
      implantDetails: user.surgeryType.contains('Hip')
          ? 'Total Hip Replacement Prosthesis'
          : 'Total Knee Replacement Prosthesis',
      emergencyContactName: 'Primary Emergency Contact',
      emergencyContactPhone: user.phoneNumber,
      notes: 'Initial registration profile created.',
    );
    await _dbHelper.saveMedicalHistory(defaultHistory);

    await _dbHelper.ensureRecoveryStart(user.patientId);
    _currentUser = user;
    return true;
  }

  Future<String?> sendOtp(String email) async {
    await Future.delayed(const Duration(milliseconds: 400));
    final cleanEmail = email.trim().toLowerCase();
    final random = Random();
    final otp = (100000 + random.nextInt(900000)).toString();
    _activeOtps[cleanEmail] = otp;
    return otp;
  }

  Future<bool> verifyOtp(String email, String otp) async {
    await Future.delayed(const Duration(milliseconds: 300));
    final cleanEmail = email.trim().toLowerCase();
    return _activeOtps[cleanEmail] == otp.trim();
  }

  Future<bool> resetPassword(String email, String newPassword) async {
    final cleanEmail = email.trim().toLowerCase();
    final account = await _dbHelper.getAccountByEmail(cleanEmail);

    if (account != null) {
      await _dbHelper.updatePassword(cleanEmail, newPassword);
      _activeOtps.remove(cleanEmail);
      return true;
    }

    final generatedId = 'PT-B7-${Random().nextInt(9000) + 1000}';
    final defaultUser = PatientUser(
      patientId: generatedId,
      fullName: 'Recovery Patient',
      email: cleanEmail,
      phoneNumber: '+91 98000 00000',
      surgeryType: 'Total Knee Arthroplasty (TKA)',
      affectedLimb: 'Right',
      surgeryDate: DateTime.now().subtract(const Duration(days: 4)),
    );
    await register(defaultUser, newPassword);
    _activeOtps.remove(cleanEmail);
    return true;
  }

  void logout() {
    _currentUser = null;
  }

  void setCurrentUser(PatientUser user) {
    _currentUser = user;
  }
}
