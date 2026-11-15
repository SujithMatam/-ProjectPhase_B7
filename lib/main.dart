import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:image_picker/image_picker.dart';
import 'package:record/record.dart';
import 'package:super_clipboard/super_clipboard.dart';

import 'models/patient_user.dart';
import 'services/auth_service.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/db_viewer_screen.dart';
import 'screens/clinical_report_screen.dart';
import 'services/database_helper.dart';
import 'services/ai_backend_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await DatabaseHelper.instance.database;
  runApp(const OrthoSyncApp());
}

// --- Translation Dictionary ---
const Map<String, Map<String, String>> uiText = {
  'English': {
    'splash': 'Initializing Clinical Protocols...',
    'newCheckin': 'New Check-in',
    'recent': 'Recent Follow-ups',
    'authPrompt': 'Sign in to save your recovery progress.',
    'login': 'Log in',
    'signup': 'Sign up',
    'recoveryPlan': 'My Recovery Plan',
    'placeholder': 'Describe your symptoms...',
    'botGreeting':
        'Hello. I am OrthoSync AI. How is your recovery progressing today?',
    'botAuthReply': 'I am analyzing your specific recovery protocols.',
    'botVoiceReply': 'I received your voice note. How is your pain level?',
    'newCheckinPrompt': 'Starting a new check-in session. To begin, how would you rate your pain today on a scale of 1 to 10?',
    'patientRecords': 'Patient Records',
    'close': 'Close',
    'you': 'You',
    'darkTheme': 'Dark Theme',
    'language': 'Language',
    'help': 'Help',
    'logout': 'Log out',
    'uploadFiles': 'Select files',
    'takePhoto': 'Take a photo',
    'addDrive': 'Google Drive',
    'stopRecording': 'Stop Recording',
  },
  'Spanish': {
    'splash': 'Inicializando Protocolos...',
    'newCheckin': 'Nuevo Control',
    'recent': 'Seguimientos Recientes',
    'authPrompt': 'Inicie sesión para guardar.',
    'login': 'Iniciar sesión',
    'signup': 'Registrarse',
    'recoveryPlan': 'Mi Plan de Recuperación',
    'placeholder': 'Describa sus síntomas...',
    'botGreeting': 'Hola. Soy OrthoSync AI. ¿Cómo progresa su recuperación?',
    'botAuthReply': 'Estoy analizando sus protocolos.',
    'botVoiceReply': 'He recibido su nota de voz. ¿Cómo es su dolor?',
    'newCheckinPrompt': 'Iniciando un nuevo control. Para empezar, ¿cómo calificaría su dolor hoy del 1 al 10?',
    'patientRecords': 'Registros del Paciente',
    'close': 'Cerrar',
    'you': 'Tú',
    'darkTheme': 'Tema Oscuro',
    'language': 'Idioma',
    'help': 'Ayuda',
    'logout': 'Cerrar sesión',
    'uploadFiles': 'Seleccionar archivos',
    'takePhoto': 'Tomar foto',
    'addDrive': 'Google Drive',
    'stopRecording': 'Detener grabación',
  },
  'Hindi': {
    'splash': 'प्रोटोकॉल प्रारंभ हो रहा है...',
    'newCheckin': 'नया चेक-इन',
    'recent': 'हाल के फॉलो-अप',
    'authPrompt': 'प्रगति सहेजने के लिए साइन इन करें।',
    'login': 'लॉग इन',
    'signup': 'साइन अप',
    'recoveryPlan': 'मेरी रिकवरी योजना',
    'placeholder': 'लक्षणों का वर्णन करें...',
    'botGreeting': 'नमस्ते। मैं OrthoSync AI हूँ। रिकवरी कैसी है?',
    'botAuthReply': 'मैं आपके प्रोटोकॉल का विश्लेषण कर रहा हूँ।',
    'botVoiceReply': 'मुझे आपका वॉयस नोट मिला। दर्द कैसा है?',
    'newCheckinPrompt': 'नया चेक-इन सत्र शुरू हो रहा है। आज आपका दर्द 1 से 10 के पैमाने पर कैसा है?',
    'patientRecords': 'रोगी के रिकॉर्ड',
    'close': 'बंद करें',
    'you': 'आप',
    'darkTheme': 'डार्क थीम',
    'language': 'भाषा',
    'help': 'सहायता',
    'logout': 'लॉग आउट',
    'uploadFiles': 'फ़ाइलें चुनें',
    'takePhoto': 'फोटो लें',
    'addDrive': 'Google Drive',
    'stopRecording': 'रिकॉर्डिंग बंद करें',
  },
};

class OrthoSyncApp extends StatefulWidget {
  const OrthoSyncApp({super.key});

  @override
  State<OrthoSyncApp> createState() => _OrthoSyncAppState();
}

class _OrthoSyncAppState extends State<OrthoSyncApp> {
  bool isDarkMode = false;

  void toggleTheme(bool value) {
    setState(() => isDarkMode = value);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OrthoSync AI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.light,
        scaffoldBackgroundColor: Colors.transparent,
        primaryColor: const Color(0xFF1A73E8),
        cardColor: Colors.white.withValues(alpha: 0.9),
        dividerColor: const Color(0xFFDADCE0),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          elevation: 0,
          iconTheme: IconThemeData(color: Colors.black87),
        ),
      ),
      darkTheme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: Colors.transparent,
        primaryColor: const Color(0xFF8AB4F8),
        cardColor: const Color(0xFF2A2D3E).withValues(alpha: 0.9),
        dividerColor: const Color(0xFF3C4043),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          elevation: 0,
          iconTheme: IconThemeData(color: Colors.white),
        ),
      ),
      themeMode: isDarkMode ? ThemeMode.dark : ThemeMode.light,
      home: MainScreen(toggleTheme: toggleTheme, isDarkMode: isDarkMode),
    );
  }
}

class Message {
  final String sender;
  final String text;
  final bool isKey;
  final String? imagePath;
  final Uint8List? imageBytes;
  final Uint8List? audioBytes;
  final String? transcript;
  final double? audioDurationSeconds;

  final String? triageLevel;
  final bool isEscalated;
  final String? intent;
  final String? targetAgent;
  final String? action;
  final String? scopeStatus;
  final dynamic sources;

  Message({
    required this.sender,
    required this.text,
    this.isKey = false,
    this.imagePath,
    this.imageBytes,
    this.audioBytes,
    this.transcript,
    this.audioDurationSeconds,
    this.triageLevel,
    this.isEscalated = false,
    this.intent,
    this.targetAgent,
    this.action,
    this.scopeStatus,
    this.sources,
  });
}

class MainScreen extends StatefulWidget {
  final Function(bool) toggleTheme;
  final bool isDarkMode;
  const MainScreen({
    super.key,
    required this.toggleTheme,
    required this.isDarkMode,
  });

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  String lang = 'English';
  bool showSplash = true;
  bool isLoggedIn = false;
  bool isMenuOpen = false;
  bool isPlusMenuOpen = false;
  bool isRecording = false;
  bool isTyping = false;
  PatientUser? currentPatient;

  // Day-by-day recovery history. Each patient gets Day 1 at first login,
  // then the day advances automatically every 24 hours.
  int currentRecoveryDay = 1;
  int selectedRecoveryDay = 1;
  int selectedConversationIndex = 0;
  int currentConversationIndex = 0;
  DateTime? recoveryStartAt;
  Timer? recoveryDayTimer;

  List<Message> messages = [];
  List<int> audioLevels = [8, 12, 16, 12, 18, 14, 10, 15];

  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final ImagePicker _picker = ImagePicker();
  final AudioRecorder _voiceRecorder = AudioRecorder();

  StreamSubscription<Uint8List>? _voiceAudioSubscription;
  Timer? _voiceAmplitudeTimer;
  BytesBuilder? _voiceBytesBuilder;
  DateTime? _voiceStartedAt;
  Timer? _voiceMaxDurationTimer;
  bool _stoppingRecording = false;

  Map<String, String> get t => uiText[lang] ?? uiText['English']!;

