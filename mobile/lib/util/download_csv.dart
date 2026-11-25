import 'download_csv_stub.dart'
    if (dart.library.html) 'download_csv_web.dart' as platform;

void downloadCsv(String filename, String contents) =>
    platform.downloadCsv(filename, contents);
