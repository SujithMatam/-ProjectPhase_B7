import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:image_picker/image_picker.dart';

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
    'you': 'You',
    'darkTheme': 'Dark Theme',
    'language': 'Language',
    'help': 'Help',
    'logout': 'Log out',
    'uploadFiles': 'Upload file',
    'takePhoto': 'Take photo',
    'addDrive': 'Add from Google Drive',
    'createImage': 'Create image',
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
    'you': 'Tú',
    'darkTheme': 'Tema Oscuro',
    'language': 'Idioma',
    'help': 'Ayuda',
    'logout': 'Cerrar sesión',
    'uploadFiles': 'Subir archivos',
    'takePhoto': 'Tomar foto',
    'addDrive': 'Añadir desde Google Drive',
    'createImage': 'Crear imagen',
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
    'you': 'आप',
    'darkTheme': 'डार्क थीम',
    'language': 'भाषा',
    'help': 'सहायता',
    'logout': 'लॉग आउट',
    'uploadFiles': 'फाइलें अपलोड करें',
    'takePhoto': 'फोटो लें',
    'addDrive': 'Google Drive से जोड़ें',
    'createImage': 'छवि बनाएं',
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

    // Smooth splash screen timer (vanishes automatically after 2.5 seconds)
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

  void handleLogin() {
    setState(() {
      isLoggedIn = true;
      messages.clear();
      widget.toggleTheme(false);
      isMenuOpen = false;
    });
  }

  void handleLogout() {
    setState(() {
      isLoggedIn = false;
      isMenuOpen = false;
      messages.clear();
      widget.toggleTheme(false);
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
                onPressed: () {
                  setState(() => messages.clear());
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
                          child: const Text(
                            "P",
                            style: TextStyle(color: Colors.white),
                          ),
                        ),
                        const SizedBox(width: 10),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                "Patient ID: B7",
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 14,
                                ),
                              ),
                              Text(
                                "Total Knee Arthroplasty",
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              )
            else
              Padding(
                padding: const EdgeInsets.all(16),
                child: ElevatedButton(
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
                            Icons.person,
                            color: theme.primaryColor,
                          ),
                          title: const Text('Avatar'),
                          onTap: () =>
                              showModal('Avatar', 'Current Patient Avatar.'),
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

            // --- PLUS ATTACHMENT MENU (Camera, Files, Google Drive) ---
            if (isPlusMenuOpen)
              Positioned(
                left: isDesktop ? 300 : 20,
                bottom: 110,
                child: Material(
                  elevation: 15,
                  borderRadius: BorderRadius.circular(20),
                  color: theme.cardColor,
                  child: Container(
                    width: 230,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        ListTile(
                          leading: Icon(
                            Icons.camera_alt,
                            color: theme.primaryColor,
                          ),
                          title: Text(t['takePhoto'] ?? 'Take photo'),
                          onTap: () => _pickImage(ImageSource.camera),
                        ),
                        ListTile(
                          leading: Icon(
                            Icons.photo_library,
                            color: theme.primaryColor,
                          ),
                          title: Text(t['uploadFiles'] ?? 'Upload file'),
                          onTap: () => _pickImage(ImageSource.gallery),
                        ),
                        ListTile(
                          leading: Icon(
                            Icons.add_to_drive,
                            color: Colors.green,
                          ),
                          title: Text(t['addDrive'] ?? 'Google Drive'),
                          onTap: _handleGoogleDrive,
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
