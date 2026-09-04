import 'dart:math';
import '../models/patient_user.dart';
import 'database_helper.dart';

class AuthService {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  final DatabaseHelper _dbHelper = DatabaseHelper.instance;
  final Map<String, String> _activeOtps = {}; // email -> 6-digit OTP

  PatientUser? _currentUser;
  PatientUser? get currentUser => _currentUser;
  bool get isAuthenticated => _currentUser != null;

  /// Authenticate with email or patientId and password against SQLite
  Future<PatientUser?> login(String identifier, String password) async {
    final cleanId = identifier.trim().toLowerCase();

    // Check patient record
    final patient = await _dbHelper.getPatientByIdOrEmail(cleanId);
    if (patient != null) {
      final account = await _dbHelper.getAccountByEmail(patient.email);
      if (account != null && account['password_hash'] == password) {
        _currentUser = patient;
        return _currentUser;
      }
    }

    // Also check account directly if registered with email
    final account = await _dbHelper.getAccountByEmail(cleanId);
    if (account != null && account['password_hash'] == password) {
      final pat = await _dbHelper.getPatientByIdOrEmail(account['email'] as String);
      if (pat != null) {
        _currentUser = pat;
        return _currentUser;
      }
    }

    return null;
  }

  /// Register a new patient in SQLite (account + patient profile + default medical history)
  Future<bool> register(PatientUser user, String password) async {
    final cleanEmail = user.email.trim().toLowerCase();

    // Check if account already exists
    final existingAccount = await _dbHelper.getAccountByEmail(cleanEmail);
    if (existingAccount != null) {
      return false; // Already registered
    }

    // 1. Insert Account
    await _dbHelper.insertAccount(cleanEmail, password);

    // 2. Insert Patient Record
    await _dbHelper.insertPatient(user);

    // 3. Create default Medical History for patient
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

    _currentUser = user;
    return true;
  }

  /// Send OTP to user's email for password recovery
  Future<String?> sendOtp(String email) async {
    await Future.delayed(const Duration(milliseconds: 400));
    final cleanEmail = email.trim().toLowerCase();

    final random = Random();
    final otp = (100000 + random.nextInt(900000)).toString();
    _activeOtps[cleanEmail] = otp;

    return otp;
  }

  /// Verify entered OTP
  Future<bool> verifyOtp(String email, String otp) async {
    await Future.delayed(const Duration(milliseconds: 300));
    final cleanEmail = email.trim().toLowerCase();
    return _activeOtps[cleanEmail] == otp.trim();
  }

  /// Reset password in SQLite
  Future<bool> resetPassword(String email, String newPassword) async {
    final cleanEmail = email.trim().toLowerCase();
    final account = await _dbHelper.getAccountByEmail(cleanEmail);

    if (account != null) {
      await _dbHelper.updatePassword(cleanEmail, newPassword);
      _activeOtps.remove(cleanEmail);
      return true;
    } else {
      // If account wasn't registered prior, register demo profile in SQLite
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
  }

  void logout() {
    _currentUser = null;
  }

  void setCurrentUser(PatientUser user) {
    _currentUser = user;
  }
}
