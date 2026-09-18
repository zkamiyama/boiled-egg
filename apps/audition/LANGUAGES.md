# 日本語 / English

## 日本語

画面右上の「言語」で **日本語 / English** を切り替えられます。
再起動や原音の再読込みは不要です。選んだ言語は次回起動時にも復元します。
初回起動、または保存値が未対応の言語の場合は、日本語で起動します。

一時的に起動言語だけを指定する場合:

```sh
bash start-audition.sh --language en --demo
bash start-audition.sh --language ja
```

`--language`はその起動中だけの指定です。画面で選択すると保存します。
保存先はQtのユーザー設定`boiled-egg/AuditionLab`、キーは`ui/language`です。
設定を保存できない場合は、現在の表示を切り替えたまま注意を表示します。

切替対象: 操作ボタン、タブ、説明、波形上の案内、音量・ピッチ・速度などの見出し、
再生・フリーズ状態、比較進捗、完了・未対応・中止表示、アプリのログとダイアログの題名。
過去に表示されたアプリメッセージも切り替わります。

原音位置、音程、速度、フォルマント方式、試聴音量、選択した比較結果、処理中のジョブは
言語切替では変更しません。フリーズや再生を停止・再生成せず、音声キューを捨てません。
方式ID・SDKへ渡す`off/harmonic/monophonic`・JSON記録・WAVの内容は翻訳しません。

ファイル名と音声デバイス名は原文を保持します。外部ライブラリの診断は原文を残し、
既知の診断には日本語の説明を添えます。OS標準のダイアログはOSの言語になる場合があります。
Qtの標準表示には、導入したPySide6に含まれる日本語カタログが利用できる場合に使います。
このアプリは1つのウィンドウでの利用を対象とします。

## English

Use **Language → 日本語 / English** at the top right. The display changes immediately,
without restarting or reloading audio. A selection in the app is saved for the next
launch. First launch defaults to Japanese; an invalid saved value also falls back
to Japanese.

For a session-only override, launch with `--language en` or `--language ja`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-audition.txt
bash start-audition.sh --language en --demo
```

Language switching does not pause, seek, reset, clear the audio queue, cancel a
render, or change pitch/speed/formants/volume. Selected comparisons remain selected.
The SDK's numeric mode IDs and string policy tokens remain canonical, as do raw
WAVs and JSON receipts. Existing application logs and result descriptions are
retranslated from their original structured messages.

File/device names and raw external diagnostics remain verbatim. Some system-owned
dialog text follows the operating system language. Standard Qt Japanese text uses
the installed PySide6 translation catalog when available. One application window
is the supported usage.

Speed **0 = native freeze**, speed **1 = normal progression**, speed **4 = 4×**.
Pitch **0 st = no pitch displacement**; it is not a zero frequency ratio or a DSP
bypass. Pause is separate from freeze. Press **F** to toggle freeze and **Space**
to pause/play. Raw WAV export is finite (0.1–120 seconds) and does not apply the
listening-volume control. No new DSP or algorithm capability is added by this
localization change.
