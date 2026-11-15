# 表セルの出典 / Table cell provenance

## 日本語

CSV/TSV、XLSX、BIFF XLS、対応するiWork IWA表のチャンクは、`sheet_name`、
`row_start/row_end`、`member_path` に加え、`table_provenance` を返します。
`search_fulltext` では `snippet`、`get_chunk` とcontextでは返した `text` の範囲に
対応するセルだけを示します。CLI・MCPは同じ処理を使います。

| フィールド | 意味 |
| --- | --- |
| `cells[].row`, `column` | 元の表の1始まりの行・列。CSV/TSVは見出しも含むレコード番号 |
| `kind` | 設定上の `header` または `data`。自動判定ではありません |
| `cell_start`, `cell_end`, `cell_length` | 元セルの抽出文字列内の範囲と全長。0始まり・終端を含まない文字位置 |
| `text_start`, `text_end` | 今回返した抜粋内でその断片が占める範囲。0始まり・終端を含まない |
| `complete` | 元セルの抽出文字列全体を含む場合だけtrue。値の科学的妥当性やキャッシュの鮮度は示しません |
| `header_start`, `header_rows` | 見出しと仮定する行の開始位置と行数 |
| `header_status` | 見出しを設定した場合は `assumed`、見出しなしなら `none` |
| `labels_in_text` | 完全な短い見出しと行ラベルを本文に添えたチャンクかどうか。セル位置の正本は `cells` |

例えば、行2・列3の4,000文字セルのうち1,200〜2,500文字だけなら、
`cell_start=1200, cell_end=2500, cell_length=4000, complete=false` です。
この断片を完全な数値として解釈しません。重なり部分は同じセル範囲として示します。
文字位置はPython/JSONで扱うUnicode文字で、UTF-8バイト位置やCSVの引用符を含む
ファイル上の位置ではありません。セル内の空白・改行・値は黙って削除しません。
XLS等の数値・日時は従来のパーサーが返す文字列表現に対する位置です。

各チャンクの本文は `chunk_size` 以下、セル出典は32件以下とし、`max_chunks` と
MCP全体の応答上限も維持します。大きな見出しは座標付きで別に索引化し、後続の
データは行・列座標から原本の見出しを確認できます。短い見出しは表示のため繰り返します。
続きや文字数上限で短縮したセルは `complete=false` とし、contextのテキスト引用にも
`table_cells`（`[row,column,start,end,length]`）を添えます。極端に小さいcontext予算では
出典を収められず、結果が省略される場合があります。`labels_in_text` は元チャンクの
表示属性で、さらに短縮した抜粋にラベルが残ることを保証しません。

設定ファイルの `[extraction]` で見出しの扱いを指定します。

```toml
[extraction]
table_header_start = 3
table_header_rows = 2
```

これは行3〜4を見出しと仮定します。それより前の空行や説明行も元の行番号で扱います。
`table_header_rows = 0` は見出しなしで、先頭レコードもデータとして保持します。
既存設定を保つため既定値は開始1・行数1です。先頭行が見出しであると確認した意味では
ありません。全ファイル・シートに共通の設定で、個別指定や自動見出し推定は行いません。
開始位置は1〜1,000,000、行数は0〜100です。設定変更は次の明示的な更新で表形式と
ZIPに反映し、未変更のPDF等は再抽出しません。

保存にはSQLite schema 3の `chunks.table_json` を使います。schema 1/2は読み取り時に
変更せず、明示的な `--index update/rebuild` のトランザクション内で移行します。
旧チャンクにはセル出典がない場合があります。表とZIPの抽出版を更新して一度再抽出し、
以後は差分再利用します。原本・設定は変更せず、予期しない失敗時はスキーマ移行も
ロールバックします。schema 3未対応の旧版アプリは更新後の索引を開けません。
旧版へ戻す場合は原本を保ち、別の派生索引を使ってください。

## English

CSV/TSV, XLSX, BIFF XLS and supported iWork IWA table chunks return
`table_provenance` alongside existing sheet, row, member, attachment and citekey
locations. In `search_fulltext`, cell spans describe the returned `snippet`; in
`get_chunk` and context they describe the returned `text`. CLI and MCP share this logic.

`cells` contains one-based `row` and `column`, configured `kind` (`header` or
`data`), half-open `cell_start/cell_end` within the original extracted cell value,
its `cell_length`, and half-open `text_start/text_end` within the returned excerpt.
Offsets count Unicode characters, not UTF-8 bytes or raw CSV quoting.
`complete` is true only for the entire extracted cell string. It does not establish
scientific validity or freshness of stored spreadsheet results. Whitespace and
newlines inside cell values are retained. Numeric/date offsets refer to the
existing parser's textual representation.

A range 1200..2500 of a 4,000-character value is a fragment (`complete=false`),
not a complete number. Overlap retains the same original offsets. Each chunk
respects `chunk_size`, contains at most 32 cell spans and participates in the
existing `max_chunks` and MCP response limits. Large headers are indexed
separately with coordinates; small headers repeat for readability. Truncated or
continuing context cells also receive compact `table_cells` citations in
`[row,column,start,end,length]` order. Very small context budgets may omit results
when their citations cannot fit. `labels_in_text` describes the original chunk's
layout and does not guarantee that labels survive subsequent excerpt clipping.

Configure `[extraction] table_header_start = 3` and `table_header_rows = 2` to
assume rows 3–4 are headers. Earlier rows retain their positions. CSV/TSV row
numbers count records, including multiline records and configured headers.
`table_header_rows = 0` keeps the first record as data. Defaults remain 1/1 for
compatibility; this is an assumption, not verified header detection.
`header_status` is `assumed` or `none`. The policy applies to all files/sheets;
per-table overrides and automatic header inference are not provided. Start accepts
1..1,000,000 and count accepts 0..100. An explicit update applies changed header
settings to table formats and ZIPs while reusing unchanged PDFs and other formats.

Storage uses SQLite schema 3 with `chunks.table_json`. Schema 1/2 indexes remain
unchanged on read. An explicit update/rebuild migrates them transactionally;
legacy chunks can lack cell provenance until updated. Table/ZIP extraction
revisions trigger one refresh and then incremental reuse. Sources/configurations
remain unchanged; unexpected failure rolls back the schema migration too.
Older applications that do not support schema 3 cannot read the upgraded index;
use a separate derived index when returning to an older application.
