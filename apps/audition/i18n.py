"""Presentation-only JA/EN catalog. Never translate DSP IDs or raw receipts.

QSettings stores only ui/language. A command-line language is a session override;
only an explicit user selection persists it. Unknown external diagnostics remain
verbatim. Structured messages let existing logs/results change language safely.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from PySide6.QtCore import QSettings, QTranslator, QLibraryInfo
from PySide6.QtWidgets import QApplication

LANGUAGES = ('ja', 'en')
CATALOG = {
    'choose_device': ('出力先を選択', 'Select an output device'),
    'device_removed': ('選択した音声デバイスが切断されました。別の出力先を選んでください。原音は保持しています。', 'The selected audio device was disconnected. Select an output device. The source is retained.'),
    'language': ('言語', 'Language'),
    'subtitle': ('C++ネイティブ再生 · 速度0＝フリーズ · ピッチ0 st＝音程変更なし', 'C++ native transport · speed 0 = freeze · pitch 0 st = original pitch'),
    'open_audio': ('音声を開く', 'Open audio'),
    'demo': ('デモ素材', 'Demo'),
    'drop_audio': ('WAV / FLAC / AIFF / OGG をドロップ', 'Drop WAV / FLAC / AIFF / OGG here'),
    'source_anchor': ('原音位置 / クリックして選択', 'SOURCE ANCHOR / Click to seek'),
    'native_mode': ('ネイティブ方式', 'Native mode'),
    'native_hint': ('フリーズ対応の新しい再生系です。従来SDKと同じPCMになる方式ではありません。切替・シーク後は再生を押してください。', 'New freeze-capable transport; not PCM-identical to the legacy SDK. Press Play after changing modes or seeking.'),
    'speed': ('再生速度', 'Playback speed'),
    'pitch': ('ピッチ変更', 'Pitch shift'),
    'formant': ('フォルマント変更', 'Formant shift'),
    'play': ('▶ 再生', '▶ Play'),
    'pause': ('Ⅱ 一時停止', 'Ⅱ Pause'),
    'freeze': ('❄ フリーズ [F]', '❄ Freeze [F]'),
    'unfreeze': ('▶ フリーズ解除 [F]', '▶ Unfreeze [F]'),
    'start': ('先頭', 'Go to start'),
    'reset': ('速度1 / ピッチ0', 'Speed 1 / Pitch 0'),
    'export_hint': ('現在位置・現在設定で有限長WAV書出し', 'Export a finite WAV from the current anchor and settings'),
    'seconds_suffix': (' 秒', ' s'),
    'export': ('WAVを書出す', 'Export WAV'),
    'compare_native': ('6方式を現在位置・同条件で比較', 'Compare 6 modes at this anchor'),
    'cancel_native': ('書出し・比較を中止', 'Cancel export / comparison'),
    'idle': ('待機中', 'Ready'),
    'native_tab': ('ネイティブ再生・フリーズ', 'Native playback / freeze'),
    'output_device': ('出力先', 'Output device'),
    'no_device': ('音声デバイスなし — WAV書出しは使用可能', 'No audio device — WAV export is available'),
    'volume': ('試聴音量（生WAVには不適用）', 'Listening volume (not applied to raw WAVs)'),
    'intro': ('速度0は一時停止ではありません。Pauseは再生停止、Freezeは原音位置だけを固定します。', 'Speed 0 is not Pause. Pause stops playback; Freeze holds only the source position.'),
    'compare_hint': ('従来SDKの全5品質モードを実SDK CLIでレンダーして試聴します。ネイティブフリーズとは別経路です。未移植の研究方式を別方式に置換しません。既存の研究出力は「比較音源を開く」で試聴できます。', 'Render all 5 legacy SDK quality modes through the actual SDK CLI. This is separate from native freeze. Unported research modes are not substituted; open their pre-rendered files for comparison.'),
    'sdk_speed': ('通常SDKの速度', 'Legacy SDK speed'),
    'sdk_bounds': ('WSOLA: 速度0.25〜4・±24 st / PV: 速度0.5〜2・±12 st。範囲外と未対応保持はエラー表示。自動代替・時間合わせ・音量正規化なし。', 'WSOLA: speed 0.25–4, ±24 st / PV: speed 0.5–2, ±12 st. Unsupported ranges or formant policies are errors. No fallback, alignment or normalization.'),
    'render_sdk': ('現在の原音をSDKでレンダー', 'Render source with SDK'),
    'compare_sdk': ('5方式を同条件で比較', 'Compare 5 SDK modes'),
    'cancel_render': ('レンダー中止', 'Cancel render'),
    'open_reference': ('比較音源を開く', 'Open comparison audio'),
    'play_reference': ('▶ 比較音源を再生', '▶ Play comparison'),
    'stop_reference': ('比較音源を停止', 'Stop comparison'),
    'save_reference': ('選択WAVと記録を保存', 'Save selected WAV + receipt'),
    'no_reference': ('比較音源未選択', 'No comparison selected'),
    'compare_tab': ('従来SDK・研究出力の比較', 'Legacy SDK / research comparison'),
    'warning': ('注意: {detail}', 'Warning: {detail}'),
    'loading': ('読込み中: {name}', 'Loading: {name}'),
    'load_first': ('先に原音を読み込んでください。', 'Load a source first.'),
    'finish_first': ('書出し・比較を完了または中止してから再生してください。', 'Finish or cancel the export / comparison before playing.'),
    'no_playback_device': ('音声デバイスがありません。有限長WAV書出し、SDK比較レンダーは使えます。', 'No audio device is available. Finite WAV export and SDK comparison rendering still work.'),
    'native_busy': ('ネイティブ書出し・比較が進行中です。', 'A native export / comparison is in progress.'),
    'comparison_busy': ('比較・書出しが進行中です。', 'A comparison / export is in progress.'),
    'export_title': ('生のfloat32 WAVを書出す', 'Export raw float32 WAV'),
    'exporting': ('有限長書出し中（既存ファイルは上書きしません）', 'Exporting finite audio (existing files are never overwritten).'),
    'native_rendering': ('6方式を同じ原音位置・設定から合成中。速度0は各C++方式がフリーズします。', 'Synthesizing 6 modes from the same source anchor and settings. At speed 0 each C++ mode performs freeze synthesis.'),
    'comparison_complete': ('比較完了: {passed}/{total}。未対応・失敗も選択欄に残しています。', 'Comparison complete: {passed}/{total}. Unsupported and failed modes remain in the list.'),
    'rendering_sdk': ('SDKレンダー中…', 'Rendering with SDK…'),
    'rendering_sdk_all': ('5方式を同じ原音・設定でレンダー中…（未対応条件は代替しません）', 'Rendering 5 modes from the same source and settings… (no fallback for unsupported controls)'),
    'save_select_first': ('保存できる比較出力を選択してください。', 'Select a completed comparison output to save.'),
    'save_title': ('比較WAVと測定記録を保存', 'Save comparison WAV and receipt'),
    'saved': ('生の比較出力を保存: {path}', 'Saved raw comparison output: {path}'),
    'external_title': ('既存の研究出力を比較用に開く', 'Open a pre-rendered research output'),
    'external_label': ('外部比較音源（生成方式は未検証）', 'External comparison (generating method unverified)'),
    'reference_first': ('比較音源を生成または開いてください。', 'Render or open comparison audio first.'),
    'device_unavailable': ('音声デバイスがありません。', 'No audio device is available.'),
    'frozen_status': ('フリーズ — 原音位置固定', 'FREEZE — source anchor held'),
    'playing_status': ('再生', 'Playing'),
    'telemetry': ('{state} | 原音 {source:.3f} s | 出力 {output:.3f} s | ピッチ {pitch:+.2f} st | 生ピーク {peak:.3f}{warning}', '{state} | Source {source:.3f} s | Output {output:.3f} s | Pitch {pitch:+.2f} st | Raw peak {peak:.3f}{warning}'),
    'peak_warning': ('  ⚠ 1.0超（WAVは制限なし）', '  ⚠ Above 1.0 (WAV is not limited)'),
    'empty': ('', ''),
    'position': ('原音位置 {seconds:.3f} s — 再生で合成を開始', 'Source anchor {seconds:.3f} s — press Play to synthesize'),
    'loaded': ('読込み完了。方式・速度を選択して再生できます。', 'Source loaded. Choose a mode and speed, then press Play.'),
    'source_retained': ('原音を維持: {name}', 'Source retained: {name}'),
    'exported': ('WAV書出し完了: {path}', 'WAV export complete: {path}'),
    'render_progress': ('比較合成 {completed}/{total} — {status}', 'Comparison {completed}/{total} — {status}'),
    'ended': ('原音終端・tail出力完了', 'End of source; tail output complete'),
    'render_failed': ('比較レンダー未完了（代替処理なし）', 'Comparison incomplete (no fallback)'),
    'close_pending': ('処理を中止して終了しています…', 'Cancelling operations and closing…'),
    'settings_failed': ('言語設定を保存できませんでした。この起動中の表示には反映しています。', 'Could not save the language preference. The current session uses the selected language.'),
    'source_loaded_pcm': ('読込み済み原音PCM', 'Loaded source PCM'),
    'comparison_detail': ('{source} | {frames} フレーム | 生ピーク {peak:.3f}', '{source} | {frames} frames | Raw peak {peak:.3f}'),
    'single_detail': ('{frames} フレーム | 生ピーク {peak:.3f} — 無加工の比較WAV', '{frames} frames | Raw peak {peak:.3f} — unmodified comparison WAV'),
    'choice': ('{kind}: {mode} — {status}', '{kind}: {mode} — {status}'),
    'kind_native': ('ネイティブ', 'Native'),
    'kind_sdk': ('SDK', 'SDK'),
    'passed': ('完了', 'Complete'),
    'failed': ('失敗', 'Failed'),
    'unsupported': ('未対応', 'Unsupported'),
    'cancelled': ('中止', 'Cancelled'),
    'pending': ('待機', 'Pending'),
    'policy_off': ('保持なし (Off)', 'Off'),
    'policy_harmonic': ('倍音・和音 (Harmonic)', 'Harmonic / polyphonic'),
    'policy_mono': ('単音 (Monophonic)', 'Monophonic'),
    'native_0': ('PV Classic — スペクトル保持', 'PV Classic — spectral hold'),
    'native_1': ('PV Locked — スペクトル保持', 'PV Locked — spectral hold'),
    'native_2': ('PV Transient — スペクトル保持', 'PV Transient — spectral hold'),
    'native_3': ('WSOLA — 時間領域保持', 'WSOLA — time-domain hold'),
    'native_4': ('WSOLA Transient — 時間領域保持', 'WSOLA Transient — time-domain hold'),
    'native_5': ('WSOLA Efficient — 時間領域保持', 'WSOLA Efficient — time-domain hold'),
    'sdk_0': ('SDK WSOLA / General（一般）', 'SDK WSOLA / General'),
    'sdk_1': ('SDK WSOLA / Transient（打撃音）', 'SDK WSOLA / Transient'),
    'sdk_2': ('SDK WSOLA / Efficient（省CPU）', 'SDK WSOLA / Efficient'),
    'sdk_3': ('SDK PV / General（一般）', 'SDK PV / General'),
    'sdk_4': ('SDK PV / Transient（打撃音）', 'SDK PV / Transient'),
    'audio_format_unsupported': ('選択デバイスはこのfloat32形式に未対応です。出力先・レートを変更してください。WAV書出しは利用できます。', 'The selected device does not support this float32 format. Choose another output device or sample rate. WAV export remains available.'),
    'audio_start_failed': ('音声デバイスを開始できません。', 'Could not start the audio device.'),
    'audio_stopped': ('音声デバイスが停止しました。出力先を選び直してください。原音は保持しています。', 'The audio device stopped. Select an output device again. The source is retained.'),
    'audio_write_failed': ('音声出力の書込みに失敗しました。', 'Writing to the audio output failed.'),
    'audio_filter': ('音声 (*.wav *.flac *.aiff *.aif *.ogg);;すべてのファイル (*)', 'Audio (*.wav *.flac *.aiff *.aif *.ogg);;All files (*)'),
    'wave_filter': ('WAV音声 (*.wav)', 'Wave (*.wav)'),
}

# OutputPump owns these exact Japanese diagnostics. Translate their presentation
# without changing its signals or buffer/recovery behavior. This is not a rewrite
# of arbitrary external error text; unknown diagnostics remain verbatim below.
OWNED_DIAGNOSTICS = {
    CATALOG[key][0]: key for key in (
        'audio_format_unsupported', 'audio_start_failed', 'audio_stopped', 'audio_write_failed')
}

# Native/worker/SDK errors remain their original machine strings outside the UI.
# Known diagnostic explanations are localized; raw details are always retained.
DIAGNOSTICS = {
    'Load a source first': '先に原音を読み込んでください。',
    'Time-domain formant policy unsupported; no fallback': '時間領域方式はフォルマント保持に未対応です。代替処理はしません。',
    'Time-domain formants are unsupported': '時間領域方式はフォルマント保持に未対応です。',
    'Formant shift requires a preservation policy': 'フォルマント変更には保持方式の選択が必要です。',
    'Native comparison cancelled': 'ネイティブ比較を中止しました。',
    'Export cancelled': 'WAV書出しを中止しました。',
    'Unsupported mode/policy/rate: no fallback': '方式・保持設定・レートの組合せに未対応です。代替処理はしません。',
    'Invalid native audio, parameter or block': '音声・パラメーター・処理ブロックが不正です。',
    'Native allocation failed': 'ネイティブ処理のメモリー確保に失敗しました。',
    'Native internal failure': 'ネイティブ処理で内部エラーが発生しました。',
    'Player accepts mono/stereo files; no silent downmix': 'モノラル・ステレオのみ対応しています。自動ダウンミックスはしません。',
    'Empty/nonfinite file': '音声が空、または非有限値を含んでいます。',
    'File exceeds player limit of32 million scalar samples': '音声ファイルが上限の3,200万サンプル値を超えています。',
    'Export must not overwrite an existing file': '既存のファイルには上書きできません。',
    'Export duration must be .1..120 seconds, including freeze': '書出し時間はフリーズを含め0.1〜120秒で指定してください。',
    'Command queue full; wait for current load/render to finish': 'コマンド待ち行列が満杯です。現在の読込み・合成の完了後に操作してください。',
    'Existing WSOLA does not preserve formants; no fallback': '既存WSOLAはフォルマント保持に未対応です。代替処理はしません。',
    'Formant shift requires an enabled policy': 'フォルマント変更には保持方式の有効化が必要です。',
}

@dataclass(frozen=True)
class Message:
    key: str
    values: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Diagnostic:
    raw: str


def message(key: str, **values: Any) -> Message:
    return Message(key, values)


class I18n:
    def __init__(self, language=None, preferences=None):
        self.preferences = preferences if preferences is not None else QSettings('boiled-egg', 'AuditionLab')
        saved = self.preferences.value('ui/language', 'ja')
        if language is not None and language not in LANGUAGES:
            raise ValueError('Language must be ja or en')
        self.language = language if language is not None else (saved if saved in LANGUAGES else 'ja')

    def text(self, value: str | Message | Diagnostic) -> str:
        if isinstance(value, Diagnostic):
            owned_key = OWNED_DIAGNOSTICS.get(value.raw)
            if owned_key is not None:
                return self.text(message(owned_key))
            explanation = DIAGNOSTICS.get(value.raw) if self.language == 'ja' else None
            return f'{explanation}\n[original] {value.raw}' if explanation else value.raw
        if not isinstance(value, Message):
            return str(value)
        pair = CATALOG[value.key]
        values = {k: self.text(v) if isinstance(v, (Message, Diagnostic)) else v
                  for k, v in value.values.items()}
        return pair[LANGUAGES.index(self.language)].format(**values)

    def select(self, language: str, persist=True) -> bool:
        if language not in LANGUAGES:
            raise ValueError('Language must be ja or en')
        self.language = language
        if not persist:
            return True
        self.preferences.setValue('ui/language', language)
        self.preferences.sync()
        return self.preferences.status() == QSettings.Status.NoError

    def install_qt_translation(self) -> bool:
        """Use the shipped Qt dialog catalog; native OS dialogs may differ."""
        app = QApplication.instance()
        if app is None:
            return False
        old = getattr(app, '_audition_qt_translator', None)
        if old is not None:
            app.removeTranslator(old)
            old.deleteLater()
        app._audition_qt_translator = None
        if self.language == 'en':
            return True
        translator = QTranslator(app)
        if not translator.load('qtbase_ja', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            translator.deleteLater()
            return False
        app.installTranslator(translator)
        app._audition_qt_translator = translator
        return True
