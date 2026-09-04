import 'package:flutter/material.dart';
import '../models/patient_user.dart';
import '../services/auth_service.dart';

class RegisterScreen extends StatefulWidget {
  final bool isDarkMode;
  const RegisterScreen({Key? key, required this.isDarkMode}) : super(key: key);

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();

  final TextEditingController _fullNameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _patientIdController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmPasswordController = TextEditingController();

  String _selectedSurgery = 'Total Knee Arthroplasty (TKA)';
  String _selectedLimb = 'Right';
  DateTime _surgeryDate = DateTime.now().subtract(const Duration(days: 2));

  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;
  bool _agreedToTerms = true;
  bool _isLoading = false;
  String? _errorMessage;

  final List<String> _surgeryOptions = [
    'Total Knee Arthroplasty (TKA)',
    'Total Hip Arthroplasty (THA)',
    'Ankle Reconstruction',
    'Lower Leg Fracture Fixation',
  ];

  final List<String> _limbOptions = ['Left', 'Right', 'Bilateral'];

  @override
  void initState() {
    super.initState();
    // Pre-populate with hospital-standard Patient ID format
    _patientIdController.text = 'PT-B7-${DateTime.now().millisecondsSinceEpoch.toString().substring(8)}';
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _patientIdController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _pickSurgeryDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _surgeryDate,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
      builder: (context, child) {
        return Theme(
          data: widget.isDarkMode ? ThemeData.dark() : ThemeData.light(),
          child: child!,
        );
      },
    );
    if (picked != null) {
      setState(() => _surgeryDate = picked);
    }
  }

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;

    if (!_agreedToTerms) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please acknowledge the postoperative data consent.')),
      );
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final newUser = PatientUser(
      patientId: _patientIdController.text.trim(),
      fullName: _fullNameController.text.trim(),
      email: _emailController.text.trim(),
      phoneNumber: _phoneController.text.trim(),
      surgeryType: _selectedSurgery,
      affectedLimb: _selectedLimb,
      surgeryDate: _surgeryDate,
    );

    final authService = AuthService();
    final success = await authService.register(newUser, _passwordController.text);

    if (!mounted) return;
    setState(() => _isLoading = false);

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: Colors.green.shade700,
          content: const Row(
            children: [
              Icon(Icons.check_circle, color: Colors.white),
              SizedBox(width: 8),
              Text('Registration successful! Access granted.'),
            ],
          ),
        ),
      );
      Navigator.pop(context, true); // return true to trigger logged in state
    } else {
      setState(() {
        _errorMessage = 'An account with this email is already registered. Please sign in.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = widget.isDarkMode;
    final bgColor1 = isDark ? const Color(0xFF10121A) : const Color(0xFFF8F9FE);
    final bgColor2 = isDark ? const Color(0xFF1A1A2E) : const Color(0xFFE8F0FE);
    final cardBg = isDark ? const Color(0xFF23263A) : Colors.white;
    final textColor = isDark ? Colors.white : const Color(0xFF202124);
    final subTextColor = isDark ? Colors.white70 : const Color(0xFF5F6368);
    final primaryColor = const Color(0xFF1A73E8);
    final inputFill = isDark ? const Color(0xFF1E2132) : const Color(0xFFF1F5F9);

    final daysAgo = DateTime.now().difference(_surgeryDate).inDays;

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [bgColor1, bgColor2],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: Column(
                  children: [
                    // Top App Bar
                    Row(
                      children: [
                        IconButton(
                          icon: Icon(Icons.arrow_back_ios_new, color: textColor, size: 20),
                          onPressed: () => Navigator.pop(context),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'Patient Registration',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            color: textColor,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // Card Container
                    Container(
                      padding: const EdgeInsets.all(24),
                      decoration: BoxDecoration(
                        color: cardBg,
                        borderRadius: BorderRadius.circular(24),
                        border: Border.all(
                          color: isDark ? Colors.white12 : Colors.black.withOpacity(0.06),
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(isDark ? 0.4 : 0.06),
                            blurRadius: 25,
                            offset: const Offset(0, 10),
                          ),
                        ],
                      ),
                      child: Form(
                        key: _formKey,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Header badge
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              decoration: BoxDecoration(
                                color: primaryColor.withOpacity(0.12),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.medical_services_outlined, size: 14, color: primaryColor),
                                  const SizedBox(width: 6),
                                  Text(
                                    'EHR Discharge Enrollment',
                                    style: TextStyle(
                                      color: primaryColor,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 12),
                            Text(
                              'Postoperative Profile Setup',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: textColor,
                              ),
                            ),
                            Text(
                              'Configure your below-hip clinical recovery tracking',
                              style: TextStyle(fontSize: 13, color: subTextColor),
                            ),
                            const SizedBox(height: 16),

                            if (_errorMessage != null) ...[
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.red.withOpacity(0.12),
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(color: Colors.red.withOpacity(0.3)),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.error_outline, color: Colors.red, size: 18),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        _errorMessage!,
                                        style: const TextStyle(color: Colors.red, fontSize: 12),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 16),
                            ],

                            // SECTION 1: Personal Info
                            _buildSectionHeader('1. Patient Demographics', textColor),
                            const SizedBox(height: 12),

                            _buildTextField(
                              controller: _fullNameController,
                              label: 'Full Name',
                              hint: 'e.g. Rishi Priyan',
                              icon: Icons.person_outline,
                              textColor: textColor,
                              fillColor: inputFill,
                              primaryColor: primaryColor,
                              validator: (v) => v == null || v.trim().isEmpty ? 'Enter full name' : null,
                            ),
                            const SizedBox(height: 12),

                            Row(
                              children: [
                                Expanded(
                                  child: _buildTextField(
                                    controller: _emailController,
                                    label: 'Email Address',
                                    hint: 'patient@hospital.com',
                                    icon: Icons.email_outlined,
                                    keyboardType: TextInputType.emailAddress,
                                    textColor: textColor,
                                    fillColor: inputFill,
                                    primaryColor: primaryColor,
                                    validator: (v) {
                                      if (v == null || v.trim().isEmpty) return 'Enter email';
                                      if (!v.contains('@')) return 'Enter valid email';
                                      return null;
                                    },
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: _buildTextField(
                                    controller: _phoneController,
                                    label: 'Phone Number',
                                    hint: '+91 98765 43210',
                                    icon: Icons.phone_outlined,
                                    keyboardType: TextInputType.phone,
                                    textColor: textColor,
                                    fillColor: inputFill,
                                    primaryColor: primaryColor,
                                    validator: (v) => v == null || v.trim().isEmpty ? 'Enter phone' : null,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 20),

                            // SECTION 2: Clinical Surgery Information (Milestone 2)
                            _buildSectionHeader('2. Orthopedic Surgery Details (Milestone 2)', textColor),
                            const SizedBox(height: 12),

                            _buildTextField(
                              controller: _patientIdController,
                              label: 'Hospital Patient ID / MRN',
                              hint: 'PT-B7-XXXX',
                              icon: Icons.badge_outlined,
                              textColor: textColor,
                              fillColor: inputFill,
                              primaryColor: primaryColor,
                              validator: (v) => v == null || v.trim().isEmpty ? 'Enter Patient ID' : null,
                            ),
                            const SizedBox(height: 12),

                            // Surgery Type Dropdown
                            Text(
                              'Surgical Procedure',
                              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor),
                            ),
                            const SizedBox(height: 6),
                            DropdownButtonFormField<String>(
                              value: _selectedSurgery,
                              dropdownColor: cardBg,
                              style: TextStyle(color: textColor, fontSize: 14),
                              decoration: InputDecoration(
                                prefixIcon: Icon(Icons.healing_outlined, color: primaryColor, size: 20),
                                filled: true,
                                fillColor: inputFill,
                                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(14),
                                  borderSide: BorderSide.none,
                                ),
                              ),
                              items: _surgeryOptions.map((opt) {
                                return DropdownMenuItem(value: opt, child: Text(opt));
                              }).toList(),
                              onChanged: (val) {
                                if (val != null) setState(() => _selectedSurgery = val);
                              },
                            ),
                            const SizedBox(height: 12),

                            // Limb and Surgery Date
                            Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Operated Limb',
                                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor),
                                      ),
                                      const SizedBox(height: 6),
                                      DropdownButtonFormField<String>(
                                        value: _selectedLimb,
                                        dropdownColor: cardBg,
                                        style: TextStyle(color: textColor, fontSize: 14),
                                        decoration: InputDecoration(
                                          prefixIcon: Icon(Icons.accessibility_new, color: primaryColor, size: 20),
                                          filled: true,
                                          fillColor: inputFill,
                                          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                          border: OutlineInputBorder(
                                            borderRadius: BorderRadius.circular(14),
                                            borderSide: BorderSide.none,
                                          ),
                                        ),
                                        items: _limbOptions.map((limb) {
                                          return DropdownMenuItem(value: limb, child: Text(limb));
                                        }).toList(),
                                        onChanged: (val) {
                                          if (val != null) setState(() => _selectedLimb = val);
                                        },
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Surgery Date',
                                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor),
                                      ),
                                      const SizedBox(height: 6),
                                      InkWell(
                                        onTap: _pickSurgeryDate,
                                        borderRadius: BorderRadius.circular(14),
                                        child: Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
                                          decoration: BoxDecoration(
                                            color: inputFill,
                                            borderRadius: BorderRadius.circular(14),
                                          ),
                                          child: Row(
                                            children: [
                                              Icon(Icons.calendar_today, color: primaryColor, size: 18),
                                              const SizedBox(width: 8),
                                              Expanded(
                                                child: Text(
                                                  '${_surgeryDate.day}/${_surgeryDate.month}/${_surgeryDate.year}',
                                                  style: TextStyle(color: textColor, fontSize: 13),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Align(
                              alignment: Alignment.centerRight,
                              child: Text(
                                'Calculated Postop Day: $daysAgo',
                                style: TextStyle(fontSize: 11, color: primaryColor, fontWeight: FontWeight.w600),
                              ),
                            ),
                            const SizedBox(height: 16),

                            // SECTION 3: Account Credentials
                            _buildSectionHeader('3. Security Credentials', textColor),
                            const SizedBox(height: 12),

                            _buildTextField(
                              controller: _passwordController,
                              label: 'Password',
                              hint: 'At least 6 characters',
                              icon: Icons.lock_outline,
                              obscureText: _obscurePassword,
                              textColor: textColor,
                              fillColor: inputFill,
                              primaryColor: primaryColor,
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                                  color: Colors.grey,
                                  size: 20,
                                ),
                                onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                              ),
                              validator: (v) {
                                if (v == null || v.length < 6) return 'Password must be at least 6 characters';
                                return null;
                              },
                            ),
                            const SizedBox(height: 12),

                            _buildTextField(
                              controller: _confirmPasswordController,
                              label: 'Confirm Password',
                              hint: 'Repeat your password',
                              icon: Icons.lock_reset,
                              obscureText: _obscureConfirmPassword,
                              textColor: textColor,
                              fillColor: inputFill,
                              primaryColor: primaryColor,
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _obscureConfirmPassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                                  color: Colors.grey,
                                  size: 20,
                                ),
                                onPressed: () => setState(() => _obscureConfirmPassword = !_obscureConfirmPassword),
                              ),
                              validator: (v) {
                                if (v != _passwordController.text) return 'Passwords do not match';
                                return null;
                              },
                            ),
                            const SizedBox(height: 14),

                            // Consent Checkbox
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                SizedBox(
                                  height: 24,
                                  width: 24,
                                  child: Checkbox(
                                    value: _agreedToTerms,
                                    activeColor: primaryColor,
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                                    onChanged: (v) => setState(() => _agreedToTerms = v ?? true),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    'I consent to offline encrypted storage of postoperative symptoms and clinical check-ins on this device.',
                                    style: TextStyle(fontSize: 11, color: subTextColor),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 20),

                            // Submit Button
                            SizedBox(
                              width: double.infinity,
                              height: 48,
                              child: ElevatedButton(
                                onPressed: _isLoading ? null : _handleRegister,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: primaryColor,
                                  foregroundColor: Colors.white,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                                  elevation: 2,
                                ),
                                child: _isLoading
                                    ? const SizedBox(
                                        height: 20,
                                        width: 20,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                        ),
                                      )
                                    : const Row(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: [
                                          Text(
                                            'Create Patient Profile',
                                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                                          ),
                                          SizedBox(width: 8),
                                          Icon(Icons.check, size: 18),
                                        ],
                                      ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    // Already have an account? Sign In
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text('Already have an account? ', style: TextStyle(fontSize: 13, color: subTextColor)),
                        GestureDetector(
                          onTap: () => Navigator.pop(context),
                          child: Text(
                            'Sign In',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                              color: primaryColor,
                              decoration: TextDecoration.underline,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title, Color textColor) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.w700,
        color: textColor.withOpacity(0.85),
        letterSpacing: 0.3,
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    required Color textColor,
    required Color fillColor,
    required Color primaryColor,
    TextInputType keyboardType = TextInputType.text,
    bool obscureText = false,
    Widget? suffixIcon,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: textColor),
        ),
        const SizedBox(height: 6),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          obscureText: obscureText,
          style: TextStyle(color: textColor, fontSize: 14),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 13),
            prefixIcon: Icon(icon, color: primaryColor, size: 20),
            suffixIcon: suffixIcon,
            filled: true,
            fillColor: fillColor,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide.none,
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide(color: primaryColor, width: 1.5),
            ),
          ),
          validator: validator,
        ),
      ],
    );
  }
}