  @override
  void initState() {
    super.initState();
    _playStartupSound();

    // Listen for Ctrl+V / browser paste events so images copied from
    // screenshots, browsers, Photos, etc. can be pasted directly into chat.
    ClipboardEvents.instance?.registerPasteEventListener(_onClipboardPaste);

    // Smooth splash screen timer
    Future.delayed(const Duration(milliseconds: 2500), () {
      if (mounted) setState(() => showSplash = false);
    });
  }

  void _playStartupSound() async {
    try {
      await _audioPlayer.play(
        UrlSource('https://actions.google.com/sounds/v1/ui/pop_up_on.ogg'),
      );
    } catch (e) {
      // Handled if browser blocks autoplay
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent + 100,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  int _calculateRecoveryDay(DateTime start) {
    final elapsed = DateTime.now().difference(start);
    if (elapsed.isNegative) return 1;
    return (elapsed.inHours ~/ 24) + 1;
  }

  Future<void> _initializeRecoveryHistory(PatientUser patient) async {
    recoveryStartAt = await DatabaseHelper.instance.getRecoveryStart(
      patient.patientId,
    );

    recoveryStartAt ??= await DatabaseHelper.instance.createRecoveryStart(
      patient.patientId,
    );

    final day = _calculateRecoveryDay(recoveryStartAt!);

    if (!mounted) return;

    final nextIndex = await DatabaseHelper.instance.getNextConversationIndex(
      patient.patientId,
      day,
    );

    final conversationIndex = nextIndex == 0 ? 0 : nextIndex - 1;

    setState(() {
      currentRecoveryDay = day;
      selectedRecoveryDay = day;
      currentConversationIndex = conversationIndex;
      selectedConversationIndex = conversationIndex;
      messages = [];
    });

    await _loadMessagesForConversation(day, conversationIndex);
    _startRecoveryDayTimer();
  }

  void _startRecoveryDayTimer() {
    recoveryDayTimer?.cancel();
    recoveryDayTimer = Timer.periodic(const Duration(minutes: 1), (_) async {
      final start = recoveryStartAt;
      if (start == null || currentPatient == null) return;

      final newDay = _calculateRecoveryDay(start);
      if (newDay != currentRecoveryDay && mounted) {
        setState(() {
          currentRecoveryDay = newDay;
          selectedRecoveryDay = newDay;
          currentConversationIndex = 0;
          selectedConversationIndex = 0;
          messages = [];
        });
        await _loadMessagesForConversation(newDay, 0);
      }
    });
  }

  String _conversationTitle(int day, int conversationIndex) {
    return conversationIndex == 0
        ? 'Day $day'
        : 'Day $day ($conversationIndex)';
  }

  Future<void> _loadMessagesForConversation(
    int day,
    int conversationIndex,
  ) async {
    final patient = currentPatient;
    if (patient == null) return;

    final rows = await DatabaseHelper.instance.getChatMessages(
      patient.patientId,
      day,
      conversationIndex,
    );

    final loaded = rows.map(_messageFromMap).toList();

    if (!mounted) return;

    setState(() {
      messages = loaded;
      selectedRecoveryDay = day;
      selectedConversationIndex = conversationIndex;

      if (day == currentRecoveryDay) {
        currentConversationIndex = conversationIndex;
      }
    });

    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
  }

  Future<void> _startNewChat({bool isDesktop = true}) async {
    final patient = currentPatient;
    if (!isLoggedIn || patient == null) return;

    _closeMenus();

    final day = currentRecoveryDay;
    final newIndex = await DatabaseHelper.instance.getNextConversationIndex(
      patient.patientId,
      day,
    );

    if (!mounted) return;

    setState(() {
      selectedRecoveryDay = day;
      selectedConversationIndex = newIndex;
      currentConversationIndex = newIndex;
      messages = [];
      isTyping = false;
      _inputController.clear();
    });

    if (!isDesktop) {
      Navigator.pop(context);
    }

    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
  }

  Future<void> _selectConversation(
    int day,
    int conversationIndex,
    bool isDesktop,
  ) async {
    if (!isLoggedIn || currentPatient == null) return;

    _closeMenus();

    if (!isDesktop) {
      Navigator.pop(context);
    }

    await _loadMessagesForConversation(day, conversationIndex);
  }

  Future<void> _loadMessagesForDay(int day) async {
    final patient = currentPatient;
    if (patient == null) return;

    await _loadMessagesForConversation(day, 0);
  }

  Message _messageFromMap(Map<String, dynamic> row) {
    return Message(
      sender: row['sender']?.toString() ?? 'bot',
      text: row['message']?.toString() ?? '',
      isKey: row['is_key'] == 1,
      imagePath: row['image_path']?.toString(),
      triageLevel: row['triage_level']?.toString(),
      isEscalated: row['is_escalated'] == 1,
      intent: row['intent']?.toString(),
      targetAgent: row['target_agent']?.toString(),
      action: row['action']?.toString(),
      scopeStatus: row['scope_status']?.toString(),
      sources: row['sources'],
    );
  }

  Future<void> _saveMessage(Message message) async {
    final patient = currentPatient;
    if (patient == null) return;

    await DatabaseHelper.instance.insertChatMessage(
      patientId: patient.patientId,
      recoveryDay: selectedRecoveryDay,
      conversationIndex: selectedConversationIndex,
      sender: message.sender,
      message: message.text,
      timestamp: DateTime.now(),
      isKey: message.isKey,
      imagePath: message.imagePath,
      triageLevel: message.triageLevel,
      isEscalated: message.isEscalated,
      intent: message.intent,
      targetAgent: message.targetAgent,
      action: message.action,
      scopeStatus: message.scopeStatus,
      sources: message.sources,
    );
  }

  Future<void> _selectRecoveryDay(int day, bool isDesktop) async {
    if (!isLoggedIn || currentPatient == null) return;

    _closeMenus();
    if (!isDesktop) Navigator.pop(context);

    await _loadMessagesForDay(day);
  }

  Future<void> _pickImage(ImageSource source) async {
    setState(() => isPlusMenuOpen = false);

    if (!isLoggedIn || currentPatient == null) {
      showModal(
        'Login Required',
        'Please log in to use OrthoSync AI. Your recovery information is needed to provide personalized postoperative guidance.',
      );
      return;
    }

    try {
      final XFile? image = await _picker.pickImage(source: source);
      if (image == null) return;

      final bytes = await image.readAsBytes();
      await _handleImageBytes(
        bytes,
        displayText: 'Uploaded an image',
        imagePath: image.path,
        fileName: image.name.isNotEmpty ? image.name : 'wound_image.png',
      );
    } catch (e) {
      showModal(
        'Image Error',
        'The image could not be opened. Please try another image or check the file permissions.',
      );
    }
  }

  Future<void> _onClipboardPaste(ClipboardReadEvent event) async {
    try {
      final reader = await event.getClipboardReader();

      // Image paste: this is the important path for Ctrl+V in Chrome.
      if (reader.canProvide(Formats.png)) {
        reader.getFile(
          Formats.png,
          (file) async {
            try {
              final bytes = await file.readAll();
              if (bytes.isEmpty) return;

              await _handleImageBytes(
                bytes,
                displayText: 'Pasted an image',
                fileName: file.fileName ?? 'pasted_image.png',
              );
            } catch (e) {
              if (mounted) {
                showModal(
                  'Paste Error',
                  'The image was copied, but OrthoSync AI could not read it from the clipboard. Please try copying the image again.',
                );
              }
            }
          },
          onError: (error) {
            if (mounted) {
              showModal(
                'Paste Error',
                'The image could not be read from the clipboard. Please try copying it again.',
              );
            }
          },
        );
        return;
      }

      // If the clipboard contains text instead of an image, preserve normal
      // Ctrl+V behaviour by inserting that text into the current TextField.
      if (reader.canProvide(Formats.plainText)) {
        final text = await reader.readValue(Formats.plainText);
        if (text != null && text.isNotEmpty && mounted) {
          _insertPastedText(text);
        }
      }
    } catch (e) {
      debugPrint('Clipboard paste handling failed: $e');
    }
  }

  void _insertPastedText(String pastedText) {
    final value = _inputController.value;
    final selection = value.selection;

    if (!selection.isValid) {
      _inputController.text += pastedText;
      _inputController.selection = TextSelection.collapsed(
        offset: _inputController.text.length,
      );
      return;
    }

    final start = selection.start;
    final end = selection.end;
    final newText = value.text.replaceRange(start, end, pastedText);
    final newOffset = start + pastedText.length;

    _inputController.value = value.copyWith(
      text: newText,
      selection: TextSelection.collapsed(offset: newOffset),
      composing: TextRange.empty,
    );
  }

  Future<void> _handleImageBytes(
    Uint8List bytes, {
    required String displayText,
    String? imagePath,
    required String fileName,
  }) async {
    if (!isLoggedIn || currentPatient == null) {
      showModal(
        'Login Required',
        'Please log in to use OrthoSync AI. Your recovery information is needed to provide personalized postoperative guidance.',
      );
      return;
    }

    if (bytes.isEmpty) return;

    final userMessage = Message(
      sender: 'user',
      text: displayText,
      imagePath: imagePath,
      imageBytes: bytes,
    );

    setState(() {
      messages.add(userMessage);
      isTyping = true;
      isPlusMenuOpen = false;
    });

    // Keep existing database behaviour. The raw pasted bytes are intentionally
    // kept in memory for the current chat instead of putting large binary data
    // into the SQLite text column.
    await _saveMessage(userMessage);
    _scrollToBottom();

    try {
      final result = await AiBackendService.instance.analyzeWoundImage(
        bytes: bytes,
        fileName: fileName,
      );

      if (!mounted) return;

      final analysis = result['analysis'];
      final reply = _friendlyImageAnalysisReply(analysis);

      final botMessage = Message(
        sender: 'bot',
        text: reply,
        targetAgent: 'WoundCareAgent',
      );

      setState(() {
        isTyping = false;
        messages.add(botMessage);
      });

      await _saveMessage(botMessage);
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;

      final errorMessage = Message(
        sender: 'bot',
        text: 'I received your image, but I could not complete the visual analysis right now. The image itself does not provide a diagnosis. Please try again, and if you have concerning symptoms, contact your surgical team.',
        targetAgent: 'WoundCareAgent',
      );

      setState(() {
        isTyping = false;
        messages.add(errorMessage);
      });

      await _saveMessage(errorMessage);
      _scrollToBottom();
    }
  }

  String _friendlyImageAnalysisReply(dynamic rawAnalysis) {
    if (rawAnalysis is! Map) {
      return 'I received your image, but I could not interpret the visual-analysis result. This image analysis is only a supplementary signal and is not a medical diagnosis.';
    }

    final flag = rawAnalysis['visual_flag']?.toString();
    final warnings = rawAnalysis['warnings'];

    final buffer = StringBuffer();
    buffer.write(
      'I checked the image using our current classical computer-vision analysis. ',
    );

    if (flag == 'elevated_redness_detected') {
      buffer.write(
        'It detected a redness-like color signal in part of the image. ',
      );
      buffer.write(
        'This does NOT mean the wound is infected or that there is a complication. ',
      );
    } else {
      buffer.write(
        'It did not detect a strong redness-like color signal in the image. ',
      );
    }

    if (warnings is List && warnings.isNotEmpty) {
      buffer.write(
        '\n\nImage-quality note: ${warnings.map((e) => e.toString()).join(' ')}',
      );
    }

    buffer.write(
      '\n\nThis is an experimental visual signal based on pixel color and brightness. '
      'It is not a trained or clinically validated wound-diagnosis model and should not replace your symptoms or a clinician\'s assessment.',
    );

    return buffer.toString();
  }

  void _handleGoogleDrive() {
    setState(() => isPlusMenuOpen = false);
    showModal("Google Drive", "Connecting to Google Drive file picker...");
  }

  void _selectAgent(String agentName) {
    setState(() => isPlusMenuOpen = false);
    showModal(
      "Agent Activated",
      "Successfully switched to the $agentName. Backend execution pool ready.",
    );
  }

  // --- FUNCTIONAL PATIENT RECORDS DISPLAY ---
  void _showPatientRecords() {
    _closeMenus();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Theme.of(context).cardColor,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Icon(Icons.folder_shared, color: Theme.of(context).primaryColor),
            const SizedBox(width: 10),
            Text(
              t['patientRecords'] ?? 'Patient Records',
              style: TextStyle(
                color: Theme.of(context).textTheme.bodyLarge?.color,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        content: SizedBox(
          width: double.maxFinite,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildRecordRow("Patient ID", "B7-9921"),
              _buildRecordRow("Name", "John Doe (Mock Patient)"),
              _buildRecordRow("Procedure", "Total Knee Arthroplasty (Right)"),
              _buildRecordRow("Date of Surgery", "August 15, 2026"),
              _buildRecordRow("Primary Surgeon", "Dr. Sarah Jenkins"),
              _buildRecordRow("Allergies", "Penicillin, Latex"),
              const Divider(),
              _buildRecordRow(
                "Current Status",
                "Post-op Week 3. Recovering as expected. Mild swelling reported.",
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              t['close'] ?? 'Close',
              style: TextStyle(
                color: Theme.of(context).primaryColor,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecordRow(String label, String val) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10.0),
      child: RichText(
        text: TextSpan(
          style: TextStyle(
            color: Theme.of(context).textTheme.bodyMedium?.color,
            fontSize: 14,
          ),
          children: [
            TextSpan(
              text: "$label: ",
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            TextSpan(text: val),
          ],
        ),
      ),
    );
  }

  void handleSend() async {
    final text = _inputController.text.trim();

    if (text.isEmpty) return;

    // LOGGED-OUT USERS: do not call the backend or save anything.
    // Show the typed message and explicitly ask the user to log in.
    if (!isLoggedIn || currentPatient == null) {
      final userMessage = Message(sender: 'user', text: text);

      final loginMessage = Message(
        sender: 'bot',
        text: 'Please log in to use OrthoSync AI. Your recovery information is needed to provide personalized postoperative guidance.',
      );

      setState(() {
        messages.add(userMessage);
        messages.add(loginMessage);
        _inputController.clear();
        isTyping = false;
      });

      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
      return;
    }

    // New messages are created in the currently selected conversation.
    // Historical conversations remain read-only from the sidebar.
    if (selectedRecoveryDay != currentRecoveryDay ||
        selectedConversationIndex != currentConversationIndex) {
      await _loadMessagesForConversation(
        currentRecoveryDay,
        currentConversationIndex,
      );
      return;
    }

    // Build conversation history BEFORE adding the current message so the
    // backend receives only previous turns plus the explicit current message.
    final chatHistory = messages
        .skip(messages.length > 10 ? messages.length - 10 : 0)
        .map(
          (msg) => {
            'role': msg.sender == 'user' ? 'user' : 'assistant',
            'content': msg.isKey ? (t[msg.text] ?? msg.text) : msg.text,
          },
        )
        .toList();

    final userMessage = Message(sender: 'user', text: text);

    setState(() {
      messages.add(userMessage);
      _inputController.clear();
      isTyping = true;
    });

    await _saveMessage(userMessage);
    Future.delayed(const Duration(milliseconds: 100), _scrollToBottom);

    try {
      final res = await AiBackendService.instance.sendChatMessage(
        patient: currentPatient,
        message: text,
        chatHistory: chatHistory,
      );

      if (!mounted) return;

      final botMessage = Message(
        sender: 'bot',
        text:
            res['reply'] as String? ??
            'I am analyzing your specific recovery protocols.',
        triageLevel: res['triage_level'] as String?,
        isEscalated: res['is_escalated'] == true,
        intent: res['intent'] as String?,
        targetAgent: res['target_agent'] as String?,
        action: res['action'] as String?,
        scopeStatus: res['scope_status'] as String?,
        sources: res['sources'],
      );

      setState(() {
        isTyping = false;
        messages.add(botMessage);
      });

      await _saveMessage(botMessage);
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;

      final errorMessage = Message(
        sender: 'bot',
        text: 'The local AI service is currently unavailable. Please start the backend and try again.',
      );

      setState(() {
        isTyping = false;
        messages.add(errorMessage);
      });

      await _saveMessage(errorMessage);
      _scrollToBottom();
    }
  }

  Future<void> startRecording() async {
    if (!isLoggedIn || currentPatient == null) {
      showModal(
        'Login Required',
        'Please log in to use OrthoSync AI. Your recovery information is needed to provide personalized postoperative guidance.',
      );
      return;
    }

    if (isRecording || _stoppingRecording) return;

    try {
      final hasPermission = await _voiceRecorder.hasPermission();
      if (!hasPermission) {
        showModal(
          'Microphone Permission',
          'Microphone access is required to record a voice message. Please allow microphone access in your browser or device settings and try again.',
        );
        return;
      }

      _voiceStartedAt = DateTime.now();
      _stoppingRecording = false;

      if (kIsWeb) {
        // Chrome/web: let the record package create the WAV file directly.
        // This avoids manually rebuilding a WAV header around browser PCM
        // chunks, which can result in audio that exists but is not usable by
        // the speech-to-text engine.
        const config = RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
          autoGain: true,
          echoCancel: true,
          noiseSuppress: true,
        );

        await _voiceRecorder.start(config, path: '');
      } else {
        // Native platforms: keep the PCM16 streaming path.
        const config = RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
          autoGain: true,
          echoCancel: true,
          noiseSuppress: true,
        );

        final audioStream = await _voiceRecorder.startStream(config);

        _voiceBytesBuilder = BytesBuilder(copy: false);

        await _voiceAudioSubscription?.cancel();
        _voiceAudioSubscription = audioStream.listen(
          (chunk) {
            _voiceBytesBuilder?.add(chunk);
          },
          onError: (Object error, StackTrace stackTrace) {
            debugPrint('Voice recorder stream error: $error');
          },
        );
      }

      if (!mounted) return;

      setState(() {
        isRecording = true;
        isTyping = false;
      });

      _voiceAmplitudeTimer?.cancel();
      _voiceAmplitudeTimer = Timer.periodic(const Duration(milliseconds: 100), (
        _,
      ) {
        if (!mounted || !isRecording) return;

        final phase = DateTime.now().millisecondsSinceEpoch ~/ 100;
        final heights = <int>[
          8 + ((phase + 0) % 5) * 3,
          8 + ((phase + 1) % 5) * 3,
          8 + ((phase + 2) % 5) * 3,
          8 + ((phase + 3) % 5) * 3,
          8 + ((phase + 4) % 5) * 3,
          8 + ((phase + 2) % 5) * 3,
          8 + ((phase + 1) % 5) * 3,
          8 + ((phase + 0) % 5) * 3,
        ];

        setState(() {
          audioLevels = heights;
        });
      });

      _voiceMaxDurationTimer?.cancel();
      _voiceMaxDurationTimer = Timer(const Duration(seconds: 120), () {
        if (isRecording && !_stoppingRecording) {
          unawaited(stopRecording());
        }
      });
    } catch (e) {
      debugPrint('Could not start voice recording: $e');

      _voiceAmplitudeTimer?.cancel();
      _voiceAmplitudeTimer = null;
      _voiceMaxDurationTimer?.cancel();
      _voiceMaxDurationTimer = null;

      await _voiceAudioSubscription?.cancel();
      _voiceAudioSubscription = null;
      _voiceBytesBuilder = null;
      _voiceStartedAt = null;

      try {
        if (await _voiceRecorder.isRecording()) {
          await _voiceRecorder.stop();
        }
      } catch (_) {}

      if (mounted) {
        setState(() {
          isRecording = false;
          audioLevels = [8, 12, 16, 12, 18, 14, 10, 15];
        });
        showModal(
          'Recording Error',
          'I could not access the microphone. Please check the browser microphone permission and try again.',
        );
      }
    }
  }

  Future<void> stopRecording() async {
    if (!isRecording || _stoppingRecording) return;

    _stoppingRecording = true;
    _voiceAmplitudeTimer?.cancel();
    _voiceAmplitudeTimer = null;
    _voiceMaxDurationTimer?.cancel();
    _voiceMaxDurationTimer = null;

    Uint8List? audioBytes;
    final startedAt = _voiceStartedAt;

    try {
      if (kIsWeb) {
        // On web, stop() returns the browser blob URL for the WAV recording.
        final recordingPath = await _voiceRecorder.stop();

        if (recordingPath == null || recordingPath.isEmpty) {
          throw Exception('The browser did not return a recording.');
        }

        audioBytes = await XFile(recordingPath).readAsBytes();
      } else {
        // Native platforms still provide raw PCM16 through startStream().
        await _voiceRecorder.stop();
        await _voiceAudioSubscription?.cancel();
        _voiceAudioSubscription = null;

        final pcmBytes = _voiceBytesBuilder?.takeBytes();
        if (pcmBytes != null && pcmBytes.isNotEmpty) {
          audioBytes = _pcm16ToWav(pcmBytes, sampleRate: 16000, channels: 1);
        }
      }
    } catch (e) {
      debugPrint('Could not stop/read voice recording: $e');
    } finally {
      _voiceBytesBuilder = null;
      _voiceStartedAt = null;

      if (mounted) {
        setState(() {
          isRecording = false;
          audioLevels = [8, 12, 16, 12, 18, 14, 10, 15];
        });
      }
    }

    try {
      if (audioBytes == null || audioBytes!.isEmpty) {
        if (mounted) {
          showModal(
            'No Audio Captured',
            'I did not receive any microphone audio. Please try recording again.',
          );
        }
        return;
      }

      final duration = startedAt == null
          ? null
          : DateTime.now().difference(startedAt).inMilliseconds / 1000.0;

      debugPrint(
        'Voice recording captured: ${audioBytes!.length} bytes, '
        'duration: ${duration?.toStringAsFixed(2)}s, '
        'web: $kIsWeb',
      );

      await _handleVoiceBytes(
        audioBytes!,
        fileName: 'voice_message.wav',
        durationSeconds: duration,
      );
    } finally {
      _stoppingRecording = false;
    }
  }

  Uint8List _pcm16ToWav(
    Uint8List pcmBytes, {
    required int sampleRate,
    required int channels,
  }) {
    const bitsPerSample = 16;
    final byteRate = sampleRate * channels * (bitsPerSample ~/ 8);
    final blockAlign = channels * (bitsPerSample ~/ 8);
    final dataLength = pcmBytes.length;
    final fileLength = 36 + dataLength;

    final output = BytesBuilder(copy: false);

    void writeAscii(String value) {
      output.add(value.codeUnits);
    }

    void writeUint32(int value) {
      final data = ByteData(4)..setUint32(0, value, Endian.little);
      output.add(data.buffer.asUint8List());
    }

    void writeUint16(int value) {
      final data = ByteData(2)..setUint16(0, value, Endian.little);
      output.add(data.buffer.asUint8List());
    }

    writeAscii('RIFF');
    writeUint32(fileLength);
    writeAscii('WAVE');
    writeAscii('fmt ');
    writeUint32(16);
    writeUint16(1);
    writeUint16(channels);
    writeUint32(sampleRate);
    writeUint32(byteRate);
    writeUint16(blockAlign);
    writeUint16(bitsPerSample);
    writeAscii('data');
    writeUint32(dataLength);
    output.add(pcmBytes);

    return output.takeBytes();
  }

  Future<void> _handleVoiceBytes(
    Uint8List audioBytes, {
    required String fileName,
    double? durationSeconds,
  }) async {
    if (!isLoggedIn || currentPatient == null) {
      showModal(
        'Login Required',
        'Please log in to use OrthoSync AI. Your recovery information is needed to provide personalized postoperative guidance.',
      );
      return;
    }

    final voiceMessage = Message(
      sender: 'user',
      text: '[Voice message]',
      audioBytes: audioBytes,
      audioDurationSeconds: durationSeconds,
    );

    setState(() {
      messages.add(voiceMessage);
      isTyping = true;
      isPlusMenuOpen = false;
    });

    _scrollToBottom();

    try {
      final previousMessages = messages
          .where((msg) => !identical(msg, voiceMessage))
          .toList();

      final historyStart = previousMessages.length > 10
          ? previousMessages.length - 10
          : 0;

      final chatHistory = previousMessages
          .skip(historyStart)
          .map(
            (msg) => {
              'role': msg.sender == 'user' ? 'user' : 'assistant',
              'content': msg.isKey ? (t[msg.text] ?? msg.text) : msg.text,
            },
          )
          .toList();

      final result = await AiBackendService.instance.sendVoiceMessage(
        patient: currentPatient,
        audioBytes: audioBytes,
        fileName: fileName,
        chatHistory: chatHistory,
      );

      if (!mounted) return;

      final transcript = result['transcript']?.toString().trim() ?? '';
      final transcription = result['transcription'];
      final lowConfidence =
          transcription is Map && transcription['low_confidence'] == true;
      final translated =
          transcription is Map && transcription['translated'] == true;
      final botReply =
          result['reply']?.toString() ??
          'I received your voice message, but no response was returned by the local AI service.';

      final userDisplayText = transcript.isEmpty
          ? '[Voice message]'
          : '[Voice message]\n\nYou said: "$transcript"';

      final updatedUserMessage = Message(
        sender: 'user',
        text: userDisplayText,
        audioBytes: audioBytes,
        transcript: transcript,
        audioDurationSeconds: durationSeconds,
      );

      final botMessage = Message(
        sender: 'bot',
        text: botReply,
        triageLevel: result['triage_level']?.toString(),
        isEscalated: result['is_escalated'] == true,
        intent: result['intent']?.toString(),
        targetAgent: result['target_agent']?.toString(),
        action: result['action']?.toString(),
        scopeStatus: result['scope_status']?.toString(),
        sources: result['sources'],
      );

      setState(() {
        final messageIndex = messages.indexOf(voiceMessage);
        if (messageIndex != -1) {
          messages[messageIndex] = updatedUserMessage;
        }
        isTyping = false;
        messages.add(botMessage);
      });

      await _saveMessage(updatedUserMessage);
      await _saveMessage(botMessage);
      _scrollToBottom();

      if (lowConfidence) {
        debugPrint('Voice transcription flagged as low confidence.');
      }
      if (translated) {
        debugPrint('Voice transcription was translated to English.');
      }
    } catch (e) {
      if (!mounted) return;

      final errorMessage = Message(
        sender: 'bot',
        text: 'I received your voice message, but I could not process it right now. Please try recording again or type your message instead. If you are experiencing an emergency, contact your local emergency service or hospital immediately.',
      );

      setState(() {
        isTyping = false;
        messages.add(errorMessage);
      });

      await _saveMessage(voiceMessage);
      await _saveMessage(errorMessage);
      _scrollToBottom();
    }
  }

  Future<void> handleLogin() async {
    _closeMenus();
    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => LoginScreen(isDarkMode: widget.isDarkMode),
      ),
    );

    if (result == true && mounted) {
      final user = AuthService().currentUser;
      setState(() {
        isLoggedIn = true;
        currentPatient = user;
        messages.clear();
        currentConversationIndex = 0;
        selectedConversationIndex = 0;
        isMenuOpen = false;
      });
      if (user != null) {
        await _initializeRecoveryHistory(user);
      }
    }
  }

  Future<void> handleRegister() async {
    _closeMenus();
    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => RegisterScreen(isDarkMode: widget.isDarkMode),
      ),
    );

    if (result == true && mounted) {
      final user = AuthService().currentUser;
      setState(() {
        isLoggedIn = true;
        currentPatient = user;
        messages.clear();
        currentConversationIndex = 0;
        selectedConversationIndex = 0;
        isMenuOpen = false;
      });
      if (user != null) {
        await _initializeRecoveryHistory(user);
      }
    }
  }

