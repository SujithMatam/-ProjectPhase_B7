import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:image_picker/image_picker.dart';

import 'models/patient_user.dart';
import 'services/auth_service.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/db_viewer_screen.dart';
import 'services/database_helper.dart';

void main() {
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
  const OrthoSyncApp({Key? key}) : super(key: key);

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
        cardColor: Colors.white.withOpacity(0.9),
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
        cardColor: const Color(0xFF2A2D3E).withOpacity(0.9),
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
  Message({
    required this.sender,
    required this.text,
    this.isKey = false,
    this.imagePath,
  });
}

class MainScreen extends StatefulWidget {
  final Function(bool) toggleTheme;
  final bool isDarkMode;
  const MainScreen({
    Key? key,
    required this.toggleTheme,
    required this.isDarkMode,
  }) : super(key: key);

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

  List<Message> messages = [];
  List<int> audioLevels = [10, 15, 20, 12, 18, 25, 15, 10];
  Timer? waveTimer;

  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final ImagePicker _picker = ImagePicker();

  Map<String, String> get t => uiText[lang] ?? uiText['English']!;

  @override
  void initState() {
    super.initState();
    _playStartupSound();

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

  Future<void> _pickImage(ImageSource source) async {
    setState(() => isPlusMenuOpen = false);
    try {
      final XFile? image = await _picker.pickImage(source: source);
      if (image != null) {
        setState(() {
          messages.add(
            Message(
              sender: 'user',
              text: "Uploaded an image",
              imagePath: image.path,
            ),
          );
          isTyping = true;
        });
        _scrollToBottom();

        Future.delayed(const Duration(milliseconds: 1500), () {
          if (mounted) {
            setState(() {
              isTyping = false;
              messages.add(
                Message(sender: 'bot', text: 'botAuthReply', isKey: true),
              );
            });
            _scrollToBottom();
          }
        });
      }
    } catch (e) {
      showModal("Camera Error", "Ensure camera permissions are granted.");
    }
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

  void handleSend() {
    if (_inputController.text.trim().isEmpty) return;
    setState(() {
      messages.add(Message(sender: 'user', text: _inputController.text));
      _inputController.clear();
      isTyping = true;
    });
    Future.delayed(const Duration(milliseconds: 100), _scrollToBottom);
    Future.delayed(const Duration(milliseconds: 1500), () {
      if (mounted) {
        setState(() {
          isTyping = false;
          messages.add(
            Message(
              sender: 'bot',
              text: isLoggedIn ? 'botAuthReply' : 'botGreeting',
              isKey: true,
            ),
          );
        });
        _scrollToBottom();
      }
    });
  }

  void startRecording() {
    setState(() => isRecording = true);
    waveTimer = Timer.periodic(const Duration(milliseconds: 150), (timer) {
      setState(() {
        audioLevels = List.generate(10, (index) => Random().nextInt(20) + 5);
      });
    });
  }

  void stopRecording() {
    waveTimer?.cancel();
    setState(() {
      isRecording = false;
      messages.add(Message(sender: 'user', text: "[Voice Note Attached]"));
      isTyping = true;
    });
    Future.delayed(const Duration(milliseconds: 1500), () {
      if (mounted) {
        setState(() {
          isTyping = false;
          messages.add(
            Message(sender: 'bot', text: 'botVoiceReply', isKey: true),
          );
        });
        _scrollToBottom();
      }
    });
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
        isMenuOpen = false;
      });
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
        isMenuOpen = false;
      });
    }
  }

  void handleLogout() {
    AuthService().logout();
    setState(() {
      isLoggedIn = false;
      currentPatient = null;
      isMenuOpen = false;
      messages.clear();
    });
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
      color: isDesktop ? theme.cardColor.withOpacity(0.4) : theme.cardColor,
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
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: ElevatedButton.icon(
                // --- FUNCTIONAL NEW CHECK-IN ---
                onPressed: () {
                  setState(() {
                    messages.clear();
                    messages.add(
                      Message(
                        sender: 'bot',
                        text: 'newCheckinPrompt',
                        isKey: true,
                      ),
                    );
                  });
                  if (!isDesktop) Navigator.pop(context);
                },
                icon: const Icon(Icons.add),
                label: Text(t['newCheckin'] ?? 'New Check-in'),
                style: ElevatedButton.styleFrom(
                  foregroundColor: textColor,
                  backgroundColor: Colors.transparent,
                  elevation: 0,
                  side: BorderSide(color: theme.dividerColor),
                  minimumSize: const Size(double.infinity, 45),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
            Expanded(
              child: isLoggedIn
                  ? ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        Text(
                          t['recent'] ?? 'Recent',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.grey,
                          ),
                        ),
                        const SizedBox(height: 10),
                        ListTile(
                          title: const Text("Post-op Day 3"),
                          selectedTileColor: theme.dividerColor,
                          selected: true,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        ListTile(
                          title: const Text("Post-op Day 2"),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
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
                      color: theme.dividerColor.withOpacity(0.3),
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
                          color: theme.primaryColor.withOpacity(0.5),
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
                                          color: theme.primaryColor.withOpacity(
                                            0.1,
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
                                            if (msg.imagePath != null)
                                              Padding(
                                                padding: const EdgeInsets.only(
                                                  bottom: 8.0,
                                                ),
                                                child: ClipRRect(
                                                  borderRadius:
                                                      BorderRadius.circular(12),
                                                  child: Image.network(
                                                    msg.imagePath!,
                                                    height: 150,
                                                    fit: BoxFit.cover,
                                                  ),
                                                ),
                                              ),
                                            Text(
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
                                color: theme.dividerColor.withOpacity(0.5),
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
                                              color: Colors.red.withOpacity(
                                                0.1,
                                              ),
                                              borderRadius:
                                                  BorderRadius.circular(20),
                                            ),
                                            child: Row(
                                              mainAxisAlignment:
                                                  MainAxisAlignment.center,
                                              children: [
                                                ...audioLevels
                                                    .map(
                                                      (h) => Container(
                                                        margin:
                                                            const EdgeInsets.symmetric(
                                                              horizontal: 2,
                                                            ),
                                                        width: 3,
                                                        height: h.toDouble(),
                                                        color: Colors.red,
                                                      ),
                                                    )
                                                    .toList(),
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
                                  color: theme.primaryColor.withOpacity(0.15),
                                  boxShadow: [
                                    BoxShadow(
                                      color: theme.primaryColor.withOpacity(
                                        0.3,
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
