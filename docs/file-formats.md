# 対応形式と抽出範囲 / File formats and extraction scope

## 日本語

対応形式は PDF、CSV、TSV、XLSX、DOCX、PPTX、DOC、XLS、TeX、Keynote、Pages、Numbers、ZIP です。画像・動画ファイルは明示的に対象外（`excluded`）です。文書内に埋め込まれた画像・動画、プレビュー、OCRも対象にしません。既存のPDF本文抽出は継続します。

| 拡張子 | 抽出する内容 | 出典位置・制約 |
|---|---|---|
| `.pdf` | 抽出可能なテキスト | ファイル先頭を1とするページ番号 |
| `.csv`, `.tsv` | セル文字列 | ヘッダを1行目とするレコード番号 |
| `.xlsx` | セル値と数式の文字列 | シート名・行番号。数式は評価しない |
| `.docx` | 本文・表・テキストボックス・ヘッダ・フッタ・脚注・文末脚注・コメントの段落 | 内部XML名と段落番号。組版後のページ番号は付けない。altChunkによる外部/埋込本文は未解析で、検出時は部分抽出 |
| `.pptx` | スライドと発表者ノートの段落・表中の文字列 | プレゼンテーションの実際のスライド順を1から数え、`page_start/end`に格納。内部XML名と段落番号も返す |
| `.doc` | Word 97–2003の本文ストーリー。フィールドは保存済み表示結果のみ | `WordDocument#main-paragraph=N`。補助ストーリー・レイアウトは対象にせず、常に部分抽出。暗号化/古い未対応版はエラー |
| `.xls` | BIFF形式のシートに保存されたセル値 | シート名・行番号。数式自体は取得できず、保存済み計算結果は古い可能性があるため部分抽出 |
| `.tex` | UTF-8、またはCP932で読める原文 | `row_start/end`は原文の行番号。TeXを実行せず、マクロ展開・include/input先の読み込み・URL取得を行わない |
| `.key`, `.pages`, `.numbers` | 旧XMLの段落、IWAの既知の本文フィールド。対応するV5表セルでは文字列・数値・真偽値・日時・期間の保存値 | XMLの要素番号、IWAのオブジェクトID/テキスト番号、表名・行番号。保存値は古い場合がある。表示上の順序/ページ/スライド番号、全表・数式の網羅性を保証できないため部分抽出 |
| `.zip` | 上記の対応文書 | `member_path`にメンバー名。内部文書の位置は`outer.docx!/word/document.xml#paragraph=N`のように保持。一般の入れ子ZIPは未解析 |

Apple形式は単一ZIP文書と、明示的にリンクされた拡張子付きディレクトリパッケージの両方に対応します。`Index.zip`の内部コンテナは文書形式の一部として解析します。パスを探すための周辺ディレクトリの走査は行いません。パッケージ中のsymlink・特殊ファイルは拒否します。未対応のセル形式や暗号化・壊れた構造は理由を返し、取得できた内容と区別します。AppleアプリやOfficeを起動しません。

既定の上限は1ファイル200 MiB（209,715,200 bytes）、コンテナの展開後の合計も200 MiBです。ZIP/OOXML/iWorkには同じサイズ・メンバー件数・圧縮率の制限を適用し、外側のZIP、内部文書、Index.zip、IWAの伸長量を共有予算で制限します。上限を超えた文書は抽出を中止します。元の文献や既存設定の上限は自動変更しません。

新規対応形式とZIPは、この実装を導入後の最初の `--index update` で、変更のない未対応記録も再抽出します。他の形式は既存の差分再利用を継続します。画像・動画は内容を読まずに`excluded`へ分類し、通常の抽出エラー集計には含めません。ディレクトリパッケージは内部ファイル一覧・サイズ・更新時刻で差分を判定し、`--verify-hashes`では内容ハッシュも確認します。原本の更新・変換・参照の書き換えは行いません。

検索結果と `get_chunk` は `extraction_status`、必要に応じて最大1000文字の`extraction_warning`（切り詰め時はフラグ付き）を返します。部分抽出はコンテキストにも明記します。出典位置は描画された文書を再現するものではありません。科学的な主張は原本で確認してください。

