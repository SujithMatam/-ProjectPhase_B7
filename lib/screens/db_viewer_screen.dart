import 'package:flutter/material.dart';
import '../services/database_helper.dart';

class DbViewerScreen extends StatefulWidget {
  const DbViewerScreen({super.key});

  @override
  State<DbViewerScreen> createState() => _DbViewerScreenState();
}

class _DbViewerScreenState extends State<DbViewerScreen> {
  final DatabaseHelper _dbHelper = DatabaseHelper.instance;
  String _selectedTable = 'patients';
  List<Map<String, dynamic>> _records = [];
  bool _isLoading = true;

  final List<String> _tables = ['patients', 'accounts', 'medical_history'];

  @override
  void initState() {
    super.initState();
    _loadTableData(_selectedTable);
  }

  Future<void> _loadTableData(String tableName) async {
    setState(() => _isLoading = true);
    try {
      final data = await _dbHelper.queryTable(tableName);
      setState(() {
        _selectedTable = tableName;
        _records = data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading table: $e')),
        );
      }
    }
  }

  Future<void> _reseedData() async {
    setState(() => _isLoading = true);
    await _dbHelper.clearAndReseed();
    await _loadTableData(_selectedTable);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Database reset and re-seeded with demo data!')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        foregroundColor: Colors.white,
        elevation: 0,
        title: const Row(
          children: [
            Icon(Icons.storage_rounded, color: Color(0xFF38BDF8)),
            SizedBox(width: 8),
            Text(
              'SQLite Database Inspector',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh Data',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => _loadTableData(_selectedTable),
          ),
          IconButton(
            tooltip: 'Reset & Re-seed Demo Data',
            icon: const Icon(Icons.restart_alt_rounded, color: Colors.amber),
            onPressed: _reseedData,
          ),
        ],
      ),
      body: Column(
        children: [
          // Table Selector Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            color: const Color(0xFF1E293B),
            child: Row(
              children: [
                const Text(
                  'Select Table:',
                  style: TextStyle(
                    color: Colors.white70,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(width: 12),
                Wrap(
                  spacing: 8,
                  children: _tables.map((table) {
                    final isSelected = _selectedTable == table;
                    return ChoiceChip(
                      label: Text(table),
                      selected: isSelected,
                      selectedColor: const Color(0xFF0284C7),
                      backgroundColor: const Color(0xFF334155),
                      labelStyle: TextStyle(
                        color: isSelected ? Colors.white : Colors.white70,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      ),
                      onSelected: (selected) {
                        if (selected) _loadTableData(table);
                      },
                    );
                  }).toList(),
                ),
                const Spacer(),
                Text(
                  '${_records.length} row(s)',
                  style: const TextStyle(
                    color: Color(0xFF38BDF8),
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),

          // Content Area
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF38BDF8)))
                : _records.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.folder_open_rounded, size: 64, color: Colors.white24),
                            const SizedBox(height: 12),
                            Text(
                              'No records found in "$_selectedTable"',
                              style: const TextStyle(color: Colors.white54, fontSize: 16),
                            ),
                          ],
                        ),
                      )
                    : SingleChildScrollView(
                        padding: const EdgeInsets.all(16),
                        scrollDirection: Axis.horizontal,
                        child: SingleChildScrollView(
                          child: DataTable(
                            headingRowColor: WidgetStateProperty.all(const Color(0xFF1E293B)),
                            dataRowColor: WidgetStateProperty.resolveWith(
                              (states) => states.contains(WidgetState.hovered)
                                  ? const Color(0xFF1E293B).withOpacity(0.5)
                                  : const Color(0xFF0F172A),
                            ),
                            border: TableBorder.all(
                              color: Colors.white12,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            columns: _records.first.keys.map((key) {
                              return DataColumn(
                                label: Text(
                                  key,
                                  style: const TextStyle(
                                    color: Color(0xFF38BDF8),
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              );
                            }).toList(),
                            rows: _records.map((row) {
                              return DataRow(
                                cells: row.values.map((val) {
                                  return DataCell(
                                    SelectableText(
                                      val?.toString() ?? 'NULL',
                                      style: const TextStyle(color: Colors.white, fontSize: 13),
                                    ),
                                  );
                                }).toList(),
                              );
                            }).toList(),
                          ),
                        ),
                      ),
          ),
        ],
      ),
    );
  }
}
