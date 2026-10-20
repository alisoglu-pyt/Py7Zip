"""Very small translation layer (Turkish / English).

Usage::

    from .i18n import I18N
    i18n = I18N("tr")
    i18n.t("menu.file.open")
    i18n.t("status.items", count=12)
"""

from __future__ import annotations

import gettext
from typing import Any

LANGUAGES = {
    "tr": "Türkçe",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "pt": "Português",
    "zh": "中文",
    "ko": "한국어",
    "az": "Azərbaycanca",
    "tk": "Türkmençe",
}

# fmt: off
TRANSLATIONS: dict[str, dict[str, str]] = {
    "tr": {
        "app.name": "Py7-Zip",
        "app.tagline": "Modern arşiv yöneticisi",
        "app.archive_manager": "Arşiv Yöneticisi",

        # Menus
        "menu.file": "Dosya",
        "menu.file.open": "Arşiv Aç…",
        "menu.file.create": "Yeni Arşiv…",
        "menu.file.extract": "Çıkar…",
        "menu.file.add": "Arşive Ekle…",
        "menu.file.delete": "Arşivden Sil",
        "menu.file.test": "Arşivi Test Et",
        "menu.file.properties": "Özellikler",
        "menu.file.close_archive": "Arşivi Kapat",
        "menu.file.add_files": "Dosya Ekle…",
        "menu.file.add_folder": "Klasör Ekle…",
        "menu.file.recent": "Son Kullanılanlar",
        "menu.file.clear_recent": "Listeyi Temizle",
        "menu.file.exit": "Çıkış",
        "menu.edit": "Düzen",
        "menu.edit.select_all": "Tümünü Seç",
        "menu.edit.deselect": "Seçimi Kaldır",
        "menu.edit.invert": "Seçimi Ters Çevir",
        "menu.edit.find": "Ara…",
        "menu.edit.settings": "Ayarlar…",
        "menu.view": "Görünüm",
        "menu.view.refresh": "Yenile",
        "menu.view.up": "Üst Klasör",
        "menu.view.back": "Geri",
        "menu.view.forward": "İleri",
        "menu.view.preview": "Önizleme Paneli",
        "menu.view.sidebar": "Kenar Çubuğu",
        "menu.view.dark": "Koyu Tema",
        "menu.view.light": "Açık Tema",
        "menu.view.language": "Dil",
        "menu.tools": "Araçlar",
        "menu.tools.settings": "Ayarlar…",
        "menu.tools.new_window": "Yeni Pencere",
        "menu.help": "Yardım",
        "menu.help.shortcuts": "Klavye Kısayolları",
        "menu.help.about": "Hakkında",

        # Toolbar
        "toolbar.open": "Aç",
        "toolbar.create": "Yeni",
        "toolbar.extract": "Çıkar",
        "toolbar.add": "Ekle",
        "toolbar.delete": "Sil",
        "toolbar.test": "Test",
        "toolbar.up": "Üst",
        "toolbar.refresh": "Yenile",
        "toolbar.preview": "Önizle",
        "toolbar.info": "Bilgi",
        "toolbar.settings": "Ayarlar",
        "toolbar.back": "Geri",
        "toolbar.forward": "İleri",

        # Path / navigation
        "path.current": "Konum:",
        "path.placeholder": "Bir klasör yolu yazın veya arşiv açın…",
        "path.this_pc": "Bu Bilgisayar",
        "path.root": "Kök",
        "search.placeholder": "Ara…",

        # Columns
        "col.name": "Ad",
        "col.size": "Boyut",
        "col.packed": "Sıkıştırılmış",
        "col.ratio": "Oran",
        "col.modified": "Değiştirilme",
        "col.crc": "CRC",
        "col.method": "Yöntem",
        "col.type": "Tür",

        # Types
        "type.folder": "Klasör",
        "type.file": "Dosya",
        "type.archive": "Arşiv",
        "type.symlink": "Bağlantı",
        "type.parent": "Üst klasör",
        "type.split": "Parçalı",

        # Status bar
        "status.items": "{count} öğe",
        "status.selected": "{count} seçili",
        "status.selected_size": "Seçili: {size}",
        "status.ready": "Hazır",
        "status.working": "İşlem sürüyor…",
        "status.cancelled": "İptal edildi",
        "status.archive": "Arşiv: {name}",
        "status.folder": "Klasör",
        "status.opening": "Açılıyor…",
        "status.extracting": "Çıkarılıyor…",
        "status.creating": "Arşiv oluşturuluyor…",
        "status.adding": "Ekleniyor…",
        "status.deleting": "Siliniyor…",
        "status.testing": "Test ediliyor…",
        "status.done": "Tamamlandı",
        "status.filtered": "{count} / {total} öğe (filtreli)",

        # Progress window
        "progress.title": "İşlem sürüyor",
        "progress.wait": "Lütfen bekleyin…",
        "progress.completed": "Tamamlandı",
        "progress.cancelling": "İptal ediliyor…",
        "progress.phase.extract": "Çıkarılıyor…",
        "progress.phase.delete": "Siliniyor…",
        "progress.phase.add": "Ekleniyor…",
        "progress.phase.rebuild": "Yeniden oluşturuluyor…",
        "progress.phase.split": "Parçalara bölünüyor…",

        # Generic buttons
        "btn.ok": "Tamam",
        "btn.cancel": "İptal",
        "btn.close": "Kapat",
        "btn.browse": "Gözat…",
        "btn.extract": "Çıkar",
        "btn.create": "Oluştur",
        "btn.add": "Ekle",
        "btn.delete": "Sil",
        "btn.open": "Aç",
        "btn.save": "Kaydet",
        "btn.apply": "Uygula",
        "btn.yes": "Evet",
        "btn.no": "Hayır",
        "btn.select_all": "Tümünü Seç",
        "btn.clear": "Temizle",
        "btn.paste": "Yapıştır",

        # Dialogs - create archive
        "dlg.create.title": "Yeni Arşiv Oluştur",
        "dlg.create.header": "Yeni arşiv",
        "dlg.create.archive_name": "Arşiv adı:",
        "dlg.create.location": "Konum:",
        "dlg.create.format": "Arşiv biçimi:",
        "dlg.create.level": "Sıkıştırma düzeyi:",
        "dlg.create.method": "Sıkıştırma yöntemi:",
        "dlg.create.password": "Parola:",
        "dlg.create.password_confirm": "Parola (tekrar):",
        "dlg.create.encrypt_header": "Dosya adlarını da şifrele",
        "dlg.create.source": "Eklenecek öğeler:",
        "dlg.create.default_name": "Arsiv",
        "dlg.create.password_mismatch": "Parolalar eşleşmiyor.",
        "dlg.create.name_required": "Lütfen bir arşiv adı girin.",
        "dlg.create.no_source": "Eklenecek öğe seçilmedi.",
        "dlg.create.exists": "Bu dosya zaten var. Üzerine yazılsın mı?",
        "dlg.create.summary": "{count} öğe seçildi",
        "dlg.create.output": "Oluşturulacak dosya:",
        "dlg.create.zip_note": "Parola yalnızca 7z biçiminde desteklenir.",
        "dlg.create.single_note": "Bu biçim yalnızca tek bir dosya sıkıştırır.",
        "dlg.create.split": "Parçalara böl (çoklu cilt)",
        "dlg.create.part_size": "Parça boyutu:",
        "dlg.create.part_example": "ör. arsiv.7z.001, .002, …",
        "dlg.create.part_invalid": "Parça boyutu en az 1 MB olmalı.",
        "unit.mb": "MB",
        "unit.gb": "GB",
        "status.splitting": "Parçalara bölünüyor…",

        # Dialogs - extract
        "dlg.extract.title": "Arşivi Çıkar",
        "dlg.extract.header": "Çıkarma",
        "dlg.extract.destination": "Hedef klasör:",
        "dlg.extract.all": "Tüm dosyalar",
        "dlg.extract.selected": "Yalnızca seçilenler",
        "dlg.extract.overwrite": "Var olan dosyaların üzerine yaz",
        "dlg.extract.use_subfolder": "Arşiv adıyla alt klasör oluştur",
        "dlg.extract.password": "Parola (gerekirse):",
        "dlg.extract.pick_archive": "Çıkarılacak arşivi seç",
        "dlg.extract.no_dest": "Lütfen bir hedef klasör seçin.",
        "dlg.extract.archive": "Arşiv:",
        "dlg.extract.selected_count": "Seçili: {count} / {total}",

        # Dialogs - settings
        "dlg.settings.title": "Ayarlar",
        "dlg.settings.header": "Ayarlar",
        "dlg.settings.general": "Genel",
        "dlg.settings.appearance": "Görünüm",
        "dlg.settings.archives": "Arşivler",
        "dlg.settings.language": "Arayüz dili:",
        "dlg.settings.theme": "Tema:",
        "dlg.settings.show_hidden": "Gizli dosyaları göster",
        "dlg.settings.confirm_delete": "Arşivden silmeden önce onay iste",
        "dlg.settings.preview": "Önizleme panelini etkinleştir",
        "dlg.settings.default_extract": "Varsayılan çıkarma klasörü:",
        "dlg.settings.compression": "Varsayılan sıkıştırma düzeyi:",
        "dlg.settings.saved": "Ayarlar kaydedildi.",
        "dlg.settings.restart_hint": "Dil değişikliği hemen uygulanır.",

        # Dialogs - password
        "dlg.password.title": "Parola Gerekli",
        "dlg.password.header": "Parola gerekli",
        "dlg.password.hint": "Bu arşiv parola ile korunuyor. Lütfen parolayı girin.",
        "dlg.password.label": "Parola:",
        "dlg.password.empty": "Parola boş olamaz.",
        "dlg.password.wrong": "Parola yanlış veya arşiv bozuk.",

        # Dialogs - properties
        "dlg.properties.title": "Özellikler",
        "dlg.properties.header": "Özellikler",
        "dlg.properties.file": "Dosya",
        "dlg.properties.format": "Biçim",
        "dlg.properties.entries": "Öğe sayısı",
        "dlg.properties.size": "Açılmış boyut",
        "dlg.properties.packed": "Sıkıştırılmış boyut",
        "dlg.properties.ratio": "Sıkıştırma oranı",
        "dlg.properties.methods": "Yöntemler",
        "dlg.properties.encrypted": "Şifreli",
        "dlg.properties.path": "Konum",
        "dlg.properties.modified": "Değiştirilme",
        "dlg.properties.type": "Tür",
        "dlg.properties.name": "Ad",
        "dlg.properties.yes": "Evet",
        "dlg.properties.no": "Hayır",

        # Dialogs - about / shortcuts
        "dlg.about.title": "Py7-Zip Hakkında",
        "dlg.about.description": (
            "Py7-Zip, 7-Zip'in C++ çekirdeğinden esinlenilerek Python ve "
            "Tkinter ile yeniden yazılmış modern bir arşiv yöneticisidir.\n\n"
            "Arşiv motoru: py7zr + Python standart kütüphanesi\n"
            "Desteklenen biçimler: 7z, zip, tar, tar.gz, tar.bz2, tar.xz, "
            "gz, bz2, xz\n"
            "Lisans: LGPL-2.1"
        ),
        "dlg.about.version": "Sürüm {version}",
        "dlg.about.author": (
            "Programlayan: Bekir Alişoğlu\n"
            "E-posta: alisoglu@yahoo.com"
        ),
        "dlg.shortcuts.title": "Klavye Kısayolları",
        "dlg.shortcuts.text": (
            "Ctrl+O   Arşiv aç\n"
            "Ctrl+N   Yeni arşiv\n"
            "Ctrl+E   Çıkar\n"
            "Ctrl+A   Tümünü seç\n"
            "Ctrl+F   Ara\n"
            "F5       Yenile\n"
            "Backspace Üst klasör\n"
            "Enter    Aç / içine gir\n"
            "Delete   Arşivden sil\n"
            "Alt+Enter Özellikler\n"
            "Ctrl+Q   Çıkış"
        ),

        # Messages
        "msg.error": "Hata",
        "msg.warning": "Uyarı",
        "msg.info": "Bilgi",
        "msg.confirm": "Onay",
        "msg.password_required": "Bu arşiv parola ile korunuyor.",
        "msg.invalid_archive": "Geçersiz veya desteklenmeyen arşiv.",
        "msg.archive_exists": "Arşiv zaten var. Üzerine yazılsın mı?",
        "msg.confirm_delete": "Seçili {count} öğe arşivden silinsin mi?",
        "msg.confirm_delete_many": "Seçili öğeler arşivden silinsin mi?",
        "msg.no_selection": "Lütfen en az bir öğe seçin.",
        "msg.done": "İşlem tamamlandı.",
        "msg.unsupported": "Bu işlem bu arşiv biçimi için desteklenmiyor.",
        "msg.unsupported_format": "Desteklenmeyen arşiv biçimi: {fmt}",
        "msg.create_success": "Arşiv oluşturuldu:\n{path}",
        "msg.extract_success": "Dosyalar çıkarıldı:\n{path}",
        "msg.add_success": "Öğeler arşive eklendi.",
        "msg.delete_success": "Öğeler arşivden silindi.",
        "msg.test_ok": "Arşiv sağlam. Hata bulunamadı.",
        "msg.test_failed": "Arşiv testi başarısız:\n{detail}",
        "msg.read_error": "Dosya okunamadı:\n{detail}",
        "msg.write_error": "Dosya yazılamadı:\n{detail}",
        "msg.extract_error": "Çıkarma başarısız:\n{detail}",
        "msg.create_error": "Arşiv oluşturulamadı:\n{detail}",
        "msg.add_error": "Ekleme başarısız:\n{detail}",
        "msg.delete_error": "Silme başarısız:\n{detail}",
        "msg.open_error": "Dosya açılamadı:\n{detail}",
        "msg.zip_password_unsupported": (
            "Zip arşivleri yazılırken parola ile şifrelenemez. "
            "Parola yalnızca 7z biçimi için kullanılabilir."
        ),
        "msg.single_file_only": (
            "gz, bz2 ve xz biçimleri yalnızca tek bir dosya sıkıştırabilir."
        ),
        "msg.temp_dir_error": "Geçici klasör oluşturulamadı:\n{detail}",
        "msg.file_missing": "Dosya bulunamadı:\n{path}",
        "msg.copy_failed": "Kopyalama başarısız:\n{detail}",
        "msg.preview_binary": "Bu dosya ikili (binary) içerik barındırıyor; metin önizlemesi gösterilemiyor.",
        "msg.preview_too_large": "Dosya önizleme için çok büyük ({size}).",
        "msg.preview_unavailable": "Önizleme kullanılamıyor.",
        "msg.filter_prompt": "Arama metni:",
        "msg.filter_empty": "Arama metni boş.",
        "msg.cancel": "İptal",
        "msg.overwrite": "Üzerine Yaz",
        "msg.skip": "Atla",
        "msg.overwrite_title": "Dosyalar zaten var",
        "msg.overwrite_text": "Hedef klasörde aynı adlı dosyalar var. Ne yapılsın?",
        "msg.open_with": "Birlikte aç",
        "msg.not_archive": "Bu bir arşiv dosyası değil.",
        "msg.no_password_needed": "Bu arşiv parola gerektirmiyor.",
        "msg.operation_cancelled": "İşlem iptal edildi.",
        "msg.close_archive": "Arşivi kapat",
        "msg.select_archive_first": "Önce bir arşiv seçin veya açın.",
        "msg.no_archive_open": "Açık bir arşiv yok.",
        "msg.nothing_to_extract": "Çıkarılacak öğe yok.",
        "msg.nothing_to_delete": "Silinecek öğe yok.",
        "msg.split_modify_unsupported": (
            "Parçalı arşivlerde ekleme/silme desteklenmiyor. "
            "Önce parçaları birleştirin."
        ),

        # Compression levels
        "level.0": "0 - Yalnızca sakla",
        "level.1": "1 - En hızlı",
        "level.3": "3 - Hızlı",
        "level.5": "5 - Normal",
        "level.7": "7 - Yüksek",
        "level.9": "9 - Ultra",
        "level.custom": "Özel",

        # Preview
        "preview.title": "Önizleme",
        "preview.no_selection": "Önizlemek için bir dosya seçin.",
        "preview.open_external": "Harici uygulamayla aç",
        "preview.extract": "Çıkar",
        "preview.loading": "Yükleniyor…",
        "preview.image": "Görsel önizleme",
        "preview.text": "Metin önizleme",
        "preview.info": "Bilgi",

        # Misc
        "misc.folder": "Klasör",
        "misc.file": "Dosya",
        "misc.bytes": "B",
        "misc.kb": "KB",
        "misc.mb": "MB",
        "misc.gb": "GB",
        "misc.tb": "TB",
        "misc.unknown": "—",
        "misc.search": "Ara",
        "misc.cancel": "İptal",
    },
    "en": {
        "app.name": "Py7-Zip",
        "app.tagline": "Modern archive manager",
        "app.archive_manager": "Archive Manager",

        "menu.file": "File",
        "menu.file.open": "Open Archive…",
        "menu.file.create": "New Archive…",
        "menu.file.extract": "Extract…",
        "menu.file.add": "Add to Archive…",
        "menu.file.delete": "Delete from Archive",
        "menu.file.test": "Test Archive",
        "menu.file.properties": "Properties",
        "menu.file.close_archive": "Close Archive",
        "menu.file.add_files": "Add Files…",
        "menu.file.add_folder": "Add Folder…",
        "menu.file.recent": "Recent Files",
        "menu.file.clear_recent": "Clear List",
        "menu.file.exit": "Exit",
        "menu.edit": "Edit",
        "menu.edit.select_all": "Select All",
        "menu.edit.deselect": "Deselect",
        "menu.edit.invert": "Invert Selection",
        "menu.edit.find": "Find…",
        "menu.edit.settings": "Settings…",
        "menu.view": "View",
        "menu.view.refresh": "Refresh",
        "menu.view.up": "Up One Level",
        "menu.view.back": "Back",
        "menu.view.forward": "Forward",
        "menu.view.preview": "Preview Pane",
        "menu.view.sidebar": "Sidebar",
        "menu.view.dark": "Dark Theme",
        "menu.view.light": "Light Theme",
        "menu.view.language": "Language",
        "menu.tools": "Tools",
        "menu.tools.settings": "Settings…",
        "menu.tools.new_window": "New Window",
        "menu.help": "Help",
        "menu.help.shortcuts": "Keyboard Shortcuts",
        "menu.help.about": "About",

        "toolbar.open": "Open",
        "toolbar.create": "New",
        "toolbar.extract": "Extract",
        "toolbar.add": "Add",
        "toolbar.delete": "Delete",
        "toolbar.test": "Test",
        "toolbar.up": "Up",
        "toolbar.refresh": "Refresh",
        "toolbar.preview": "Preview",
        "toolbar.info": "Info",
        "toolbar.settings": "Settings",
        "toolbar.back": "Back",
        "toolbar.forward": "Forward",

        "path.current": "Location:",
        "path.placeholder": "Type a folder path or open an archive…",
        "path.this_pc": "This PC",
        "path.root": "Root",
        "search.placeholder": "Search…",

        "col.name": "Name",
        "col.size": "Size",
        "col.packed": "Packed",
        "col.ratio": "Ratio",
        "col.modified": "Modified",
        "col.crc": "CRC",
        "col.method": "Method",
        "col.type": "Type",

        "type.folder": "Folder",
        "type.file": "File",
        "type.archive": "Archive",
        "type.symlink": "Link",
        "type.parent": "Parent folder",
        "type.split": "Split",

        "status.items": "{count} items",
        "status.selected": "{count} selected",
        "status.selected_size": "Selected: {size}",
        "status.ready": "Ready",
        "status.working": "Working…",
        "status.cancelled": "Cancelled",
        "status.archive": "Archive: {name}",
        "status.folder": "Folder",
        "status.opening": "Opening…",
        "status.extracting": "Extracting…",
        "status.creating": "Creating archive…",
        "status.adding": "Adding…",
        "status.deleting": "Deleting…",
        "status.testing": "Testing…",
        "status.done": "Done",
        "status.filtered": "{count} / {total} items (filtered)",

        # Progress window
        "progress.title": "Working",
        "progress.wait": "Please wait…",
        "progress.completed": "Completed",
        "progress.cancelling": "Cancelling…",
        "progress.phase.extract": "Extracting…",
        "progress.phase.delete": "Deleting…",
        "progress.phase.add": "Adding…",
        "progress.phase.rebuild": "Rebuilding…",
        "progress.phase.split": "Splitting into parts…",

        "btn.ok": "OK",
        "btn.cancel": "Cancel",
        "btn.close": "Close",
        "btn.browse": "Browse…",
        "btn.extract": "Extract",
        "btn.create": "Create",
        "btn.add": "Add",
        "btn.delete": "Delete",
        "btn.open": "Open",
        "btn.save": "Save",
        "btn.apply": "Apply",
        "btn.yes": "Yes",
        "btn.no": "No",
        "btn.select_all": "Select All",
        "btn.clear": "Clear",
        "btn.paste": "Paste",

        "dlg.create.title": "Create New Archive",
        "dlg.create.header": "New archive",
        "dlg.create.archive_name": "Archive name:",
        "dlg.create.location": "Location:",
        "dlg.create.format": "Archive format:",
        "dlg.create.level": "Compression level:",
        "dlg.create.method": "Compression method:",
        "dlg.create.password": "Password:",
        "dlg.create.password_confirm": "Password (repeat):",
        "dlg.create.encrypt_header": "Encrypt file names too",
        "dlg.create.source": "Items to add:",
        "dlg.create.default_name": "Archive",
        "dlg.create.password_mismatch": "The passwords do not match.",
        "dlg.create.name_required": "Please enter an archive name.",
        "dlg.create.no_source": "No items selected to add.",
        "dlg.create.exists": "This file already exists. Overwrite it?",
        "dlg.create.summary": "{count} items selected",
        "dlg.create.output": "File to create:",
        "dlg.create.zip_note": "Passwords are only supported for the 7z format.",
        "dlg.create.single_note": "This format can only compress a single file.",
        "dlg.create.split": "Split into parts (multi-volume)",
        "dlg.create.part_size": "Part size:",
        "dlg.create.part_example": "e.g. archive.7z.001, .002, …",
        "dlg.create.part_invalid": "Part size must be at least 1 MB.",
        "unit.mb": "MB",
        "unit.gb": "GB",
        "status.splitting": "Splitting into parts…",

        "dlg.extract.title": "Extract Archive",
        "dlg.extract.header": "Extraction",
        "dlg.extract.destination": "Destination folder:",
        "dlg.extract.all": "All files",
        "dlg.extract.selected": "Selected items only",
        "dlg.extract.overwrite": "Overwrite existing files",
        "dlg.extract.use_subfolder": "Create a subfolder named after the archive",
        "dlg.extract.password": "Password (if required):",
        "dlg.extract.pick_archive": "Choose the archive to extract",
        "dlg.extract.no_dest": "Please choose a destination folder.",
        "dlg.extract.archive": "Archive:",
        "dlg.extract.selected_count": "Selected: {count} / {total}",

        "dlg.settings.title": "Settings",
        "dlg.settings.header": "Settings",
        "dlg.settings.general": "General",
        "dlg.settings.appearance": "Appearance",
        "dlg.settings.archives": "Archives",
        "dlg.settings.language": "Interface language:",
        "dlg.settings.theme": "Theme:",
        "dlg.settings.show_hidden": "Show hidden files",
        "dlg.settings.confirm_delete": "Confirm before deleting from archive",
        "dlg.settings.preview": "Enable the preview pane",
        "dlg.settings.default_extract": "Default extraction folder:",
        "dlg.settings.compression": "Default compression level:",
        "dlg.settings.saved": "Settings saved.",
        "dlg.settings.restart_hint": "Language changes apply immediately.",

        "dlg.password.title": "Password Required",
        "dlg.password.header": "Password required",
        "dlg.password.hint": "This archive is password protected. Please enter the password.",
        "dlg.password.label": "Password:",
        "dlg.password.empty": "The password cannot be empty.",
        "dlg.password.wrong": "Wrong password or corrupted archive.",

        "dlg.properties.title": "Properties",
        "dlg.properties.header": "Properties",
        "dlg.properties.file": "File",
        "dlg.properties.format": "Format",
        "dlg.properties.entries": "Entries",
        "dlg.properties.size": "Unpacked size",
        "dlg.properties.packed": "Packed size",
        "dlg.properties.ratio": "Compression ratio",
        "dlg.properties.methods": "Methods",
        "dlg.properties.encrypted": "Encrypted",
        "dlg.properties.path": "Location",
        "dlg.properties.modified": "Modified",
        "dlg.properties.type": "Type",
        "dlg.properties.name": "Name",
        "dlg.properties.yes": "Yes",
        "dlg.properties.no": "No",

        "dlg.about.title": "About Py7-Zip",
        "dlg.about.description": (
            "Py7-Zip is a modern archive manager rewritten in Python and "
            "Tkinter, inspired by the 7-Zip C++ codebase.\n\n"
            "Engine: py7zr + the Python standard library\n"
            "Formats: 7z, zip, tar, tar.gz, tar.bz2, tar.xz, gz, bz2, xz\n"
            "License: LGPL-2.1"
        ),
        "dlg.about.version": "Version {version}",
        "dlg.about.author": (
            "Developer: Bekir Alişoğlu\n"
            "Email: alisoglu@yahoo.com"
        ),
        "dlg.shortcuts.title": "Keyboard Shortcuts",
        "dlg.shortcuts.text": (
            "Ctrl+O    Open archive\n"
            "Ctrl+N    New archive\n"
            "Ctrl+E    Extract\n"
            "Ctrl+A    Select all\n"
            "Ctrl+F    Find\n"
            "F5        Refresh\n"
            "Backspace Up one level\n"
            "Enter     Open / enter\n"
            "Delete    Delete from archive\n"
            "Alt+Enter Properties\n"
            "Ctrl+Q    Quit"
        ),

        "msg.error": "Error",
        "msg.warning": "Warning",
        "msg.info": "Information",
        "msg.confirm": "Confirm",
        "msg.password_required": "This archive is password protected.",
        "msg.invalid_archive": "Invalid or unsupported archive.",
        "msg.archive_exists": "The archive already exists. Overwrite it?",
        "msg.confirm_delete": "Delete the selected {count} items from the archive?",
        "msg.confirm_delete_many": "Delete the selected items from the archive?",
        "msg.no_selection": "Please select at least one item.",
        "msg.done": "Operation completed.",
        "msg.unsupported": "This operation is not supported for this archive format.",
        "msg.unsupported_format": "Unsupported archive format: {fmt}",
        "msg.create_success": "Archive created:\n{path}",
        "msg.extract_success": "Files extracted to:\n{path}",
        "msg.add_success": "Items were added to the archive.",
        "msg.delete_success": "Items were deleted from the archive.",
        "msg.test_ok": "The archive is healthy. No errors found.",
        "msg.test_failed": "Archive test failed:\n{detail}",
        "msg.read_error": "Could not read the file:\n{detail}",
        "msg.write_error": "Could not write the file:\n{detail}",
        "msg.extract_error": "Extraction failed:\n{detail}",
        "msg.create_error": "Could not create the archive:\n{detail}",
        "msg.add_error": "Could not add items:\n{detail}",
        "msg.delete_error": "Could not delete items:\n{detail}",
        "msg.open_error": "Could not open the file:\n{detail}",
        "msg.zip_password_unsupported": (
            "Zip archives cannot be encrypted while writing. Passwords are "
            "only available for the 7z format."
        ),
        "msg.single_file_only": (
            "The gz, bz2 and xz formats can only compress a single file."
        ),
        "msg.temp_dir_error": "Could not create a temporary folder:\n{detail}",
        "msg.file_missing": "File not found:\n{path}",
        "msg.copy_failed": "Copy failed:\n{detail}",
        "msg.preview_binary": "This file contains binary data; no text preview is available.",
        "msg.preview_too_large": "The file is too large to preview ({size}).",
        "msg.preview_unavailable": "Preview is not available.",
        "msg.filter_prompt": "Search text:",
        "msg.filter_empty": "The search text is empty.",
        "msg.cancel": "Cancel",
        "msg.overwrite": "Overwrite",
        "msg.skip": "Skip",
        "msg.overwrite_title": "Files already exist",
        "msg.overwrite_text": "The destination already contains files with the same names. What should be done?",
        "msg.open_with": "Open with",
        "msg.not_archive": "This is not an archive file.",
        "msg.no_password_needed": "This archive does not require a password.",
        "msg.operation_cancelled": "Operation cancelled.",
        "msg.close_archive": "Close archive",
        "msg.select_archive_first": "Select or open an archive first.",
        "msg.no_archive_open": "No archive is currently open.",
        "msg.nothing_to_extract": "There is nothing to extract.",
        "msg.nothing_to_delete": "There is nothing to delete.",
        "msg.split_modify_unsupported": (
            "Adding/removing items from split archives is not supported. "
            "Join the parts first."
        ),

        "level.0": "0 - Store only",
        "level.1": "1 - Fastest",
        "level.3": "3 - Fast",
        "level.5": "5 - Normal",
        "level.7": "7 - High",
        "level.9": "9 - Ultra",
        "level.custom": "Custom",

        "preview.title": "Preview",
        "preview.no_selection": "Select a file to preview.",
        "preview.open_external": "Open with default app",
        "preview.extract": "Extract",
        "preview.loading": "Loading…",
        "preview.image": "Image preview",
        "preview.text": "Text preview",
        "preview.info": "Info",

        "misc.folder": "Folder",
        "misc.file": "File",
        "misc.bytes": "B",
        "misc.kb": "KB",
        "misc.mb": "MB",
        "misc.gb": "GB",
        "misc.tb": "TB",
        "misc.unknown": "—",
        "misc.search": "Search",
        "misc.cancel": "Cancel",
    },
}
# fmt: on


from .locales import EXTRA_TRANSLATIONS  # noqa: E402

TRANSLATIONS.update(EXTRA_TRANSLATIONS)


class I18N:
    """Runtime translator with a graceful fallback chain."""

    def __init__(self, language: str = "tr") -> None:
        self.language = language if language in TRANSLATIONS else "en"

    def set_language(self, language: str) -> None:
        if language in TRANSLATIONS:
            self.language = language

    def t(self, key: str, **kwargs: Any) -> str:
        text = TRANSLATIONS.get(self.language, {}).get(key)
        if text is None:
            text = TRANSLATIONS["en"].get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    def __call__(self, key: str, **kwargs: Any) -> str:
        return self.t(key, **kwargs)
