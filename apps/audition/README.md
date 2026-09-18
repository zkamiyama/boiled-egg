# boiled egg Audition Lab — PySide6 standalone

プラグインやDAWを起動せずに使うファイル試聴アプリです。現時点の検証対象は
Linux x86_64。速度0のフリーズはC++の新しい出力駆動transportが合成し、Pythonで
変換済みの短いWAVをループさせる方式ではありません。試用ブランチの機能で、
既存mainのSDK・プラグインを置き換えません。

## 起動（ビルド済みLinuxパッケージ）

Python 3.11以降と、使用できる音声出力デバイスが必要です。初回のみ:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-audition.txt
```

通常起動:

```sh
bash start-audition.sh --demo
# または .venv/bin/python run_audition.py --file /path/to/audio.wav
```

PySide6/NumPy/SoundFileはrequirementsからインストールします。Qt、Python、
システムライブラリを内包した単一実行ファイルではありません。配布ZIPにフォントや
外部SDKを含めません。Qtのxcbライブラリ不足があるDebian/Ubuntu環境では、
ディストリビューションのlibegl1 / libopengl0 / libpulse0 / libsndfile1 /
libxcb-cursor0 / libxkbcommon-x11-0などを導入してください。

## ソースからビルド

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-audition.txt
bash scripts/build_audition.sh
.venv/bin/python run_audition.py --demo
```

CMake 3.20以降・C++20コンパイラーを使用します。transportと実SDK CLIを別々に
ビルドします。既存のWSOLA/PVをフリーズ対応として偽装せず、処理経路を分けます。

## 操作

「音声を開く」またはドラッグ＆ドロップでWAV/FLAC/AIFF/OGGを読み込みます。
モノラル・ステレオ、32 million scalar samplesまでです。内部ではfloat32で処理。

- 速度 **0 = フリーズ / 1 = 等速 / 4 = 4倍速**。小数指定も可能。
- ピッチ **0 st = 音程変更なし**。範囲は-24〜+24半音（0.25〜4倍の周波数比）。
  0 stは「DSPを完全バイパスしてPCMが同一になる」という意味ではありません。
- Fキーでフリーズ/元の速度へ復帰。Spaceで再生/一時停止。
  一時停止は出力を止め、フリーズは原音の参照位置だけを止めます。
- フリーズ中もピッチ/フォルマントを変更できます。ピッチ平滑化は出力時間で進行。
- 波形をクリックして位置を選び、再生を押します。方式・レート変更も一旦停止します。
- PV系はOff/Harmonic/Monophonic、±12 stの独立フォルマント操作があります。
  時間領域系はフォルマント非対応と表示し、別方式へ自動切替しません。
- 「WAVを書出す」は現在位置・設定から0.1〜120秒を新規生成します。
  無期限のフリーズにも必ず有限の書出し長を指定します。

試聴音量は初期25%。まず低い音量で確認してください。WAV書出しには試聴音量を
適用せず、生のfloat出力を保存します。1.0を超えるピークを勝手に正規化/制限せず、
表示します。書出しは新しい合成履歴から始まるため、直前に聴いていたバッファの
厳密な録音ではありません。既存ファイルを上書きしません。

## 試せる方式と「全方式」の範囲

ネイティブ再生タブ: PV Classic / Locked / Transient、WSOLA / Transient /
Efficientの6つの**新transportモード**。全て速度0〜4、ピッチ±24 stを受け付けます。
PVは保持した局所スペクトル・周波数から位相を継続、時間領域系は保持位置周辺の
波形断片を相関探索して合成します。合成方式の名前が似ていても旧SDKと同一PCMの
実装ではありません。

従来SDK比較タブ: **現在のmain SDKの全5モード**（WSOLA General/Transient/
Efficient、PV General/Transient）を実SDK CLIでレンダーします。
「5方式を同条件で比較」は原音を一度スナップショットし、同じ指定で5モードを実行。
完了後に選択欄で切り替え「比較音源を再生」、または「選択WAVと記録を保存」。
Harmonic等を指定して非対応になるモードも、unsupportedとして結果に残します。

従来WSOLA: 速度0.25〜4、±24 st、フォルマントOffのみ。
従来PV: 速度0.5〜2、±12 st、Off/Harmonic/Monophonic。
従来SDK自体には速度0がないため、このタブではフリーズへ暗黙変換しません。
比較出力は120秒まで。結果は一時領域にあるため、必要なWAVは終了前に保存します。

過去の研究枝のmulti-resolution、phase-gradient、HPSS、可変窓等をすべてこの
transportへ移植したわけではありません。これらは既に生成した研究音声を
「比較音源を開く」で再生できますが、方式の識別は利用者の管理となります。
外部R3/Signalsmith/native zplaneエンジンは同梱・新規実行しません。

## 再生・精度の境界

フリーズではC++の原音時計が固定され、出力時計と合成位相は進みます。解析窓と
オーバーラップ、最大2ブロックのPythonキュー、Qt/OSの出力バッファがあるため、
クリックした瞬間のスピーカー出力がサンプル単位で即時変更される保証ではありません。
表示は合成側の原音位置で、DAC到達時刻ではありません。安定時の周波数テストは
自然な楽曲の聴感評価や全制御範囲の音質保証と区別します。

メモリーは読み込んだ原音＋固定DSP領域で保持し、フリーズ時間に比例した録音を
蓄積しません。ライブ入力の無限保持/全入力保存/固定遅延はこのファイル再生とは
別の問題です。Qt/Pythonはハードリアルタイム保証の対象外です。

この開発環境で実DAC/スピーカーへの再生は確認できていません。GUI、実C++レンダー、
WAV書出し、Qtへの部分書込み、デバイス不在/故障を自動試験しています。無音デバイスを
実音出力の成功として扱いません。デバイスがない場合もWAV生成・比較は使用可能。

## 再現テスト

```sh
QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 .venv/bin/python -m unittest discover \
  -s apps/audition -p 'test_*.py' -v
QT_QPA_PLATFORM=offscreen .venv/bin/python run_audition.py --smoke --screenshot preview.png
.venv/bin/python apps/audition/assess_freeze.py --output new-freeze-results
```

`--smoke`はネイティブの音声読込みを確認してから終了し、ライブラリ不在なら失敗に
なります。実機再生や自然音の総合音質を認定するコマンドではありません。
EOF後は「先頭」または波形クリックで位置を戻してください。
EOFや無音の位置でフリーズしても、存在しない音が生成されるわけではありません。
