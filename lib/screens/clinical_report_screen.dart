// OrthoSync Clinical Report Screen
// ignore_for_file: deprecated_member_use

// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;


import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../models/patient_user.dart';
import '../services/ai_backend_service.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Colour palette shared across all cards
// ─────────────────────────────────────────────────────────────────────────────
const _kBlue = Color(0xFF4A90D9);
const _kGreen = Color(0xFF27AE60);
const _kOrange = Color(0xFFF39C12);
const _kRed = Color(0xFFE74C3C);
const _kPurple = Color(0xFF8E44AD);
const _kTeal = Color(0xFF1ABC9C);

class ClinicalReportScreen extends StatefulWidget {
  final PatientUser? patient;
  final bool isDarkMode;

  const ClinicalReportScreen({
    super.key,
    required this.patient,
    required this.isDarkMode,
  });

  @override
  State<ClinicalReportScreen> createState() => _ClinicalReportScreenState();
}

class _ClinicalReportScreenState extends State<ClinicalReportScreen>
    with SingleTickerProviderStateMixin {
  // ── state ─────────────────────────────────────────────────────────────────
  Map<String, dynamic>? _summary;
  Map<String, dynamic>? _reminderStatus;
  bool _loading = true;
  bool _error = false;
  String _errorMsg = '';

  bool _pdfLoading = false;

  late AnimationController _fadeCtrl;
  late Animation<double> _fadeAnim;

  int _selectedDays = 7;

  // ── lifecycle ─────────────────────────────────────────────────────────────
  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _fadeAnim = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeInOut);
    _loadSummary();
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    super.dispose();
  }

  // ── data ──────────────────────────────────────────────────────────────────
  Future<void> _loadSummary() async {
    setState(() {
      _loading = true;
      _error = false;
    });
    try {
      final patientId = widget.patient?.patientId ?? 'PT-B7-8921';
      final data = await AiBackendService.instance.getReportSummary(
        patientId: patientId,
        days: _selectedDays,
      );
      Map<String, dynamic>? reminderStatus;
      try {
        reminderStatus =
            await AiBackendService.instance.getMedicationReminderStatus();
      } catch (_) {
        // The report remains usable when the optional reminder status endpoint
        // is unavailable during backend startup.
      }
      if (mounted) {
        setState(() {
          _summary = data;
          _reminderStatus = reminderStatus;
          _loading = false;
        });
        _fadeCtrl.forward(from: 0);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = true;
          _errorMsg = e.toString();
        });
      }
    }
  }

  Future<void> _downloadPdf() async {
    setState(() => _pdfLoading = true);
    try {
      final patientId = widget.patient?.patientId ?? 'PT-B7-8921';
      final bytes = await AiBackendService.instance.downloadPdfReport(
        patientId: patientId,
        days: _selectedDays,
      );

      if (kIsWeb) {
        // Web: create a blob URL and trigger download
        final blob = html.Blob([bytes], 'application/pdf');
        final url = html.Url.createObjectUrlFromBlob(blob);
        html.AnchorElement(href: url)
          ..setAttribute('download', 'OrthoSync_Report_$patientId.pdf')
          ..click();
        html.Url.revokeObjectUrl(url);
      } else {
        // Mobile: show a snackbar for now; integrators can use path_provider
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                'PDF downloaded (${bytes.length} bytes). '
                'Save path integration needed for mobile.',
              ),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: _kRed,
            content: Text('PDF unavailable: $e'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _pdfLoading = false);
    }
  }

  // ── helpers ───────────────────────────────────────────────────────────────
  Color _triageColor(String level) {
    switch (level.toUpperCase()) {
      case 'RED':
        return _kRed;
      case 'YELLOW':
        return _kOrange;
      default:
        return _kGreen;
    }
  }

  // ── build ─────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final isDark = widget.isDarkMode;
    final bg = isDark ? const Color(0xFF10121A) : const Color(0xFFF4F7FF);
    final cardBg = isDark ? const Color(0xFF1E2035) : Colors.white;
    final textPrimary = isDark ? Colors.white : const Color(0xFF1A1F36);
    final textSecondary = isDark ? Colors.white60 : Colors.black54;

    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        backgroundColor: isDark ? const Color(0xFF1E2035) : Colors.white,
        elevation: 0,
        title: Row(
          children: [
            Icon(Icons.description_rounded, color: _kBlue, size: 22),
            const SizedBox(width: 8),
            Text(
              'Clinical Summary Report',
              style: TextStyle(
                color: textPrimary,
                fontWeight: FontWeight.bold,
                fontSize: 18,
              ),
            ),
          ],
        ),
        actions: [
          // Days selector
          DropdownButtonHideUnderline(
            child: DropdownButton<int>(
              value: _selectedDays,
              dropdownColor: cardBg,
              style: TextStyle(color: textPrimary, fontSize: 13),
              items: const [
                DropdownMenuItem(value: 3, child: Text('3 days')),
                DropdownMenuItem(value: 7, child: Text('7 days')),
                DropdownMenuItem(value: 14, child: Text('14 days')),
                DropdownMenuItem(value: 30, child: Text('30 days')),
              ],
              onChanged: (v) {
                if (v != null) {
                  setState(() => _selectedDays = v);
                  _loadSummary();
                }
              },
            ),
          ),
          const SizedBox(width: 8),
          // Refresh
          IconButton(
            tooltip: 'Refresh',
            icon: Icon(Icons.refresh, color: _kBlue),
            onPressed: _loadSummary,
          ),
          // PDF download
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: _pdfLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : ElevatedButton.icon(
                    onPressed: _downloadPdf,
                    icon: const Icon(Icons.picture_as_pdf, size: 16),
                    label: const Text('Download PDF'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _kRed,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 8,
                      ),
                      textStyle: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                      ),
                    ),
                  ),
          ),
        ],
      ),
      body: _buildBody(bg, cardBg, textPrimary, textSecondary),
    );
  }

  Widget _buildBody(
    Color bg,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    if (_loading) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(color: _kBlue),
            const SizedBox(height: 20),
            Text(
              'Generating clinical report…',
              style: TextStyle(color: textSecondary),
            ),
          ],
        ),
      );
    }

    if (_error) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.wifi_off_rounded, size: 64, color: _kRed),
              const SizedBox(height: 16),
              Text(
                'Backend unavailable',
                style: TextStyle(
                  color: textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Start the FastAPI server (python main.py) then retry.',
                textAlign: TextAlign.center,
                style: TextStyle(color: textSecondary),
              ),
              const SizedBox(height: 8),
              Text(
                _errorMsg,
                textAlign: TextAlign.center,
                style: TextStyle(color: textSecondary, fontSize: 11),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: _loadSummary,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _kBlue,
                  foregroundColor: Colors.white,
                ),
              ),
            ],
          ),
        ),
      );
    }

    final s = _summary!;

    return FadeTransition(
      opacity: _fadeAnim,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(s, cardBg, textPrimary, textSecondary),
                const SizedBox(height: 16),
                _buildStatsRow(s, cardBg, textPrimary, textSecondary),
                const SizedBox(height: 16),
                _buildPainTrajectory(s, cardBg, textPrimary, textSecondary),
                const SizedBox(height: 16),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: _buildMedicationCard(
                        s,
                        cardBg,
                        textPrimary,
                        textSecondary,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: _buildWellbeingCard(
                        s,
                        cardBg,
                        textPrimary,
                        textSecondary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _buildMedicationSchedule(
                  s,
                  cardBg,
                  textPrimary,
                  textSecondary,
                ),
                const SizedBox(height: 16),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: _buildExerciseCard(
                        s,
                        cardBg,
                        textPrimary,
                        textSecondary,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: _buildNutritionCard(
                        s,
                        cardBg,
                        textPrimary,
                        textSecondary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _buildTriageAlerts(s, cardBg, textPrimary, textSecondary),
                const SizedBox(height: 16),
                _buildClinicalNarrative(s, cardBg, textPrimary, textSecondary),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── section widgets ───────────────────────────────────────────────────────

  Widget _buildHeader(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    // Derive overall triage from safety_triage.status
    final safetyStatus = (s['safety_triage'] as Map?)?['status'] as String? ?? '';
    final overallLevel = safetyStatus.contains('CRITICAL')
        ? 'RED'
        : safetyStatus.contains('MODERATE')
        ? 'YELLOW'
        : 'GREEN';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _kBlue.withValues(alpha: 0.85),
            _kPurple.withValues(alpha: 0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 32,
            backgroundColor: Colors.white.withValues(alpha: 0.25),
            child: const Icon(
              Icons.person_rounded,
              size: 36,
              color: Colors.white,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${s['full_name'] ?? 'Patient'}  ·  ${s['patient_id'] ?? '—'}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${s['surgery_type'] ?? '—'}  •  ${s['affected_limb'] ?? ''} side',
                  style: const TextStyle(color: Colors.white70, fontSize: 14),
                ),
                const SizedBox(height: 4),
                Text(
                  'Surgeon: ${s['operating_surgeon'] ?? '—'}  •  Generated: ${s['generated_at'] ?? '—'}',
                  style: const TextStyle(color: Colors.white54, fontSize: 12),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              _triageBadge(overallLevel),
              const SizedBox(height: 6),
              Text(
                'Post-op Day ${s['postop_day'] ?? '—'}',
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _triageBadge(String level) {
    final color = _triageColor(level);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        border: Border.all(color: color, width: 1.5),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        level,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.bold,
          fontSize: 13,
        ),
      ),
    );
  }

  Widget _buildStatsRow(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    // Use actual backend schema keys
    final pain = s['pain_trend'] as Map? ?? {};
    final mob = s['mobility_progression'] as Map? ?? {};
    final med = s['medication_adherence'] as Map? ?? {};

    return Row(
      children: [
        Expanded(
          child: _statCard(
            icon: Icons.trending_down_rounded,
            color: _kGreen,
            label: 'Avg Pain',
            value: '${pain['average'] ?? '—'} / 10',
            bg: cardBg,
            textPrimary: textPrimary,
            textSecondary: textSecondary,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _statCard(
            icon: Icons.fitness_center_rounded,
            color: _kBlue,
            label: 'Exercise Adherence',
            value: '${mob['exercise_compliance_pct'] ?? 0}%',
            bg: cardBg,
            textPrimary: textPrimary,
            textSecondary: textSecondary,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _statCard(
            icon: Icons.medication_rounded,
            color: _kPurple,
            label: 'Med Adherence',
            value: '${med['overall_adherence_pct'] ?? 0}%',
            bg: cardBg,
            textPrimary: textPrimary,
            textSecondary: textSecondary,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _statCard(
            icon: Icons.rotate_right_rounded,
            color: _kTeal,
            label: 'Flexion ROM',
            value: '${mob['latest_flexion_deg'] ?? '—'}°',
            bg: cardBg,
            textPrimary: textPrimary,
            textSecondary: textSecondary,
          ),
        ),
      ],
    );
  }

  Widget _statCard({
    required IconData icon,
    required Color color,
    required String label,
    required String value,
    required Color bg,
    required Color textPrimary,
    required Color textSecondary,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              color: textPrimary,
              fontSize: 22,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(color: textSecondary, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildPainTrajectory(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    // Backend uses pain_trend (dict) and metrics_history (list) for bar chart
    final pain = s['pain_trend'] as Map? ?? {};
    final metrics = (s['metrics_history'] as List? ?? []);

    return _sectionCard(
      icon: Icons.show_chart,
      iconColor: _kOrange,
      title: 'Pain Trajectory ($_selectedDays Days)',
      cardBg: cardBg,
      textPrimary: textPrimary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _inlineChip('Peak: ${pain['max'] ?? '—'}', _kRed),
              const SizedBox(width: 8),
              _inlineChip('Avg: ${pain['average'] ?? '—'}', _kOrange),
              const SizedBox(width: 8),
              _inlineChip('Low: ${pain['min'] ?? '—'}', _kGreen),
              const SizedBox(width: 8),
              _inlineChip(pain['status'] as String? ?? 'Stable', _kBlue),
            ],
          ),
          if (metrics.isNotEmpty) ...[
            const SizedBox(height: 16),
            SizedBox(
              height: 64,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: metrics.take(14).map<Widget>((e) {
                  final val = (e['pain_score'] as num?)?.toDouble() ?? 0;
                  const maxH = 56.0;
                  final h = (val / 10) * maxH;
                  final barColor = val >= 7
                      ? _kRed
                      : val >= 4
                      ? _kOrange
                      : _kGreen;
                  return Expanded(
                    child: Container(
                      margin: const EdgeInsets.symmetric(horizontal: 2),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          Text(
                            '${val.toInt()}',
                            style: TextStyle(
                              fontSize: 9,
                              color: textSecondary,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Container(
                            height: h.clamp(4.0, maxH),
                            decoration: BoxDecoration(
                              color: barColor,
                              borderRadius: BorderRadius.circular(3),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ] else ...[
            const SizedBox(height: 12),
            Text(
              pain['status'] as String? ?? 'No daily pain data for this window.',
              style: TextStyle(color: textSecondary, fontSize: 14),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMedicationCard(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    // Backend: medication_adherence.{overall_adherence_pct, active_prescriptions[]}
    final med = s['medication_adherence'] as Map? ?? {};
    final prescriptions = (med['active_prescriptions'] as List? ?? []);

    return _sectionCard(
      icon: Icons.medication_rounded,
      iconColor: _kPurple,
      title: 'Medication Adherence',
      cardBg: cardBg,
      textPrimary: textPrimary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _progressBar(
            (med['overall_adherence_pct'] as num?)?.toInt() ?? 0,
            _kPurple,
            textSecondary,
          ),
          const SizedBox(height: 12),
          _kvRow(
            'Active prescriptions',
            '${prescriptions.length}',
            textPrimary,
            textSecondary,
          ),
          ...prescriptions.take(4).map((p) {
            final px = p as Map? ?? {};
            return Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(
                children: [
                  Icon(Icons.circle, size: 8, color: _kPurple),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${px['name'] ?? ''} ${px['dose'] ?? ''}  •  ${px['purpose'] ?? ''}',
                      style: TextStyle(color: textSecondary, fontSize: 12),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: _kGreen.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      '${px['adherence_pct'] ?? '—'}%',
                      style: TextStyle(
                        color: _kGreen,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildMedicationSchedule(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    final adherence = s['medication_adherence'] as Map? ?? {};
    final schedule = (adherence['daily_schedule'] as List? ?? []);
    final reminderEmail =
        _reminderStatus?['recipient'] ?? 'rvns12345@gamil.com';
    final configured = _reminderStatus?['email_configured'] == true;
    final running = _reminderStatus?['scheduler_running'] == true;

    return _sectionCard(
      icon: Icons.schedule_rounded,
      iconColor: _kTeal,
      title: "Today's Medication Schedule",
      cardBg: cardBg,
      textPrimary: textPrimary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Times and doses are taken from the prescribing doctor’s report.',
            style: TextStyle(color: textSecondary, fontSize: 12),
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              headingRowColor: WidgetStatePropertyAll(
                _kTeal.withValues(alpha: 0.12),
              ),
              columns: const [
                DataColumn(label: Text('Time')),
                DataColumn(label: Text('Medicine')),
                DataColumn(label: Text('Dose')),
                DataColumn(label: Text('Purpose')),
              ],
              rows: schedule.map((entry) {
                final row = entry as Map? ?? {};
                return DataRow(cells: [
                  DataCell(Text('${row['time'] ?? '—'}')),
                  DataCell(Text('${row['medication'] ?? '—'}')),
                  DataCell(Text('${row['dose'] ?? '—'}')),
                  DataCell(Text('${row['purpose'] ?? '—'}')),
                ]);
              }).toList(),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Icon(
                configured && running
                    ? Icons.notifications_active
                    : Icons.notifications_off,
                size: 17,
                color: configured && running ? _kGreen : _kOrange,
              ),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  configured && running
                      ? 'Email reminders are active for $reminderEmail.'
                      : 'Reminder scheduler is running for $reminderEmail; email delivery needs SMTP configuration.',
                  style: TextStyle(color: textSecondary, fontSize: 12),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildWellbeingCard(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    final wb = s['mental_wellbeing'] as Map? ?? {};
    final flags = (wb['flags'] as List? ?? []);
    final patterns = (wb['interaction_patterns'] as List? ?? []);

    return _sectionCard(
      icon: Icons.psychology_rounded,
      iconColor: _kTeal,
      title: 'Mental Wellbeing',
      cardBg: cardBg,
      textPrimary: textPrimary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _inlineChip(
                'Sentiment: ${wb['sentiment'] ?? 'neutral'}',
                _kTeal,
              ),
            ],
          ),
          const SizedBox(height: 10),
          _kvRow(
            'Kinesiophobia flags',
            '${wb['kinesiophobia_flags'] ?? 0}',
            textPrimary,
            textSecondary,
          ),
          _kvRow(
            'Anxiety mentions',
            '${wb['anxiety_mentions'] ?? 0}',
            textPrimary,
            textSecondary,
          ),
          _kvRow(
            'Sleep concerns',
            '${wb['sleep_concerns'] ?? 0}',
            textPrimary,
            textSecondary,
          ),
          if (flags.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              'Wellbeing flags:',
              style: TextStyle(
                color: textSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
            ...flags.take(3).map(
              (f) => Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(
                  children: [
                    Icon(Icons.flag_rounded, size: 14, color: _kOrange),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        f.toString(),
                        style: TextStyle(color: textSecondary, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
          if (patterns.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Interaction patterns:',
              style: TextStyle(
                color: textSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
            ...patterns.take(2).map(
              (p) => Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '• $p',
                  style: TextStyle(color: textSecondary, fontSize: 12),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildExerciseCard(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    final ex = s['exercise_adherence'] as Map? ?? {};
    final completed = (ex['completed_exercises'] as List? ?? []);

    return _sectionCard(
      icon: Icons.fitness_center_rounded,
      iconColor: _kBlue,
      title: 'Rehabilitation & Exercise',
      cardBg: cardBg,
      textPrimary: textPrimary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _progressBar(
            (ex['adherence_percentage'] as num?)?.toInt() ?? 0,
            _kBlue,
            textSecondary,
          ),
          const SizedBox(height: 12),
          _kvRow(
            'Sessions completed',
            '${ex['sessions_completed'] ?? 0}',
            textPrimary,
            textSecondary,
          ),
          _kvRow(
            'Sessions missed',
            '${ex['sessions_missed'] ?? 0}',
            textPrimary,
            textSecondary,
          ),
          if (completed.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Completed exercises:',
              style: TextStyle(
                color: textSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
            ...completed.take(4).map(
              (e) => Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(
                  children: [
                    Icon(Icons.check_circle_outline, size: 14, color: _kGreen),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        e.toString(),
                        style: TextStyle(color: textSecondary, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildNutritionCard(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    final nut = s['nutrition_summary'] as Map? ?? {};
    final concerns = (nut['concerns'] as List? ?? []);
    final recommendations = (nut['recommendations'] as List? ?? []);

    return _sectionCard(
      icon: Icons.restaurant_rounded,
      iconColor: _kGreen,
      title: 'Nutrition & Diet',
      cardBg: cardBg,
      textPrimary: textPrimary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _kvRow(
            'Protein target',
            nut['protein_target'] as String? ?? 'Not assessed',
            textPrimary,
            textSecondary,
          ),
          _kvRow(
            'Hydration status',
            nut['hydration_status'] as String? ?? 'Not assessed',
            textPrimary,
            textSecondary,
          ),
          _kvRow(
            'Supplement support',
            nut['supplement_support'] as String? ?? 'Not assessed',
            textPrimary,
            textSecondary,
          ),
          if (concerns.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Dietary concerns:',
              style: TextStyle(
                color: textSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
            ...concerns.take(3).map(
              (c) => Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(
                  children: [
                    Icon(Icons.info_outline, size: 14, color: _kOrange),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        c.toString(),
                        style: TextStyle(color: textSecondary, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
          if (recommendations.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Recommendations:',
              style: TextStyle(
                color: textSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
            ...recommendations.take(3).map(
              (r) => Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '• $r',
                  style: TextStyle(color: textSecondary, fontSize: 12),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTriageAlerts(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    final alerts = (s['triage_alerts'] as List? ?? []);
    if (alerts.isEmpty) return const SizedBox.shrink();

    return _sectionCard(
      icon: Icons.warning_amber_rounded,
      iconColor: _kRed,
      title: 'Safety Triage Alerts (${alerts.length})',
      cardBg: cardBg,
      textPrimary: textPrimary,
      child: Column(
        children: alerts.take(5).map<Widget>((alert) {
          final a = alert as Map? ?? {};
          final level = a['triage_level'] as String? ?? 'GREEN';
          final color = _triageColor(level);
          return Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: color.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: color,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            level,
                            style: TextStyle(
                              color: color,
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                            ),
                          ),
                          if (a['date'] != null) ...[
                            const SizedBox(width: 8),
                            Text(
                              a['date'].toString(),
                              style: TextStyle(
                                color: textSecondary,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ],
                      ),
                      if (a['urgency'] != null)
                        Text(
                          a['urgency'].toString(),
                          style: TextStyle(color: textPrimary, fontSize: 13),
                        ),
                      if (a['reasons'] != null)
                        Text(
                          (a['reasons'] as List).join(' · '),
                          style: TextStyle(
                            color: textSecondary,
                            fontSize: 12,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildClinicalNarrative(
    Map<String, dynamic> s,
    Color cardBg,
    Color textPrimary,
    Color textSecondary,
  ) {
    final narrative = s['clinical_narrative'] as String? ?? '';
    if (narrative.isEmpty) return const SizedBox.shrink();

    return _sectionCard(
      icon: Icons.article_rounded,
      iconColor: _kBlue,
      title: 'Clinical Narrative',
      cardBg: cardBg,
      textPrimary: textPrimary,
      child: Text(narrative, style: TextStyle(color: textSecondary, height: 1.6)),
    );
  }

  // ── reusable sub-components ───────────────────────────────────────────────

  Widget _sectionCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required Color cardBg,
    required Color textPrimary,
    required Widget child,
  }) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.07),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: iconColor, size: 18),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(
                  color: textPrimary,
                  fontWeight: FontWeight.bold,
                  fontSize: 15,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }

  Widget _inlineChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _progressBar(int pct, Color color, Color textSecondary) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Adherence',
              style: TextStyle(color: textSecondary, fontSize: 12),
            ),
            Text(
              '$pct%',
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.bold,
                fontSize: 13,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: LinearProgressIndicator(
            value: pct / 100,
            minHeight: 8,
            backgroundColor: color.withValues(alpha: 0.15),
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
      ],
    );
  }

  Widget _kvRow(
    String key,
    String value,
    Color textPrimary,
    Color textSecondary,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(key, style: TextStyle(color: textSecondary, fontSize: 13)),
          Text(
            value,
            style: TextStyle(
              color: textPrimary,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
