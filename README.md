# anki-gemini-notion

Ankiでの英語学習にAI（Gemini）の言語学的分析を加え、その結果を自動的にNotionへデータベース化する自動化ツールです。

## 使用ツール (Tech Stack)
- **Anki**: 学習データの管理・入力
- **Gemini API (Google AI Studio)**: 聴覚的・認知的障壁の言語学的分析
- **Notion API**: 分析データの蓄積・可視化ダッシュボード

## 概要 (Overview)
英語学習者が「なぜ聞き取れなかったのか」という原因をAIが即座に分析します。
単なる意味の解説ではなく、「リエゾン」「フラッピング」「音の消失」などの音韻論的な特徴や、文法構造による認知的な負荷を特定し、Notionへ自動的に記録します。

## 特徴 (Features)
- **自動言語分析**: カードを追加した瞬間にGeminiが「日本人の脳がなぜその音を拾えないのか」を日本語で解説。
- **5カテゴリ分類**: ミスの原因を [Liaison, Flapping, Vocabulary, Grammar, Speed] の5つに自動分類。
- **Notion連携**: 日付、英文、和訳、カテゴリ、分析結果をリアルタイムで同期。
- **config.json対応**: APIキーやフィールド名をプログラム本体から分離し、セキュアかつ汎用的な設計を実現。

## セットアップ (Setup)
1. GitHubから `__init__.py` と `config.json` をダウンロードし、Ankiのアドオンフォルダに配置。
   
2. Ankiのアドオン設定画面（config）から以下の項目を入力してください。

```json
{
    "NOTION_TOKEN": "あなたのNotionトークン",
    "DATABASE_ID": "あなたのデータベースID",
    "GEMINI_API_KEY": "あなたのGemini APIキー",
    "TARGET_NOTE_TYPE": "使用するノートタイプ名",
    "FIELD_SENTENCE": "英文が入力されているフィールド名",
    "FIELD_TRANSLATION": "和訳が入力されているフィールド名"
}
```

​3. Notion側で以下のプロパティを持つデータベースを作成してください。
・​English study: タイトル型

​・日本語訳: テキスト型

​・日付: 日付型

​・エラーカテゴリ: マルチセレクト型 (Liaison, Flapping, Vocabulary, Grammar, Speed)

・​分析: テキスト型
