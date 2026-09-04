import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/patient_user.dart';

class AiBackendService {
  static final AiBackendService instance = AiBackendService._internal();
  factory AiBackendService() => instance;
  AiBackendService._internal();

  static const String baseUrl = 'http://127.0.0.1:8000';

  /// Check if Python agent service is running
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

  /// Send message to Chatbot Agent
  Future<Map<String, dynamic>> sendChatMessage({
    required PatientUser? patient,
    required String message,
  }) async {
    final payload = {
      'patient_id': patient?.patientId ?? 'PT-DEMO',
      'surgery_type': patient?.surgeryType ?? 'Total Knee Arthroplasty (TKA)',
      'affected_limb': patient?.affectedLimb ?? 'Right',
      'postop_day': patient?.postopDayCount ?? 3,
      'message': message,
    };

    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/chat'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      } else {
        throw Exception('Server returned status: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('AI Chatbot Backend offline ($e). Using local intelligence.');
      return _localChatFallback(patient, message);
    }
  }

  /// Send patient symptoms to Python Agentic Backend for assessment
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
        return jsonDecode(response.body) as Map<String, dynamic>;
      } else {
        throw Exception('Server returned status: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('AI Backend offline ($e). Using local safety fallback.');
      return _localSafetyFallback(patient, symptoms, painScore);
    }
  }

  Map<String, dynamic> _localChatFallback(PatientUser? patient, String message) {
    final lower = message.toLowerCase();
    final day = patient?.postopDayCount ?? 3;
    final joint = patient?.surgeryType.contains('Hip') == true ? 'hip' : 'knee';

    if (lower.contains('calf') || lower.contains('shortness of breath') || lower.contains('chest pain') || lower.contains('pus')) {
      return {
        'reply': '⚠️ **CRITICAL ALERT**: You reported high-risk symptoms. Please contact your surgical emergency department immediately or call emergency services.',
        'triage_level': 'RED',
        'is_escalated': true,
      };
    } else if (lower.contains('swell') || lower.contains('ice')) {
      return {
        'reply': 'Mild to moderate swelling around your $joint is expected on Day $day. Elevate your leg above heart level and apply an ice pack (wrapped in a cloth) for 20 minutes, 3–4 times daily.',
        'triage_level': 'GREEN',
        'is_escalated': false,
      };
    } else if (lower.contains('pain') || lower.contains('medicine') || lower.contains('pill')) {
      return {
        'reply': 'Post-op soreness is normal as tissues recover. Take your prescribed pain medications 30-45 minutes before starting physical therapy sessions to keep pain manageable.',
        'triage_level': 'GREEN',
        'is_escalated': false,
      };
    } else {
      return {
        'reply': 'I am monitoring your recovery for Day $day. Make sure to perform your scheduled rehabilitation exercises, ice the $joint, and keep the incision clean and dry.',
        'triage_level': 'GREEN',
        'is_escalated': false,
      };
    }
  }

  Map<String, dynamic> _localSafetyFallback(PatientUser patient, String symptoms, int painScore) {
    final lower = symptoms.toLowerCase();
    final isRed = lower.contains('calf') || lower.contains('chest pain') || lower.contains('pus');
    final isYellow = lower.contains('swelling') || lower.contains('fever') || lower.contains('stiffness');
    final triageLevel = isRed ? 'RED' : (isYellow ? 'YELLOW' : 'GREEN');

    return {
      'patient_id': patient.patientId,
      'surgery_type': patient.surgeryType,
      'affected_limb': patient.affectedLimb,
      'postop_day': patient.postopDayCount,
      'triage': {
        'triage_level': triageLevel,
        'urgency': isRed ? 'EMERGENCY CLINICAL ESCALATION' : (isYellow ? 'MODERATE RISK' : 'NORMAL RECOVERY'),
        'reasons': [if (isRed) 'Red flag keyword detected' else if (isYellow) 'Yellow risk symptom detected' else 'Normal symptoms'],
        'is_escalated': isRed || isYellow,
      },
      'clinical_summary': 'Local device assessment. Triage status: $triageLevel.',
      'recommendations': [
        if (isRed)
          'Contact your surgical clinic emergency line immediately.'
        else if (isYellow)
          'Elevate limb and apply ice pack; report persistent swelling to nursing team.'
        else
          'Continue Day ${patient.postopDayCount} physical therapy rehabilitation exercises.'
      ],
      'retrieved_protocols': []
    };
  }
}
