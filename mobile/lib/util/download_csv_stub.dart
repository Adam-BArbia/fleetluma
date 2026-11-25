/// Not called in Android UI; the export widget is Web-only.
void downloadCsv(String filename, String contents) {
  throw UnsupportedError('CSV download is only available in Web mode');
}
