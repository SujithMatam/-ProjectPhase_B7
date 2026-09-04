class PatientUser {
  final String patientId; // e.g. "PT-B7-8921" or MRN
  final String fullName;
  final String email;
  final String phoneNumber;
  final String surgeryType; // e.g. "Total Knee Arthroplasty (TKA)"
  final String affectedLimb; // "Left", "Right", "Bilateral"
  final DateTime surgeryDate;
  final int postopDayCount;

  PatientUser({
    required this.patientId,
    required this.fullName,
    required this.email,
    required this.phoneNumber,
    required this.surgeryType,
    required this.affectedLimb,
    required this.surgeryDate,
    int? postopDayCount,
  }) : postopDayCount = postopDayCount ?? DateTime.now().difference(surgeryDate).inDays.clamp(1, 365);

  Map<String, dynamic> toMap() {
    return {
      'patient_id': patientId,
      'full_name': fullName,
      'email': email,
      'phone_number': phoneNumber,
      'surgery_type': surgeryType,
      'affected_limb': affectedLimb,
      'surgery_date': surgeryDate.toIso8601String(),
      'postop_day_count': postopDayCount,
    };
  }

  factory PatientUser.fromMap(Map<String, dynamic> map) {
    return PatientUser(
      patientId: map['patient_id'] as String? ?? '',
      fullName: map['full_name'] as String? ?? '',
      email: map['email'] as String? ?? '',
      phoneNumber: map['phone_number'] as String? ?? '',
      surgeryType: map['surgery_type'] as String? ?? 'Total Knee Arthroplasty (TKA)',
      affectedLimb: map['affected_limb'] as String? ?? 'Right',
      surgeryDate: map['surgery_date'] != null
          ? DateTime.tryParse(map['surgery_date'].toString()) ?? DateTime.now()
          : DateTime.now(),
      postopDayCount: map['postop_day_count'] is int
          ? map['postop_day_count'] as int
          : int.tryParse(map['postop_day_count']?.toString() ?? '1') ?? 1,
    );
  }

  PatientUser copyWith({
    String? patientId,
    String? fullName,
    String? email,
    String? phoneNumber,
    String? surgeryType,
    String? affectedLimb,
    DateTime? surgeryDate,
    int? postopDayCount,
  }) {
    return PatientUser(
      patientId: patientId ?? this.patientId,
      fullName: fullName ?? this.fullName,
      email: email ?? this.email,
      phoneNumber: phoneNumber ?? this.phoneNumber,
      surgeryType: surgeryType ?? this.surgeryType,
      affectedLimb: affectedLimb ?? this.affectedLimb,
      surgeryDate: surgeryDate ?? this.surgeryDate,
      postopDayCount: postopDayCount ?? this.postopDayCount,
    );
  }
}

class MedicalHistory {
  final int? id;
  final String patientId;
  final String allergies;
  final String chronicConditions;
  final String pastSurgeries;
  final String currentMedications;
  final String implantDetails;
  final String emergencyContactName;
  final String emergencyContactPhone;
  final String notes;
  final DateTime updatedAt;

  MedicalHistory({
    this.id,
    required this.patientId,
    this.allergies = 'None reported',
    this.chronicConditions = 'None',
    this.pastSurgeries = 'None',
    this.currentMedications = 'None',
    this.implantDetails = 'Standard Titanium Prosthesis',
    this.emergencyContactName = '',
    this.emergencyContactPhone = '',
    this.notes = '',
    DateTime? updatedAt,
  }) : updatedAt = updatedAt ?? DateTime.now();

  Map<String, dynamic> toMap() {
    final map = <String, dynamic>{
      'patient_id': patientId,
      'allergies': allergies,
      'chronic_conditions': chronicConditions,
      'past_surgeries': pastSurgeries,
      'current_medications': currentMedications,
      'implant_details': implantDetails,
      'emergency_contact_name': emergencyContactName,
      'emergency_contact_phone': emergencyContactPhone,
      'notes': notes,
      'updated_at': updatedAt.toIso8601String(),
    };
    if (id != null) {
      map['id'] = id;
    }
    return map;
  }

  factory MedicalHistory.fromMap(Map<String, dynamic> map) {
    return MedicalHistory(
      id: map['id'] as int?,
      patientId: map['patient_id'] as String? ?? '',
      allergies: map['allergies'] as String? ?? 'None reported',
      chronicConditions: map['chronic_conditions'] as String? ?? 'None',
      pastSurgeries: map['past_surgeries'] as String? ?? 'None',
      currentMedications: map['current_medications'] as String? ?? 'None',
      implantDetails: map['implant_details'] as String? ?? 'Standard Titanium Prosthesis',
      emergencyContactName: map['emergency_contact_name'] as String? ?? '',
      emergencyContactPhone: map['emergency_contact_phone'] as String? ?? '',
      notes: map['notes'] as String? ?? '',
      updatedAt: map['updated_at'] != null
          ? DateTime.tryParse(map['updated_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}
