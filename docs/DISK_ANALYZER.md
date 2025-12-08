# Disk Analyzer Module

## Overview

The Disk Analyzer module is an integrated feature of the AI Infrastructure Monitor that helps users identify and safely clean up disk space. It provides intelligent analysis of disk usage and offers safe cleanup options with backup capabilities.

## Features

### 🔍 Disk Scanning

- **Comprehensive Analysis**: Scans multiple categories of files that can be safely cleaned
- **Background Processing**: Scans run asynchronously without blocking the UI
- **Detailed Reporting**: Shows file counts and sizes for each category

### 🗂️ Cleanup Categories

The system analyzes the following categories:

1. **Temporary Files** (Low Risk)

   - Windows temp directories
   - User temp folders
   - Files older than 7 days
   - Safe for automatic cleanup

2. **Browser Cache** (Low Risk)

   - Chrome, Edge, Firefox cache
   - Safe for automatic cleanup
   - May slow down browser initially after cleanup

3. **Recycle Bin** (Low Risk)

   - Files in Windows Recycle Bin
   - Requires user review before cleanup

4. **Windows Update Cache** (Low Risk)

   - Old Windows Update files
   - Files older than 30 days
   - Safe for automatic cleanup

5. **Old Installers** (Medium Risk)

   - .msi, .exe files in Downloads
   - Files older than 30 days
   - Requires user review

6. **Thumbnail Cache** (Low Risk)

   - Windows thumbnail database
   - Safe for automatic cleanup

7. **Development Cache** (High Risk)
   - node_modules, **pycache**, .cache
   - Requires careful review
   - Can be regenerated but takes time

### 🛡️ Safety Features

1. **Automatic Backup**

   - All files are backed up before deletion
   - Backups stored in `C:\Users\[USER]\.ai-infra-monitor\cleanup_backup\`
   - Backups retained for 30 days
   - Rollback capability (future feature)

2. **Protected Paths**

   - System directories are never touched
   - User documents, pictures, videos protected
   - Program Files protected

3. **Risk Levels**

   - Each category has a risk level (low, medium, high)
   - Visual indicators in the UI
   - Safe categories can be auto-cleaned

4. **Confirmation Required**
   - User must explicitly select categories
   - Confirmation dialog before cleanup
   - Shows what will be deleted

## Architecture

### Backend Components

```
backend/
├── disk_analyzer/
│   ├── __init__.py
│   ├── rules.py          # Cleanup rules and categories
│   ├── scanner.py        # Disk scanning logic
│   └── cleaner.py        # Cleanup and backup logic
├── api/
│   ├── models/
│   │   └── disk_analyzer.py  # Pydantic models
│   └── routes/
│       └── disk_analyzer.py  # API endpoints
└── db/
    └── schema.sql        # Database tables
```

### Database Schema

**disk_scans**

- Stores scan results and metadata
- Tracks scan status (pending, running, completed, failed)
- Stores categories as JSONB

**cleanup_operations**

- Records cleanup operations
- Tracks files deleted and space freed
- Stores backup path

**cleanup_items**

- Individual files identified for cleanup
- Linked to scan_id
- Includes risk level and safety flag

### Frontend Components

```
dashboard/src/pages/
├── DiskAnalyzer.jsx      # Main component
└── DiskAnalyzer.css      # Styles
```

## API Endpoints

### Start Scan

```
POST /api/v1/disk-analyzer/scan
Body: { "host_id": 1 }
Response: { "ok": true, "scan_id": 123, "status": "pending" }
```

### Get Scan Results

```
GET /api/v1/disk-analyzer/scan/{scan_id}
Response: {
  "scan_id": 123,
  "status": "completed",
  "total_size": 5368709120,
  "categories": { ... }
}
```

### List Scans

```
GET /api/v1/disk-analyzer/scans?host_id=1&limit=10
Response: { "scans": [...], "total": 5 }
```

### Perform Cleanup

```
POST /api/v1/disk-analyzer/cleanup
Body: {
  "scan_id": 123,
  "categories": ["temp_files", "browser_cache"],
  "create_backup": true
}
Response: {
  "ok": true,
  "operation_id": 456,
  "files_deleted": 1234,
  "size_freed": 1073741824,
  "backup_path": "C:\\Users\\...\\cleanup_backup\\..."
}
```

### List Cleanup Operations

```
GET /api/v1/disk-analyzer/cleanups?scan_id=123&limit=10
Response: { "operations": [...], "total": 3 }
```

## Usage Guide

### For Users

1. **Navigate to Disk Analyzer**

   - Click "Disk Analyzer" in the navigation menu

2. **Start a Scan**

   - Click "Start New Scan" button
   - Wait for scan to complete (may take a few minutes)

3. **Review Results**

   - See categories with file counts and sizes
   - Check risk levels (green = low, yellow = medium, red = high)
   - Read descriptions for each category

4. **Select Categories to Clean**

   - Click on category cards to select them
   - Selected cards will be highlighted
   - Review the total space that will be freed

5. **Perform Cleanup**

   - Click "Clean Selected" button
   - Confirm the operation
   - Wait for cleanup to complete
   - Review the results (files deleted, space freed, backup location)

6. **View History**
   - Scroll down to see previous scans
   - Click on a scan to view its details

### For Developers

#### Adding New Cleanup Categories

1. **Define the category in `rules.py`**:

```python
def get_my_custom_cache() -> List[str]:
    # Return list of paths to scan
    return [r"C:\MyApp\Cache"]