  void handleLogout() {
    recoveryDayTimer?.cancel();
    recoveryDayTimer = null;
    recoveryStartAt = null;
    currentRecoveryDay = 1;
    selectedRecoveryDay = 1;
    currentConversationIndex = 0;
    selectedConversationIndex = 0;
    AuthService().logout();
    setState(() {
      isLoggedIn = false;
      currentPatient = null;
      isMenuOpen = false;
      messages.clear();
    });
  }

  @override
  void dispose() {
    recoveryDayTimer?.cancel();
    _voiceAmplitudeTimer?.cancel();
    _voiceMaxDurationTimer?.cancel();
    _inputController.dispose();
    _scrollController.dispose();
    ClipboardEvents.instance?.unregisterPasteEventListener(_onClipboardPaste);
    _audioPlayer.dispose();
    _voiceRecorder.dispose();
    super.dispose();
  }

  void _closeMenus() {
    if (isMenuOpen || isPlusMenuOpen) {
      setState(() {
        isMenuOpen = false;
        isPlusMenuOpen = false;
      });
    }
  }

  void showModal(String title, String content) {
    _closeMenus();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Theme.of(context).cardColor,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text(
          title,
          style: TextStyle(color: Theme.of(context).textTheme.bodyLarge?.color),
        ),
        content: Text(
          content,
          style: TextStyle(
            color: Theme.of(context).textTheme.bodyMedium?.color,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.storage_rounded, color: Color(0xFF38BDF8)),
            tooltip: 'View SQLite DB',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const DbViewerScreen()),
            ),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              t['close'] ?? 'Close',
              style: TextStyle(color: Theme.of(context).primaryColor),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAgentTile(IconData icon, String title, {Color? color}) {
    final theme = Theme.of(context);
    return ListTile(
      leading: Icon(icon, color: color ?? theme.iconTheme.color, size: 22),
      title: Text(
        title,
        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
      ),
      dense: true,
      visualDensity: VisualDensity.compact,
      onTap: () => _selectAgent(title),
    );
  }

