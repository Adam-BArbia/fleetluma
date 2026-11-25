// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

void downloadCsv(String filename, String contents) {
  final bytes = html.Blob([contents], 'text/csv;charset=utf-8');
  final url = html.Url.createObjectUrlFromBlob(bytes);
  try {
    final anchor = html.AnchorElement(href: url)..download = filename;
    anchor.click();
  } finally {
    html.Url.revokeObjectUrl(url);
  }
}