## English

The default per-file limit and total container expansion budget are both 200 MiB (209,715,200 bytes). Existing explicit configuration values are preserved on upgrade.

Supported formats are PDF, CSV, TSV, XLSX, DOCX, PPTX, DOC, XLS, TeX, Keynote, Pages, Numbers and ZIP. Images and videos are explicitly `excluded`, including embedded media and document previews. No OCR is performed; existing PDF text extraction continues.

- DOCX extracts paragraphs in the body, tables, text boxes, headers, footers, footnotes, endnotes and comments. Citations use XML part names and paragraph numbers, without inferred rendered page numbers. Detected altChunk content is omitted and marked partial.
- PPTX follows the presentation's slide relationships, preserving actual 1-based slide order in `page_start/end`; slide/notes XML parts and paragraph numbers identify the text.
- Binary DOC supports Word 97–2003 main-story text and saved field display results. Auxiliary stories and layout are omitted; results are partial. Citations use `WordDocument#main-paragraph=N`.
- XLS reads stored BIFF cell values with sheet/row coordinates. Formula expressions are unavailable and cached results can be stale, so extraction is partial. XLSX continues to retain literal formulas without calculation.
- TeX indexes literal UTF-8/CP932 source with source line numbers in `row_start/end`. No compilation, macro expansion, include/input file access or URL fetching occurs.
- Keynote/Pages/Numbers read legacy XML paragraphs and known IWA text fields. Common V5 table storage supports saved strings, numbers, booleans, dates and durations. XML element numbers or IWA object/text identifiers locate evidence; table names/row numbers locate supported cells. Saved cell values may be stale. Coverage, rendered ordering, page/slide numbers and formulas are not guaranteed. All iWork extraction is partial. Unknown layouts and encryption produce diagnostics rather than guessed text.
- iWork supports ZIP documents and explicitly linked directory packages with `.key`, `.pages` or `.numbers` suffixes. Only that package is inspected; symlinks and special files are rejected. `Index.zip` is an internal document container, distinct from unsupported general nested ZIP archives. No Office or Apple apps are launched.
- ZIP members use the same format policy. Nested document provenance is preserved as `outer.docx!/word/document.xml#paragraph=N`. Shared byte/member budgets cover outer ZIPs, document packages, Index.zip and IWA decompression. Existing per-file and compression-ratio limits also apply.

The first update after installing this extraction revision retries new formats and ZIPs, including unchanged cached unsupported records. Other formats retain incremental reuse. Media classification does not read or hash image/video bytes and is excluded from extraction-failure counts. Directory-package reuse considers contained names, sizes and mtimes; `--verify-hashes` also checks contents. Originals, attachment references and configured limits are never rewritten.

Full-text search and `get_chunk` expose `extraction_status` and an optional `extraction_warning`, bounded to 1000 characters with a truncation flag. Contexts also label partial extraction. Citations describe stored source locations, not a rendered reconstruction. Verify scientific claims against originals.

## Implementation references

These describe format structures; no upstream parser code or generated schemas are vendored.

- [Microsoft MS-DOC specification](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/): FIB, CLX, PlcPcd and compressed/uncompressed text pieces.
- [iWorkFileFormat schemas](https://github.com/obriensp/iWorkFileFormat/tree/master/iWorkFileInspector/iWorkFileInspector/Messages/Proto): TSP archive records and TSWP/TST field definitions.
- [SheetJS iWork format notes](https://github.com/SheetJS/notes/blob/main/iwa/README.md): IWA framing and table storage.
- [Numbers parser schemas](https://github.com/masaccio/numbers-parser/blob/main/src/protos/TSTArchives.proto) and [cell representation](https://github.com/masaccio/numbers-parser/blob/main/src/numbers_parser/cell.py): V5 cell flags, values and wide offsets.
- [Snappy raw format](https://github.com/google/snappy/blob/main/format_description.txt): bounded literal and copy decoding.