CLEANUP_CATEGORIES['my_cache'] = CleanupCategory(
    name='my_cache',
    display_name='My Custom Cache',
    description='Cache files from My App',
    risk_level='low',
    is_safe_auto=True,
    get_paths=get_my_custom_cache
)
```

2. **Add scanning logic in `scanner.py`**:

```python
def _scan_my_cache(self, base_path: str) -> List[Dict]:
    # Implement scanning logic
    files = []
    # ... scan files ...
    return files
```

3. **Update the scanner's `_scan_category` method** to handle the new category

#### Running Tests

```bash
# Test disk scanner
python -c "from backend.disk_analyzer.scanner import DiskScanner; s = DiskScanner(1); print(s.scan_all_categories())"

# Test cleanup (dry run)
# Implement test in backend/tests/
```

## Configuration

### Environment Variables

No additional environment variables required. Uses existing database configuration.

### Backup Settings

- **Backup Location**: `C:\Users\[USER]\.ai-infra-monitor\cleanup_backup\`
- **Retention Period**: 30 days (configurable in cleaner.py)
- **Auto-cleanup**: Old backups are automatically removed

### Scan Settings

- **Max Depth**: Limited to prevent excessive scanning
- **File Age Threshold**:
  - Temp files: 7 days
  - Installers: 30 days
  - Windows Update: 30 days
- **Max Files per Category**: 100 (for performance)

## Security Considerations

1. **Protected Directories**: System directories are blacklisted
2. **File Patterns**: Important file types are protected
3. **Permissions**: Respects file system permissions
4. **Backup First**: Always creates backup before deletion
5. **Explicit Confirmation**: User must confirm cleanup

## Troubleshooting

### Scan Fails

**Issue**: Scan status shows "failed"

**Solutions**:

- Check if agent has sufficient permissions
- Review error message in scan details
- Ensure disk is accessible
- Check database connectivity

### Cleanup Doesn't Free Expected Space

**Issue**: Less space freed than expected

**Possible Causes**:

- Files in use cannot be deleted
- Permission denied on some files
- Files already deleted by another process

**Solution**:

- Review cleanup operation errors
- Check backup folder for what was actually deleted
- Run scan again to see updated results

### Permission Errors

**Issue**: "Permission denied" errors during scan or cleanup

**Solution**:

- Run the backend with administrator privileges
- Exclude directories you don't have access to
- Check Windows file permissions

## Future Enhancements

- [ ] Rollback functionality (restore from backup)
- [ ] Scheduled automatic scans
- [ ] Email notifications for low disk space
- [ ] Duplicate file detection
- [ ] Large file finder (files >1GB)
- [ ] AI-powered recommendations
- [ ] Compression instead of deletion option
- [ ] Cloud backup integration

## Performance

- **Scan Time**: 2-5 minutes for typical system
- **Cleanup Time**: 30 seconds - 2 minutes depending on file count
- **Database Impact**: Minimal (background tasks)
- **Memory Usage**: ~100-200 MB during scan

## Limitations

- Windows only (currently)
- Cannot clean files in use
- Cannot access encrypted/protected files
- Limited to local disks (no network drives)
- Recycle Bin size estimation may be approximate

## Support

For issues or questions:

1. Check logs in backend console
2. Review scan/cleanup error messages
3. Check database for operation history
4. Consult main project README

## License

Same as main project (AI Infrastructure Monitor)