  /// Coloured pill badge that identifies which specialized agent responded.
  Widget _agentBadge(String agentName, String? intent) {
    // Map known agent names → accent colour
    final Map<String, Color> agentColors = {
      'MedicationAgent': const Color(0xFF8E44AD),
      'NutritionAgent': const Color(0xFF27AE60),
      'MentalWellbeingAgent': const Color(0xFF1ABC9C),
      'RehabilitationAgent': const Color(0xFF4A90D9),
      'PainSymptomsAgent': const Color(0xFFE74C3C),
      'RecoveryProgressAgent': const Color(0xFFF39C12),
      'WoundCareAgent': const Color(0xFF2980B9),
      'DailyActivityAgent': const Color(0xFF16A085),
    };
    final color = agentColors[agentName] ?? const Color(0xFF607D8B);

    // Shorten display name: "MedicationAgent" → "Medication"
    final display = agentName.replaceAll('Agent', '');

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.smart_toy_outlined, size: 11, color: color),
          const SizedBox(width: 4),
          Text(
            display,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  BoxDecoration _getBackgroundGradient() {
    if (widget.isDarkMode) {
      return const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF10121A), Color(0xFF1A1A2E)],
        ),
      );
    } else {
      return const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFDFDFD), Color(0xFFE8F0FE)],
        ),
      );
    }
  }

  Widget _buildSidebar(ThemeData theme, Color textColor, bool isDesktop) {
    return Container(
      width: isDesktop ? 280 : double.infinity,
      color: isDesktop
          ? theme.cardColor.withValues(alpha: 0.4)
          : theme.cardColor,
      child: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.health_and_safety,
                  color: theme.primaryColor,
                  size: 30,
                ),
                const SizedBox(width: 10),
                Text(
                  'OrthoSync AI',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: textColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Expanded(
              child: isLoggedIn
                  ? ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: () =>
                                _startNewChat(isDesktop: isDesktop),
                            icon: const Icon(Icons.add_rounded, size: 20),
                            label: const Text('New Chat'),
                            style: ElevatedButton.styleFrom(
                              minimumSize: const Size(double.infinity, 44),
                              backgroundColor: theme.primaryColor,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 18),
                        const Text(
                          'Recovery History',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 10),
                        FutureBuilder<List<Map<String, int>>>(
                          future: DatabaseHelper.instance.getChatSessions(
                            currentPatient!.patientId,
                          ),
                          builder: (context, snapshot) {
                            final sessions = <Map<String, int>>[];

                            if (snapshot.hasData) {
                              sessions.addAll(snapshot.data!);
                            }

                            // Always show the currently active empty/new chat.
                            final currentKey =
                                '$currentRecoveryDay:$currentConversationIndex';

                            final hasCurrent = sessions.any(
                              (session) =>
                                  '${session['recovery_day']}:${session['conversation_index']}' ==
                                  currentKey,
                            );

                            if (!hasCurrent) {
                              sessions.insert(0, {
                                'recovery_day': currentRecoveryDay,
                                'conversation_index': currentConversationIndex,
                              });
                            }

                            return Column(
                              children: [
                                for (final session in sessions)
                                  Builder(
                                    builder: (context) {
                                      final day = session['recovery_day'] ?? 1;
                                      final conversationIndex =
                                          session['conversation_index'] ?? 0;
                                      final isSelected =
                                          day == selectedRecoveryDay &&
                                          conversationIndex ==
                                              selectedConversationIndex;

                                      return ListTile(
                                        leading: Icon(
                                          day == currentRecoveryDay
                                              ? Icons.today_rounded
                                              : Icons.history_rounded,
                                          size: 20,
                                          color: isSelected
                                              ? theme.primaryColor
                                              : Colors.grey,
                                        ),
                                        title: Text(
                                          _conversationTitle(
                                            day,
                                            conversationIndex,
                                          ),
                                          style: TextStyle(
                                            fontWeight: isSelected
                                                ? FontWeight.w600
                                                : FontWeight.normal,
                                          ),
                                        ),
                                        subtitle:
                                            day == currentRecoveryDay &&
                                                conversationIndex ==
                                                    currentConversationIndex
                                            ? const Text('Current chat')
                                            : null,
                                        selected: isSelected,
                                        selectedTileColor: theme.dividerColor,
                                        shape: RoundedRectangleBorder(
                                          borderRadius: BorderRadius.circular(
                                            8,
                                          ),
                                        ),
                                        onTap: () => _selectConversation(
                                          day,
                                          conversationIndex,
                                          isDesktop,
                                        ),
                                      );
                                    },
                                  ),
                              ],
                            );
                          },
                        ),
                        const Divider(height: 24),
                        // ── Clinical Report shortcut ──────────────────────
                        ListTile(
                          leading: const Icon(
                            Icons.description_rounded,
                            color: Color(0xFF4A90D9),
                            size: 22,
                          ),
                          title: const Text(
                            'Clinical Report',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          subtitle: const Text(
                            'Summary · PDF download',
                            style: TextStyle(fontSize: 11),
                          ),
                          dense: true,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          onTap: () {
                            if (!isDesktop) Navigator.pop(context);
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => ClinicalReportScreen(
                                  patient: currentPatient,
                                  isDarkMode: widget.isDarkMode,
                                ),
                              ),
                            );
                          },
                        ),
                      ],
                    )
                  : Padding(
                      padding: const EdgeInsets.all(20.0),
                      child: Text(
                        t['authPrompt'] ?? 'Sign in',
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Colors.grey),
                      ),
                    ),
            ),
            if (isLoggedIn)
              MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: () => setState(() => isMenuOpen = !isMenuOpen),
                  child: Container(
                    margin: const EdgeInsets.all(16),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: theme.dividerColor.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      children: [
                        CircleAvatar(
                          backgroundColor: theme.primaryColor,
                          child: Text(
                            (currentPatient?.fullName.isNotEmpty == true)
                                ? currentPatient!.fullName[0].toUpperCase()
                                : "P",
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                "Patient ID: ${currentPatient?.patientId ?? 'B7'}",
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                              Text(
                                "View Profile Menu",
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          Icons.keyboard_arrow_up,
                          color: Colors.grey.shade600,
                          size: 20,
                        ),
                      ],
                    ),
                  ),
                ),
              )
            else
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    ElevatedButton(
                      onPressed: handleLogin,
                      style: ElevatedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 45),
                        backgroundColor: theme.primaryColor,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: Text(
                        t['login'] ?? 'Log in',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    OutlinedButton(
                      onPressed: handleRegister,
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 42),
                        side: BorderSide(
                          color: theme.primaryColor.withValues(alpha: 0.5),
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: Text(
                        t['signup'] ?? 'Sign up',
                        style: TextStyle(
                          color: theme.primaryColor,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textColor = theme.textTheme.bodyLarge?.color ?? Colors.black;
    final isDesktop = MediaQuery.of(context).size.width >= 800;

    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: !isDesktop && !showSplash
          ? AppBar(
              title: const Text(
                'OrthoSync AI',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              centerTitle: true,
            )
          : null,
      drawer: !isDesktop && !showSplash
          ? Drawer(child: _buildSidebar(theme, textColor, isDesktop))
          : null,

      body: GestureDetector(
        onTap: _closeMenus,
        behavior: HitTestBehavior.opaque,
        child: Stack(
          children: [
            Container(decoration: _getBackgroundGradient()),
            if (!showSplash)
              Row(
                children: [
                  if (isDesktop) _buildSidebar(theme, textColor, isDesktop),
                  Expanded(
                    child: Column(
                      children: [
                        Expanded(
                          child: messages.isEmpty
                              ? Center(
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Container(
                                        padding: const EdgeInsets.all(20),
                                        decoration: BoxDecoration(
                                          shape: BoxShape.circle,
                                          color: theme.primaryColor.withValues(
                                            alpha: 0.1,
                                          ),
                                        ),
                                        child: Icon(
                                          Icons.health_and_safety,
                                          size: 60,
                                          color: theme.primaryColor,
                                        ),
                                      ),
                                      const SizedBox(height: 20),
                                      Text(
                                        t['botGreeting'] ?? 'Hello.',
                                        textAlign: TextAlign.center,
                                        style: TextStyle(
                                          fontSize: 22,
                                          fontWeight: FontWeight.w500,
                                          color: textColor,
                                        ),
                                      ),
                                    ],
                                  ),
                                )
                              : ListView.builder(
                                  controller: _scrollController,
                                  padding: const EdgeInsets.all(20),
                                  itemCount:
                                      messages.length + (isTyping ? 1 : 0),
                                  itemBuilder: (context, index) {
                                    if (index == messages.length && isTyping) {
                                      return Align(
                                        alignment: Alignment.centerLeft,
                                        child: Container(
                                          margin: const EdgeInsets.symmetric(
                                            vertical: 10,
                                          ),
                                          child: const Text(
                                            "OrthoSync AI is typing...",
                                            style: TextStyle(
                                              color: Colors.grey,
                                              fontStyle: FontStyle.italic,
                                            ),
                                          ),
                                        ),
                                      );
                                    }
                                    final msg = messages[index];
                                    final isUser = msg.sender == 'user';

                                    return Align(
                                      alignment: isUser
                                          ? Alignment.centerRight
                                          : Alignment.centerLeft,
                                      child: Container(
                                        margin: const EdgeInsets.symmetric(
                                          vertical: 8,
                                        ),
                                        padding: const EdgeInsets.symmetric(
                                          vertical: 14,
                                          horizontal: 18,
                                        ),
                                        decoration: BoxDecoration(
                                          color: isUser
                                              ? theme.primaryColor
                                              : theme.cardColor,
                                          borderRadius:
                                              BorderRadius.circular(
                                                20,
                                              ).copyWith(
                                                bottomRight: isUser
                                                    ? const Radius.circular(5)
                                                    : const Radius.circular(20),
                                                bottomLeft: !isUser
                                                    ? const Radius.circular(5)
                                                    : const Radius.circular(20),
                                              ),
                                        ),
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            if (msg.imageBytes != null ||
                                                msg.imagePath != null)
                                              Padding(
                                                padding: const EdgeInsets.only(
                                                  bottom: 8.0,
                                                ),
                                                child: ClipRRect(
                                                  borderRadius:
                                                      BorderRadius.circular(12),
                                                  child: msg.imageBytes != null
                                                      ? Image.memory(
                                                          msg.imageBytes!,
                                                          height: 150,
                                                          width: 220,
                                                          fit: BoxFit.cover,
                                                        )
                                                      : Image.network(
                                                          msg.imagePath!,
                                                          height: 150,
                                                          width: 220,
                                                          fit: BoxFit.cover,
                                                          errorBuilder:
                                                              (
                                                                context,
                                                                error,
                                                                stackTrace,
                                                              ) => Container(
                                                                height: 150,
                                                                width: 220,
                                                                alignment:
                                                                    Alignment
                                                                        .center,
                                                                color: Colors
                                                                    .black12,
                                                                child: const Icon(
                                                                  Icons
                                                                      .broken_image_outlined,
                                                                  size: 36,
                                                                  color: Colors
                                                                      .grey,
                                                                ),
                                                              ),
                                                        ),
                                                ),
                                              ),

                                            if (!isUser &&
                                                msg.triageLevel != null)
                                              Padding(
                                                padding: const EdgeInsets.only(
                                                  bottom: 6,
                                                ),
                                                child: Text(
                                                  'Triage: ${msg.triageLevel}',
                                                  style: TextStyle(
                                                    fontSize: 12,
                                                    fontWeight: FontWeight.bold,
                                                    color:
                                                        msg.triageLevel == 'RED'
                                                        ? Colors.red
                                                        : msg.triageLevel ==
                                                              'YELLOW'
                                                        ? Colors.orange
                                                        : Colors.green,
                                                  ),
                                                ),
                                              ),

                                            if (!isUser && msg.isEscalated)
                                              Container(
                                                margin: const EdgeInsets.only(
                                                  bottom: 8,
                                                ),
                                                padding: const EdgeInsets.all(
                                                  8,
                                                ),
                                                decoration: BoxDecoration(
                                                  color: Colors.red.withValues(
                                                    alpha: 0.1,
                                                  ),
                                                  borderRadius:
                                                      BorderRadius.circular(8),
                                                ),
                                                child: const Text(
                                                  'Emergency escalation required',
                                                  style: TextStyle(
                                                    color: Colors.red,
                                                    fontWeight: FontWeight.bold,
                                                  ),
                                                ),
                                              ),

                                            // ── Agent badge ──────────────────
                                            if (!isUser &&
                                                msg.targetAgent != null &&
                                                msg.targetAgent!.isNotEmpty)
                                              Padding(
                                                padding: const EdgeInsets.only(
                                                  bottom: 6,
                                                ),
                                                child: Wrap(
                                                  spacing: 6,
                                                  runSpacing: 4,
                                                  children: [
                                                    _agentBadge(
                                                      msg.targetAgent!,
                                                      msg.intent,
                                                    ),
                                                    if (msg.action != null)
                                                      Container(
                                                        padding:
                                                            const EdgeInsets.symmetric(
                                                              horizontal: 7,
                                                              vertical: 2,
                                                            ),
                                                        decoration: BoxDecoration(
                                                          color: Colors.grey
                                                              .withValues(
                                                                alpha: 0.12,
                                                              ),
                                                          borderRadius:
                                                              BorderRadius.circular(
                                                                8,
                                                              ),
                                                        ),
                                                        child: Text(
                                                          msg.action!,
                                                          style:
                                                              const TextStyle(
                                                                fontSize: 10,
                                                                color:
                                                                    Colors.grey,
                                                              ),
                                                        ),
                                                      ),
                                                  ],
                                                ),
                                              ),

                                            if (msg.audioBytes != null)
                                              Padding(
                                                padding: const EdgeInsets.only(
                                                  bottom: 8,
                                                ),
                                                child: Row(
                                                  mainAxisSize:
                                                      MainAxisSize.min,
                                                  children: [
                                                    IconButton(
                                                      visualDensity:
                                                          VisualDensity.compact,
                                                      tooltip:
                                                          'Play voice message',
                                                      onPressed: () async {
                                                        try {
                                                          await _audioPlayer.play(
                                                            UrlSource(
                                                              Uri.dataFromBytes(
                                                                msg.audioBytes!,
                                                                mimeType:
                                                                    'audio/wav',
                                                              ).toString(),
                                                            ),
                                                          );
                                                        } catch (e) {
                                                          debugPrint(
                                                            'Voice playback failed: $e',
                                                          );
                                                        }
                                                      },
                                                      icon: Icon(
                                                        Icons.play_circle_fill,
                                                        color: isUser
                                                            ? Colors.white
                                                            : theme
                                                                  .primaryColor,
                                                        size: 32,
                                                      ),
                                                    ),
                                                    const SizedBox(width: 4),
                                                    Column(
                                                      crossAxisAlignment:
                                                          CrossAxisAlignment
                                                              .start,
                                                      children: [
                                                        Text(
                                                          'Voice message',
                                                          style: TextStyle(
                                                            color: isUser
                                                                ? Colors.white
                                                                : textColor,
                                                            fontWeight:
                                                                FontWeight.w600,
                                                            fontSize: 13,
                                                          ),
                                                        ),
                                                        if (msg.audioDurationSeconds !=
                                                            null)
                                                          Text(
                                                            '${msg.audioDurationSeconds!.toStringAsFixed(1)} s',
                                                            style: TextStyle(
                                                              color: isUser
                                                                  ? Colors
                                                                        .white70
                                                                  : Colors.grey,
                                                              fontSize: 11,
                                                            ),
                                                          ),
                                                      ],
                                                    ),
                                                  ],
                                                ),
                                              ),

                                            SelectableText(
                                              msg.isKey
                                                  ? (t[msg.text] ?? msg.text)
                                                  : msg.text,
                                              style: TextStyle(
                                                color: isUser
                                                    ? Colors.white
                                                    : textColor,
                                                fontSize: 16,
                                              ),
                                            ),

                                            // ── Sources footer ───────────────
                                            if (!isUser &&
                                                msg.sources != null &&
                                                (msg.sources as List?)
                                                        ?.isNotEmpty ==
                                                    true)
                                              Padding(
                                                padding: const EdgeInsets.only(
                                                  top: 8,
                                                ),
                                                child: Wrap(
                                                  spacing: 6,
                                                  runSpacing: 4,
                                                  children: [
                                                    const Icon(
                                                      Icons
                                                          .library_books_outlined,
                                                      size: 12,
                                                      color: Colors.grey,
                                                    ),
                                                    ...(msg.sources as List)
                                                        .take(3)
                                                        .map(
                                                          (src) => Text(
                                                            src.toString(),
                                                            style:
                                                                const TextStyle(
                                                                  fontSize: 10,
                                                                  color: Colors
                                                                      .grey,
                                                                  fontStyle:
                                                                      FontStyle
                                                                          .italic,
                                                                ),
                                                          ),
                                                        ),
                                                  ],
                                                ),
                                              ),
                                          ],
                                        ),
                                      ),
                                    );
                                  },
                                ),
                        ),

                        Container(
                          padding: const EdgeInsets.all(20).copyWith(top: 10),
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: theme.cardColor,
                              border: Border.all(
                                color: theme.dividerColor.withValues(
                                  alpha: 0.5,
                                ),
                              ),
                              borderRadius: BorderRadius.circular(30),
                            ),
                            child: Row(
                              children: [
                                IconButton(
                                  icon: Icon(
                                    Icons.add_circle_outline,
                                    color: textColor,
                                  ),
                                  onPressed: () {
                                    setState(() {
                                      isPlusMenuOpen = !isPlusMenuOpen;
                                      isMenuOpen = false;
                                    });
                                  },
                                ),
                                isRecording
                                    ? Expanded(
                                        child: GestureDetector(
                                          onTap: stopRecording,
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(
                                              vertical: 10,
                                            ),
                                            decoration: BoxDecoration(
                                              color: Colors.red.withValues(
                                                alpha: 0.1,
                                              ),
                                              borderRadius:
                                                  BorderRadius.circular(20),
                                            ),
                                            child: Row(
                                              mainAxisAlignment:
                                                  MainAxisAlignment.center,
                                              children: [
                                                ...audioLevels.map(
                                                  (h) => Container(
                                                    margin:
                                                        const EdgeInsets.symmetric(
                                                          horizontal: 2,
                                                        ),
                                                    width: 3,
                                                    height: h.toDouble(),
                                                    color: Colors.red,
                                                  ),
                                                ),
                                                const SizedBox(width: 10),
                                                Text(
                                                  t['stopRecording'] ?? 'Stop',
                                                  style: const TextStyle(
                                                    color: Colors.red,
                                                    fontWeight: FontWeight.bold,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ),
                                      )
                                    : IconButton(
                                        icon: Icon(
                                          Icons.mic_none,
                                          color: textColor,
                                        ),
                                        onPressed: startRecording,
                                      ),
                                if (!isRecording)
                                  Expanded(
                                    child: TextField(
                                      controller: _inputController,
                                      style: TextStyle(color: textColor),
                                      decoration: InputDecoration(
                                        hintText: t['placeholder'],
                                        hintStyle: const TextStyle(
                                          color: Colors.grey,
                                        ),
                                        border: InputBorder.none,
                                        contentPadding:
                                            const EdgeInsets.symmetric(
                                              horizontal: 10,
                                            ),
                                      ),
                                      onSubmitted: (_) => handleSend(),
                                    ),
                                  ),
                                Container(
                                  decoration: BoxDecoration(
                                    color: theme.primaryColor,
                                    shape: BoxShape.circle,
                                  ),
                                  child: IconButton(
                                    icon: const Icon(
                                      Icons.send,
                                      color: Colors.white,
                                      size: 18,
                                    ),
                                    onPressed: handleSend,
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

            // --- MAIN PROFILE MENU (Added Patient Records Here) ---
            if (isMenuOpen && isLoggedIn)
              Positioned(
                left: isDesktop ? 20 : null,
                right: !isDesktop ? 20 : null,
                bottom: isDesktop ? 90 : 100,
                child: Material(
                  elevation: 15,
                  borderRadius: BorderRadius.circular(20),
                  color: theme.cardColor,
                  child: Container(
                    width: 260,
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        ListTile(
                          leading: Icon(
                            Icons.folder_shared,
                            color: theme.primaryColor,
                          ),
                          title: Text(t['patientRecords'] ?? 'Patient Records'),
                          onTap: _showPatientRecords, // Triggers the new functional modal
                        ),
                        const Divider(),
                        SwitchListTile(
                          title: Text(t['darkTheme'] ?? 'Dark Theme'),
                          value: widget.isDarkMode,
                          onChanged: widget.toggleTheme,
                          secondary: const Icon(Icons.dark_mode),
                        ),
                        ListTile(
                          leading: const Icon(Icons.language),
                          title: DropdownButton<String>(
                            value: lang,
                            isExpanded: true,
                            underline: const SizedBox(),
                            items: ['English', 'Spanish', 'Hindi'].map((
                              String value,
                            ) {
                              return DropdownMenuItem<String>(
                                value: value,
                                child: Text(value),
                              );
                            }).toList(),
                            onChanged: (val) => setState(() => lang = val!),
                          ),
                        ),
                        const Divider(),
                        ListTile(
                          leading: const Icon(
                            Icons.logout,
                            color: Colors.redAccent,
                          ),
                          title: Text(
                            t['logout'] ?? 'Log out',
                            style: const TextStyle(
                              color: Colors.redAccent,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          onTap: handleLogout,
                        ),
                      ],
                    ),
                  ),
                ),
              ),

            // --- EXPANDED SCROLLABLE PLUS MENU ---
            if (isPlusMenuOpen)
              Positioned(
                left: isDesktop ? 300 : 20,
                bottom: 110,
                child: Material(
                  elevation: 15,
                  borderRadius: BorderRadius.circular(20),
                  color: theme.cardColor,
                  child: Container(
                    width: 270,
                    height: 400,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        ListTile(
                          leading: Icon(
                            Icons.camera_alt,
                            color: theme.primaryColor,
                          ),
                          title: Text(t['takePhoto'] ?? 'Take a photo'),
                          visualDensity: VisualDensity.compact,
                          onTap: () => _pickImage(ImageSource.camera),
                        ),
                        ListTile(
                          leading: Icon(
                            Icons.photo_library,
                            color: theme.primaryColor,
                          ),
                          title: Text(t['uploadFiles'] ?? 'Select files'),
                          visualDensity: VisualDensity.compact,
                          onTap: () => _pickImage(ImageSource.gallery),
                        ),
                        ListTile(
                          leading: const Icon(
                            Icons.add_to_drive,
                            color: Colors.green,
                          ),
                          title: Text(t['addDrive'] ?? 'Google Drive'),
                          visualDensity: VisualDensity.compact,
                          onTap: _handleGoogleDrive,
                        ),
                        const Divider(),
                        Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 4,
                          ),
                          child: Text(
                            "Specialized Multi-Agent Pool",
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: theme.primaryColor,
                            ),
                          ),
                        ),
                        Expanded(
                          child: ListView(
                            padding: EdgeInsets.zero,
                            children: [
                              _buildAgentTile(
                                Icons.assignment,
                                "Intake & Context Agent",
                              ),
                              _buildAgentTile(
                                Icons.trending_up,
                                "Recovery Progress Agent",
                              ),
                              _buildAgentTile(
                                Icons.sick,
                                "Symptom Assessment Agent",
                              ),
                              _buildAgentTile(
                                Icons.fitness_center,
                                "Rehabilitation & Exercise Agent",
                              ),
                              _buildAgentTile(
                                Icons.medication,
                                "Medication Adherence Agent",
                              ),
                              _buildAgentTile(
                                Icons.healing,
                                "Wound Care & Imaging Agent",
                              ),
                              _buildAgentTile(
                                Icons.directions_run,
                                "Daily Activity & ADL Agent",
                              ),
                              _buildAgentTile(
                                Icons.restaurant,
                                "Nutrition & Recovery Diet Agent",
                              ),
                              _buildAgentTile(
                                Icons.psychology,
                                "Mental Wellbeing Agent",
                              ),
                              _buildAgentTile(
                                Icons.warning,
                                "Emergency Escalation Agent",
                                color: Colors.redAccent,
                              ),
                              _buildAgentTile(
                                Icons.summarize,
                                "Report Generation Agent",
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

            // --- SMOOTH AUTOMATED ANIMATED SPLASH SCREEN ---
            if (showSplash)
              Container(
                decoration: _getBackgroundGradient(),
                child: Center(
                  child: TweenAnimationBuilder(
                    duration: const Duration(milliseconds: 1200),
                    tween: Tween<double>(begin: 0.5, end: 1.0),
                    curve: Curves.easeOutBack,
                    builder: (context, scale, child) {
                      return Transform.scale(
                        scale: scale,
                        child: Opacity(
                          opacity: scale.clamp(0.0, 1.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                padding: const EdgeInsets.all(30),
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: theme.primaryColor.withValues(
                                    alpha: 0.15,
                                  ),
                                  boxShadow: [
                                    BoxShadow(
                                      color: theme.primaryColor.withValues(
                                        alpha: 0.3,
                                      ),
                                      blurRadius: 30,
                                      spreadRadius: 5,
                                    ),
                                  ],
                                ),
                                child: Icon(
                                  Icons.health_and_safety,
                                  size: 100,
                                  color: theme.primaryColor,
                                ),
                              ),
                              const SizedBox(height: 30),
                              Text(
                                t['splash'] ?? 'Loading...',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.w600,
                                  color: textColor,
                                  letterSpacing: 1.2,
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
