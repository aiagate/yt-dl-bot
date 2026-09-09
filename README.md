# yt-dl-bot

YouTube と Twitch の動画をダウンロードし、YouTube のライブチャットから
ハイライトを作成する Discord bot です。Discord の通常コマンドに加えて、
指定したチャンネルへ URL だけを投稿したときの自動ルーティングにも対応します。
データベースは使用せず、動画・メタデータ・サムネイル・グラフをファイルとして保存します。

## 前提

- Python 3.12（`>=3.12,<3.13`）
- [uv](https://docs.astral.sh/uv/)
- ローカル実行では `ffmpeg` と `ffprobe` が PATH に必要です。Docker イメージには
  `ffmpeg` が含まれます。
- Discord Developer Portal で作成した bot と、送受信に使用するチャンネルの ID

## セットアップと起動

依存関係をロックファイルどおりにインストールします。

```sh
uv sync --locked
```

環境変数のテンプレートをコピーし、`replace-me` と各チャンネル ID を実際の値へ
置き換えます。

```sh
cp .env.example .env
```

`.env` は Git の管理対象外です。`DISCORD_KEY`（bot トークン）を含むため、
コミットしないでください。インストール済みパッケージは次のいずれかで起動できます。

```sh
uv run yt-dl-bot
# 同じエントリポイントをモジュールとして起動する場合
uv run python -m yt_dl_bot.discord_bot_main
```

相対パスの設定は、Python アプリケーションを起動したときのカレントディレクトリを
基準に解決されます。リポジトリ直下から起動すると、既定の `downloads/`、
`logs/`、`cookie/` をそのまま利用できます。

## 設定

### アプリケーションの設定

`Settings` が読み込む必須項目と既定値は次のとおりです。チャンネル ID は Discord の
数値 ID を指定してください。

| 変数 | 必須 | 用途・既定値 |
| --- | --- | --- |
| `DISCORD_KEY` | はい | Discord bot トークン |
| `LOG_CHANNEL` | はい | エラー traceback と管理通知を送るチャンネル |
| `VIDEO_OUTPUT_CHANNEL` | はい | ダウンロード成功通知を送るチャンネル |
| `HIGHLIGHT_OUTPUT_CHANNEL` | はい | ハイライトの embed とグラフを送るチャンネル |
| `DOWNLOAD_CHANNEL` | はい | URL 自動ルーティングで動画をダウンロードするチャンネル |
| `HIGHLIGHT_CHANNEL` | はい | URL 自動ルーティングで YouTube ハイライトを作るチャンネル |
| `SAVE_PATH` | いいえ | 動画・メタデータ・サムネイルの保存先（`downloads`） |
| `GRAPH_SAVE_PATH` | いいえ | 投稿後のグラフの保存先（`downloads/graph`） |
| `TMP_PATH` | いいえ | yt-dlp とグラフの一時ファイル置き場（`downloads/cache`） |
| `LOG_PATH` | いいえ | ログディレクトリ（`logs`） |

`INITIAL_EXTENSIONS` を指定すると、起動時に読み込む Cog の一覧も変更できます。
通常は `setting.py` の `DEFAULT_INITIAL_EXTENSIONS` を利用してください。

Discord 側では **Bot > Privileged Gateway Intents** の **Message Content Intent** を
有効にする必要があります。コードが有効にする gateway intent のうち、privileged
intent はこれだけです（`guilds`、`guild_messages`、`dm_messages` も利用します）。

アプリケーションは完全な例外 traceback を `LOG_PATH/discord_bot_main.log` に保存します。
Discord のログチャンネルへ送信する報告では、認証情報・Cookie ヘッダー・secret らしい
キーと値・URL のユーザー情報・機密クエリーパラメーター・ローカル絶対パスを一般的な
パターンに基づいてマスクします。これは誤送信を減らすための処理であり、自由形式の
例外メッセージに埋め込まれた任意の秘密情報をすべて検出するものではありません。
例外メッセージへ認証情報を含めないでください。

### Compose 専用の変数

`compose.yaml` では、アプリケーションのパス設定をコンテナへ渡すのではなく、ホストの
ディレクトリをコンテナ内の既定パスへマウントします。

| 変数 | コンテナ内のマウント先 | 既定のホスト側パス |
| --- | --- | --- |
| `DOWNLOADS_PATH` | `/app/downloads` | `./downloads` |
| `COOKIE_PATH` | `/app/cookie`（読み取り専用） | `./cookie` |

したがって、`DOWNLOADS_PATH` と `COOKIE_PATH` は Python を直接起動したときの
`Settings` の項目ではありません。Twitch のダウンロードで Cookie を使う場合は、
直接起動でも Compose でも `cookie/cookies.txt` が存在すると自動的に読み込まれます。
Compose ではホストの `${COOKIE_PATH}/cookies.txt` が `/app/cookie/cookies.txt` に
対応します。Cookie ファイルは秘密情報として扱ってください。

## アーキテクチャ

Discord の受信処理、ダウンロード、チャット解析、Discord への表示を分離しています。

```text
Discord message
  -> MainCog / MessageRouter
  -> YouTubeCog または TwitchCog
  -> application service
  -> YouTubeDownloader または YtDlpDownloader
  -> 共通の DownloadEngine
  -> yt-dlp とファイルシステム
```

`ApplicationServices.from_settings()` が Cog から利用するユースケースを組み立てます。
アプリケーションサービスは yt-dlp、チャット、ファイルシステムの失敗をアプリケーション
エラーへ変換します。`DownloadEngine` は共通の yt-dlp 処理をオーケストレーションし、
`DownloadPolicy` がサイトごとの差分を定義します。`ArtifactStore` は保存先の計画、
既存ファイルとの衝突検査、移動、失敗時のロールバックを担当します。

YouTube のハイライトは、次の独立した経路で処理されます。

```text
YouTubeHighlightService
  -> ChatHighlightPipeline
  -> PytchatSource / HighlightAnalyzer / MatplotlibGraphRenderer
```

主要な実装箇所は次のとおりです。

- `cogs/`: Discord コマンド、返信、embed、自動 URL ルーティング
- `application_container.py`: アダプターとサービスを接続する composition root
- `application_results.py`: Discord に依存しないユースケースの結果型
- `cogs/highlight_presenter.py`: ハイライト結果を Discord の embed とフィールド制限へ整形
- `video_download_service.py`: 動画の事前確認とダウンロードのユースケース
- `youtube_highlight_service.py`: YouTube ハイライト作成とグラフの保存
- `download_engine.py`: yt-dlp オプション、再試行、ダウンロードのオーケストレーション
- `artifact_store.py`: 成果物の保存先、衝突検査、移動、ロールバック
- `chat_highlights.py`: リプレイチャットの収集、ピーク検出、グラフ描画
- `setting.py`: 環境変数からの設定と、起動時に読み込む Cog の初期一覧

## コマンドと自動ルーティング

コマンドプレフィックスは `!` です。ユーザーが実行できるメディアコマンドは次の
3 つです。

```text
!youtube download <url>
!youtube highlight <url>
!twitch download <url>
```

URL 引数は対象サービスの HTTP(S) URL として検証されます。URL の前後の空白は除去
されますが、対応していないホスト、認証情報付き URL、ポート付き URL は受け付けません。
対応ホストは次のとおりです。

- YouTube: `youtube.com`、`www.youtube.com`、`m.youtube.com`、`music.youtube.com`、
  `youtu.be`
- Twitch: `twitch.tv`、`www.twitch.tv`、`m.twitch.tv`、`clips.twitch.tv`

メッセージ本文が対応する HTTP(S) URL **だけ** の場合は、チャンネル設定に応じて
自動的にコマンドとして処理します。

| チャンネル設定 | YouTube URL | Twitch URL |
| --- | --- | --- |
| `DOWNLOAD_CHANNEL` | `youtube download` | `twitch download` |
| `HIGHLIGHT_CHANNEL` | `youtube highlight` | 無視 |

URL の前後の空白は許可されますが、URL の周囲に説明文などがあるメッセージは対象外です。
bot が投稿したメッセージ、対応していないホスト、対象外のチャンネル、通常の `!` コマンド
も自動ルーティングしません。

自動ルーティングで動画の取得やハイライト作成に失敗した場合も、投稿元へエラーを返信し、
ログチャンネルへマスク済みの詳細を送ります。

所有者限定の管理コマンドは次のとおりです。

```text
!system close
!cog load <name>
!cog reload <name>
!cog unload <name>
```

Cog コマンドの `<name>` には `all` を指定できます。`all` または `systemcog` を
unload する場合は、意図しない停止を防ぐため `-f` も必要です。

## YouTube・Twitch の処理差分

両サイトのダウンロードは共通の `DownloadEngine` を使い、完了した成果物を一時領域
から保存先へ移動します。サイトごとのポリシーは次のとおりです。

- **YouTube**: スケジュール済み・ライブ開始待ちと判定できるメタデータ取得エラーを、
  最大 10 回または待機時間の合計 6 時間まで再試行します。ライブ配信は開始時点から
  取得し、メタデータとサムネイルの成果物を必須とします。
- **Twitch**: 汎用 yt-dlp ポリシーを使うため、上記のスケジュール再試行と
  `live_from_start` は行いません。オフラインの配信は専用のメッセージで通知します。
  `cookie/cookies.txt` が存在すると Cookie ファイルを指定し、メタデータとサムネイルは
  任意の成果物として扱います。
- **ハイライト**: YouTube のみ対応します。リプレイチャットを読み込み、30 秒単位で
  コメント数を集計して活動ピークを検出し、リンクとグラフを投稿した後にグラフを保存します。

## 成果物の配置

既定値での配置は次のとおりです。`<timestamp>` は `YYYY-MM-DD-HHMM` 形式です。

```text
downloads/
├── <timestamp>_<video-id>.<video-extension>
├── metadata/
│   └── <timestamp>_<video-id>.<metadata-extension>
├── thumbnail/
│   └── <timestamp>_<video-id>.<image-extension>
├── graph/
│   └── scoregraph_<timestamp>_<video-id>.png
└── cache/                 # ダウンロード処理中の一時領域
logs/
└── discord_bot_main.log
```

動画は `SAVE_PATH` 直下、メタデータとサムネイルはその `metadata/` と `thumbnail/`
に保存されます。yt-dlp の出力形式により、メタデータやサムネイルが複数になる場合が
あります。ハイライトのグラフは `TMP_PATH` で生成して Discord へ投稿し、成功後に
`GRAPH_SAVE_PATH` へ移動します。既定ではいずれも `downloads/` 配下です。

## 拡張方法

Cog を追加する場合は、`src/yt_dl_bot/cogs/` 以下に async な `setup(bot)` 関数を持つ
モジュールを作り、`commands.Cog` にコマンドまたは listener を登録します。そのモジュール
の import path を `setting.py` の `DEFAULT_INITIAL_EXTENSIONS` に追加してください。
コマンドハンドラー内で設定やサービスを直接構築せず、`bot.settings` と `bot.services`
から利用します。

新しいダウンロード元を追加する場合は、まず `url_validation.py` に厳密な URL 識別と検証を
追加します。yt-dlp の処理が適用できるなら `DownloadEngine` と適切な `DownloadPolicy` を
再利用し、安定した結果型とアプリケーションエラーを公開するサービスでラップします。
そのサービスを `ApplicationServices` に追加し、Discord 固有の表示は専用 Cog に置きます。
ネットワーク、時計、待機、ファイルシステムに依存する処理はコラボレーターを明示的に
受け取る設計にすると、テストで置き換えられます。

## Docker Compose

まずリポジトリ直下に `.env` を用意してから、Compose の設定を検証して起動します。

```sh
docker compose config --quiet
docker compose up -d
```

Compose は次のマウントを行います。

- `DOWNLOADS_PATH` -> `/app/downloads`（動画、メタデータ、サムネイル、グラフ）
- `COOKIE_PATH` -> `/app/cookie`（読み取り専用）
- `./logs` -> `/app/logs`（アプリケーションログ）

コンテナは外部データベースなしで bot を実行します。ホスト側のディレクトリを変更した
場合でも、アプリケーション内のパスは `/app/downloads`、`/app/cookie`、`/app/logs` の
ままです。設定の補間だけを確認する場合は、CI と同じく次を実行できます。

```sh
docker compose --env-file .env.example config --quiet
```

このコマンドは Discord への接続やチャンネル ID の有効性までは検査しません。

## テストと静的検査

ロック済み依存関係を同期した後、CI と同じ主な検査を実行できます。

```sh
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run mypy
uv run coverage run -m unittest discover -s tests -v
uv run coverage report
uv run pip-audit
uv lock --check
docker compose --env-file .env.example config --quiet
```

CI は `src/`、`tests/`、`scripts/` に対する Ruff の整形・lint、`src/yt_dl_bot` 全体の
型検査、ブランチカバレッジ 85% 以上を検証します。整形を適用する場合は次を実行します。

```sh
uv run ruff format src tests scripts
```

### ブラックボックス受け入れテスト

`acceptance/` は実装を参照せずに振る舞いを検証するための狭いテスト領域です。
まず `acceptance/contracts/` の契約を読み、テストでは `acceptance/support/` の
アダプターだけを使用してください。ローカルルールは `acceptance/AGENTS.md` にあります。

```sh
./acceptance/run-tests
```

### 外部統合 smoke test

必須ではない **External integration smoke** workflow は、毎週月曜日 04:17 UTC に実行され、
Actions タブの **Run workflow** からも手動起動できます。次の 3 つの境界を個別に検査します。

- メディアをダウンロードしない yt-dlp のメタデータ抽出
- アーカイブ済み YouTube チャットリプレイの pytchat 初回バッチ取得
- 1 秒の合成音源を使ったローカル `ffmpeg`/`ffprobe` 実行とメタデータ後処理

ffmpeg ジョブは実行前に `ffmpeg` と `ffprobe` をインストールします。通常のユニットテスト
ではこれらの実行ファイルをモックするため、システムのマルチメディアパッケージは不要です。
各ジョブには再試行回数と 5 分のプロセスタイムアウトがあり、レポートは GitHub の step
summary に出力され、JSON artifact として 14 日間保持されます。外部サービスの可用性、
地域・レート制限、動画の削除、YouTube の応答変更による一時的な失敗があり得るため、
この workflow は pull request の CI には含まれません。失敗時は一度再実行してから、
統合側の変更かどうかを判断してください。

既定の対象は公開テスト動画で、認証情報は使用しません。スケジュール実行ではリポジトリ
変数 `YTDLP_SMOKE_URL` と `PYTCHAT_SMOKE_VIDEO_ID` で対象を上書きできます。手動実行の
入力がある場合はリポジトリ変数より優先されます。上書き対象も公開アクセス可能である必要が
あり、この workflow が完全なメディアをダウンロードすることはありません。

ffmpeg の決定的な probe はローカルでも実行できます。

```sh
uv run python scripts/external_smoke.py ffmpeg
```

検証ヘルパーは通常のオフラインユニットテストでカバーされています。yt-dlp と pytchat
の probe は外部メディアサービスへの依存を避けるため、週次・手動 workflow でのみ実行します。

現在の pytchat 0.5.5 では、以前の既定リプレイが無効になったため、既定値を有効な公開
アーカイブへ置き換えています。ただし、そのアーカイブは pytchat にリプレイとして認識
される一方、リプレイ要求の初回バッチが空になることがあります。他の公開アーカイブでも
タイムアウトなど同様の挙動が確認されているため、pytchat ジョブは調査が完了するまで
空バッチを成功扱いせず、失敗したままにします。

`mypy` は全関数の完全な型注釈、完全なジェネリック型引数とデコレーター、明示的な Optional
型、安全な戻り値、厳密な等価性検査、到達不能コード、未使用設定の検査を要求します。型情報を
持たない外部 API の値は、実行時検証で絞り込むまで入力境界で `object` として扱います。
第三者ライブラリの型情報不足に対する限定的な `ignore_missing_imports` と discord.py
デコレーターの ignore には、それぞれ設定または呼び出し箇所に理由を記載しています。

## ライセンス

MIT License（詳細は [LICENSE](LICENSE) を参照してください）。
