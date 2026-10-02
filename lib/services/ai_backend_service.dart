import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../models/patient_user.dart';

class AiBackendService {
  static final AiBackendService instance = AiBackendService._internal();
  factory AiBackendService() => instance;
  AiBackendService._internal();

  static const String baseUrl = 'http://127.0.0.1:8000';

  /// Check if Python agent service is running.
  Future<bool> isBackendOnline() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/health'))
          .timeout(const Duration(seconds: 2));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  /// Login against the Python backend.
  Future<Map<String, dynamic>?> patientLogin({
    required String identifier,
    required String password,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/patient-login'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'identifier': identifier, 'password': password}),
          )
          .timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) {
          return decoded;
        }
      }

      debugPrint(
        'Patient backend login failed: ${response.statusCode} ${response.body}',
      );
    } catch (e) {
      debugPrint('Patient backend login unavailable: $e');
    }

    return null;
  }

  /// Send message to Chatbot Agent with patient context and previous turns.
  Future<Map<String, dynamic>> sendChatMessage({
    required PatientUser? patient,
    required String message,
    List<Map<String, String>> chatHistory = const [],
  }) async {
    final payload = {
      'patient_id': patient?.patientId ?? 'PT-DEMO',
      'surgery_type': patient?.surgeryType ?? 'Total Knee Arthroplasty (TKA)',
      'affected_limb': patient?.affectedLimb ?? 'Right',
      'postop_day': patient?.postopDayCount ?? 3,
      'surgery_date': patient?.surgeryDate.toIso8601String(),
      'message': message,
      'chat_history': chatHistory,
    };

    Object? lastError;

    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        final response = await http
            .post(
              Uri.parse('$baseUrl/api/chat'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode(payload),
            )
            .timeout(const Duration(seconds: 15));

        if (response.statusCode == 200) {
          final decoded = jsonDecode(response.body);
          if (decoded is Map<String, dynamic>) {
            return decoded;
          }
          throw Exception('Invalid chatbot response from backend.');
        }

        final detail = response.body.trim();
        throw Exception(
          'Server returned status: ${response.statusCode}'
          '${detail.isEmpty ? '' : ' - $detail'}',
        );
      } catch (e) {
        lastError = e;
        if (attempt == 0) {
          await Future<void>.delayed(const Duration(milliseconds: 750));
        }
      }
    }

    debugPrint('AI Chatbot Backend unavailable: $lastError');
    throw lastError ?? Exception('AI chatbot request failed');
  }

  /// Send patient symptoms to Python Agentic Backend for assessment.
  Future<Map<String, dynamic>> assessSymptoms({
    required PatientUser patient,
    required String symptoms,
    int painScore = 5,
    double? temperatureC,
  }) async {
    final payload = {
      'patient_id': patient.patientId,
      'surgery_type': patient.surgeryType,
      'affected_limb': patient.affectedLimb,
      'postop_day': patient.postopDayCount,
      'symptoms': symptoms,
      'pain_score': painScore,
      'temperature_c': temperatureC,
    };

    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/assess-symptoms'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) {
          return decoded;
        }
        throw Exception('Invalid symptom assessment response.');
      }

      throw Exception('Server returned status: ${response.statusCode}');
    } catch (e) {
      debugPrint('AI Backend offline ($e). Using local safety fallback.');
      return _localSafetyFallback(patient, symptoms, painScore);
    }
  }

  /// Analyze an actual uploaded wound image using the current
  /// deterministic classical-computer-vision backend.
  ///
  /// This is deliberately separate from the future trained medical model.
  /// When the trained model is ready, this method can be changed to call
  /// the model-backed endpoint without changing the rest of the UI contract.
  Future<Map<String, dynamic>> analyzeWoundImage({
    required String fileName,
    required Uint8List bytes,
  }) async {
    if (bytes.isEmpty) {
      throw Exception('The selected image is empty.');
    }

    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/wound-image/analyze'),
    );

    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: fileName),
    );

    try {
      final streamedResponse = await request.send().timeout(
        const Duration(seconds: 30),
      );

      final response = await http.Response.fromStream(streamedResponse);

      Map<String, dynamic>? decoded;
      try {
        final body = jsonDecode(response.body);
        if (body is Map<String, dynamic>) {
          decoded = body;
        }
      } catch (_) {
        // Handled below with a friendly error.
      }

      if (response.statusCode >= 200 && response.statusCode < 300) {
        if (decoded != null) {
          return decoded;
        }
        throw Exception('The image analysis returned an invalid response.');
      }

      final detail = decoded?['detail']?.toString();
      throw Exception(
        detail?.isNotEmpty == true
            ? detail!
            : 'The image could not be analyzed (HTTP ${response.statusCode}).',
      );
    } catch (e) {
      debugPrint('Wound image analysis failed: $e');
      rethrow;
    }
  }

  /// Send a recorded voice message to the Python voice pipeline.
  ///
  /// The Flutter client sends a WAV file created from the recorder's PCM16
  /// stream. The backend transcribes it with faster-whisper and then feeds the
  /// transcript into the exact same safety-first LAM pipeline used by typed
  /// chat.
  Future<Map<String, dynamic>> sendVoiceMessage({
    required PatientUser? patient,
    required Uint8List audioBytes,
    required String fileName,
    List<Map<String, String>> chatHistory = const [],
  }) async {
    if (audioBytes.isEmpty) {
      throw Exception('The recorded voice message is empty.');
    }

    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/voice/chat'),
    );

    request.fields['patient_id'] = patient?.patientId ?? 'PT-DEMO';
    request.fields['surgery_type'] =
        patient?.surgeryType ?? 'Total Knee Arthroplasty (TKA)';
    request.fields['affected_limb'] = patient?.affectedLimb ?? 'Right';
    request.fields['postop_day'] = (patient?.postopDayCount ?? 3).toString();

    final surgeryDate = patient?.surgeryDate;
    if (surgeryDate != null) {
      request.fields['surgery_date'] = surgeryDate.toIso8601String();
    }

    if (chatHistory.isNotEmpty) {
      request.fields['chat_history'] = jsonEncode(chatHistory);
    }

    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        audioBytes,
        filename: fileName.isNotEmpty ? fileName : 'voice_message.wav',
      ),
    );

    try {
      final streamedResponse = await request.send().timeout(
        const Duration(minutes: 3),
      );

      final response = await http.Response.fromStream(streamedResponse);

      Map<String, dynamic>? decoded;
      try {
        final body = jsonDecode(response.body);
        if (body is Map<String, dynamic>) {
          decoded = body;
        }
      } catch (_) {}

      if (response.statusCode >= 200 && response.statusCode < 300) {
        if (decoded != null) {
          return decoded;
        }
        throw Exception('The voice service returned an invalid response.');
      }

      final detail = decoded?['detail']?.toString();
      throw Exception(
        detail?.isNotEmpty == true
            ? detail!
            : 'The voice message could not be processed '
                  '(HTTP ${response.statusCode}).',
      );
    } catch (e) {
      debugPrint('Voice message processing failed: $e');
      rethrow;
    }
  }

  /// Fetch the structured JSON clinical summary for a patient.
  Future<Map<String, dynamic>> getReportSummary({
    required String patientId,
    int days = 7,
  }) async {
    try {
      final response = await http
          .get(
            Uri.parse(
              '$baseUrl/api/reports/summary/'
              '${Uri.encodeComponent(patientId)}?days=$days',
            ),
          )
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) {
          return decoded;
        }
        throw Exception('Invalid report summary response.');
      }

      throw Exception('Report summary failed: ${response.statusCode}');
    } catch (e) {
      debugPrint('Report summary unavailable: $e');
      rethrow;
    }
  }

  /// Fetch the doctor's expanded daily medication schedule.
  Future<Map<String, dynamic>> getMedicationSchedule({
    required String patientId,
  }) async {
    try {
      final response = await http
          .get(
            Uri.parse(
              '$baseUrl/api/medications/schedule/'
              '${Uri.encodeComponent(patientId)}',
            ),
          )
          .timeout(const Duration(seconds: 15));

      if (response.statusCode != 200) {
        throw Exception('Medication schedule failed: ${response.statusCode}');
      }

      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }

      throw Exception('Invalid medication schedule response.');
    } catch (e) {
      debugPrint('Medication schedule unavailable: $e');
      rethrow;
    }
  }

  /// Fetch reminder delivery configuration/status from the running backend.
  Future<Map<String, dynamic>> getMedicationReminderStatus() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/medications/reminders/status'))
          .timeout(const Duration(seconds: 5));

      if (response.statusCode != 200) {
        throw Exception(
          'Medication reminder status failed: ${response.statusCode}',
        );
      }

      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }

      throw Exception('Invalid medication reminder response.');
    } catch (e) {
      debugPrint('Medication reminder status unavailable: $e');
      rethrow;
    }
  }

  /// Download the PDF clinical report as raw bytes.
  Future<Uint8List> downloadPdfReport({
    required String patientId,
    int days = 7,
  }) async {
    try {
      final response = await http
          .get(
            Uri.parse(
              '$baseUrl/api/reports/pdf/'
              '${Uri.encodeComponent(patientId)}?days=$days',
            ),
          )
          .timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        return response.bodyBytes;
      }

      throw Exception('PDF export failed: ${response.statusCode}');
    } catch (e) {
      debugPrint('PDF download unavailable: $e');
      rethrow;
    }
  }

  Map<String, dynamic> _localSafetyFallback(
    PatientUser patient,
    String symptoms,
    int painScore,
  ) {
    final lower = symptoms.toLowerCase();

    final isRed =
        lower.contains('calf') ||
        lower.contains('chest pain') ||
        lower.contains('pus');

    final isYellow =
        lower.contains('swelling') ||
        lower.contains('fever') ||
        lower.contains('stiffness');

    final triageLevel = isRed ? 'RED' : (isYellow ? 'YELLOW' : 'GREEN');

    return {
      'patient_id': patient.patientId,
      'surgery_type': patient.surgeryType,
      'affected_limb': patient.affectedLimb,
      'postop_day': patient.postopDayCount,
      'triage': {
        'triage_level': triageLevel,
        'urgency': isRed
            ? 'EMERGENCY CLINICAL ESCALATION'
            : (isYellow ? 'MODERATE RISK' : 'NORMAL RECOVERY'),
        'reasons': [
          if (isRed)
            'Red flag keyword detected'
          else if (isYellow)
            'Yellow risk symptom detected'
          else
            'Normal symptoms',
        ],
        'is_escalated': isRed || isYellow,
      },
      'clinical_summary':
          'Local device assessment. Triage status: $triageLevel.',
      'recommendations': [
        if (isRed)
          'Contact your surgical clinic emergency line immediately.'
        else if (isYellow)
          'Report persistent or worsening symptoms to your surgical team.'
        else
          'Continue your prescribed rehabilitation plan.',
      ],
      'retrieved_protocols': [],
    };
  }
}
