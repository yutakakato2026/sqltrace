import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
import re
import sqlite3
import uuid

# =========================
# 基本設定
# =========================
st.set_page_config(
    page_title="SQLTrace",
    page_icon="🧩",
    layout="wide"
)

st.title("🧩 SQLTrace")
st.caption("SQL学習ログ・構造化トレーニングアプリ")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "sqltrace_log.csv"
SAMPLE_DB_PATH = "data/sqltrace_sample.db"

COLUMNS = [
    "SQLログID",
    "日付",
    "教材",
    "問題タイトル",
    "学習段階",
    "学習対象",
    "言語_技術",
    "難易度",

    "問われていること",
    "必要テーブル",
    "必要列",
    "集計粒度",
    "条件",
    "出力列",
    "並び替え",

    "自分のSQL",
    "正解SQL_改善SQL",
    "使用構文",
    "WITH使用",
    "SQL実行結果",

    "正誤",
    "解答時間_秒",
    "ミス分類",
    "ミス原因",
    "次回ルール",
    "理解度",
    "再現したい度",

    "ChatGPTプロンプト",
    "ChatGPT回答貼り戻し",
    "レビュー後_正解SQL",
    "レビュー後_ミス分類",
    "レビュー後_ミス原因",
    "レビュー後_次回ルール",

    "再練習済み",
    "再練習日",
    "再練習メモ",
]

# =========================
# CSV読み込み＆保存関数
# =========================
def load_data():
    if CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH)

        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""

        return df[COLUMNS]

    return pd.DataFrame(columns=COLUMNS)

def save_data(new_row):
    new_row = new_row.copy()

    if not str(
        new_row.get("SQLログID", "")
    ).strip():
        new_row["SQLログID"] = create_sql_log_id()

    df = load_data()

    df = pd.concat(
        [
            df,
            pd.DataFrame([new_row])
        ],
        ignore_index=True
    )

    df[COLUMNS].to_csv(
        CSV_PATH,
        index=False,
        encoding="utf-8-sig"
    )

def update_data(df):
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df[COLUMNS].to_csv(CSV_PATH, index=False, encoding="utf-8-sig")


# =========================
# SQLTrace 練習ログID作成関数
# =========================
def create_sql_log_id():
    return (
        "SQL_"
        + uuid.uuid4().hex[:8].upper()
    )

# =========================
# ChatGPT回答の貼り戻し分解関数
# =========================
def extract_section(text, start_label, end_label=None):
    if not isinstance(text, str) or text.strip() == "":
        return ""

    if end_label:
        pattern = rf"{re.escape(start_label)}：\s*(.*?)(?={re.escape(end_label)}：)"
    else:
        pattern = rf"{re.escape(start_label)}：\s*(.*)"

    match = re.search(pattern, text, re.S)
    return match.group(1).strip() if match else ""

# =========================
# DBからスキーマ取得関数
# =========================
def get_database_schema(db_path):
    db_file = Path(db_path)

    if not db_file.exists():
        return {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)

    tables = [row[0] for row in cursor.fetchall()]

    schema = {}

    for table in tables:
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = cursor.fetchall()

        schema[table] = [
            {
                "name": col[1],
                "type": col[2]
            }
            for col in columns
        ]

    conn.close()

    return schema

# 選択したテーブルの列をプロンプト用に整形する関数 ============
def format_schema_for_prompt(schema, selected_tables):
    lines = []

    for table in selected_tables:
        columns = [
            col["name"]
            for col in schema[table]
        ]

        lines.append(
            f"{table}({', '.join(columns)})"
        )

    return "\n".join(lines)

# =====================
# 問題1だけを切り出す関数
#=======================
def extract_problem_block(text, problem_no=1):
    start_marker = f"## 問題{problem_no}"
    next_marker = f"## 問題{problem_no + 1}"

    start = text.find(start_marker)

    if start == -1:
        return ""

    end = text.find(next_marker, start)

    if end == -1:
        return text[start:].strip()

    return text[start:end].strip()


# =========================
# 選択肢
# =========================
learning_stages = [
    "SELECT基礎",
    "WHERE条件",
    "ORDER BY",
    "集計_GROUP BY",
    "HAVING",
    "CASE",
    "JOIN",
    "サブクエリ",
    "WITH_CTE",
    "ウィンドウ関数",
    "総合問題"
]

mistake_types = [
    "なし",
    "問題理解ミス",
    "テーブル・列選択ミス",
    "JOINミス",
    "粒度・GROUP BYミス",
    "WHERE/HAVINGミス",
    "集計関数ミス",
    "CASEミス",
    "WITH/サブクエリ分解ミス",
    "構文ミス",
    "処理順序ミス",
    "その他"
]

syntax_options = [
    "SELECT",
    "WHERE",
    "ORDER BY",
    "GROUP BY",
    "HAVING",
    "JOIN",
    "CASE",
    "サブクエリ",
    "WITH",
    "ウィンドウ関数"
]

# 演習作成用
exercise_topics = [
    "SELECT基礎",
    "WHERE条件",
    "ORDER BY",
    "集計_GROUP BY",
    "HAVING",
    "CASE",
    "JOIN",
    "サブクエリ",
    "WITH_CTE",
    "VIEW",
    "総合問題"
]

exercise_difficulties = [
    "基礎",
    "標準",
    "応用"
]

exercise_formats = [
    "問題のみ",
    "問題＋ヒント",
    "問題＋ヒント＋正解SQL",
    "SQLTrace転記用"
]


# =========================
# セッション状態の初期化
# =========================
if "reviewed_sql" not in st.session_state:
    st.session_state["reviewed_sql"] = ""

if "reviewed_mistake_type" not in st.session_state:
    st.session_state["reviewed_mistake_type"] = "なし"

if "reviewed_mistake_reason" not in st.session_state:
    st.session_state["reviewed_mistake_reason"] = ""

if "reviewed_next_rule" not in st.session_state:
    st.session_state["reviewed_next_rule"] = ""


# =====================================
# ChatGPT出題結果 → 問題構造への反映
# =====================================
if "pending_exercise_problem" in st.session_state:

    pending = st.session_state["pending_exercise_problem"]

    st.session_state["learning_stage"] = pending.get(
        "learning_stage",
        ""
    )

    st.session_state["asked"] = pending.get("asked", "")
    st.session_state["tables"] = pending.get("tables", "")
    st.session_state["columns_needed"] = pending.get("columns_needed", "")
    st.session_state["grain"] = pending.get("grain", "")
    st.session_state["condition"] = pending.get("condition", "")
    st.session_state["output_columns"] = pending.get(
        "output_columns",
        ""
    )
    st.session_state["sort_rule"] = pending.get("sort_rule", "")
    st.session_state["correct_sql"] = pending.get("correct_sql", "")

    del st.session_state["pending_exercise_problem"]
# =========================
# 入力フォームではなく通常入力
# =========================
# =========================
# 1. 基本情報
# =========================
with st.expander("1. 基本情報", expanded=True):

    learning_target = st.selectbox(
    "学習対象",
    ["SQL", "Python", "pandas", "その他"],
    index=0
    )

    language_tech = st.selectbox(
        "言語・技術",
        [
            "SQL / Progate",
            "SQL / SQLite",
            "SQL",
            "Python",
            "Python / pandas",
            "その他"
        ],
        index=0
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        input_date = st.date_input("日付", value=date.today())
        material = st.text_input("教材", placeholder="例：SQLBolt / Progate / 自作問題")

    with col2:
        problem_title = st.text_input("問題タイトル", placeholder="例：JOIN演習1")
        learning_stage = st.selectbox(
            "学習段階",
            learning_stages,
            key="learning_stage"
        )

    with col3:
        difficulty = st.selectbox("難易度", ["易しい", "普通", "難しい"])

# =========================
# 2. 問題構造
# =========================
with st.expander("2. 問題構造", expanded=True):

    asked = st.text_area(
        "問われていること",
        placeholder="例：商品カテゴリ別の売上合計を求める",
        key="asked"
    )

    col1, col2 = st.columns(2)

    with col1:
        tables = st.text_area(
            "必要テーブル",
            placeholder="例：orders, order_items, products",
            key="tables"
        )

        columns_needed = st.text_area(
            "必要列",
            placeholder="例：order_id, product_id, price, quantity",
            key="columns_needed"
        )

        grain = st.text_input(
            "集計粒度",
            placeholder="例：商品カテゴリ単位 / 顧客単位 / 月単位",
            key="grain"
        )

    with col2:
        condition = st.text_area(
            "条件",
            placeholder="例：2026年の注文のみ",
            key="condition"
        )

        output_columns = st.text_area(
            "出力列",
            placeholder="例：category, total_sales",
            key="output_columns"
        )

        sort_rule = st.text_input(
            "並び替え",
            placeholder="例：total_salesの降順",
            key="sort_rule"
        )

# =========================
# 3. SQL記録
# =========================
with st.expander("3. SQL記録", expanded=False):

    my_sql = st.text_area(
        "自分のSQL",
        height=180,
        placeholder="ここに自分で書いたSQLを貼ります"
    )

    correct_sql = st.text_area(
        "正解SQL / 改善SQL",
        height=180,
        placeholder="模範SQLや改善後SQLを貼ります",
        key="correct_sql"
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        used_syntax = st.multiselect("使用構文", syntax_options)

    with col2:
        with_used = st.selectbox("WITH使用", ["いいえ", "はい"])

    with col3:
        sql_result = st.selectbox(
            "SQL実行結果",
            ["未確認", "正しい", "エラー", "結果違い"]
        )

# =========================
# 4. 振り返り
# =========================
with st.expander("4. 振り返り", expanded=False):

    col1, col2, col3 = st.columns(3)

    with col1:
        correctness = st.selectbox("正誤", ["正解", "一部正解", "不正解", "未確認"])
        answer_time = st.number_input("解答時間_秒", min_value=0, step=10)

    with col2:
        mistake_type = st.selectbox("ミス分類", mistake_types)
        understanding = st.slider("理解度", 1, 5, 3)

    with col3:
        reproducibility = st.slider("再現したい度", 1, 5, 3)

    mistake_reason = st.text_area(
        "ミス原因",
        placeholder="例：JOINキーを確認せず、誤った列で結合した"
    )

    next_rule = st.text_area(
        "次回ルール",
        placeholder="例：JOIN前に主キー・外部キー・粒度を確認する"
    )


# =============================
# ChatGPTレビュー用プロンプト生成
# =============================
chatgpt_prompt = f"""
以下は、私がSQL学習のために整理した問題構造と自分のSQLです。
著作権に配慮し、元の問題文を復元せず、構造・SQL改善・ミス分類・次回ルールに絞ってレビューしてください。

# 学習段階
{learning_stage}

# 問われていること
{asked}

# 必要テーブル
{tables}

# 必要列
{columns_needed}

# 集計粒度
{grain}

# 条件
{condition}

# 出力列
{output_columns}

# 並び替え
{sort_rule}

# 自分のSQL
{my_sql}

# 正解SQL / 改善SQL
{correct_sql}

# 現時点の自己評価
正誤：{correctness}
ミス分類：{mistake_type}
ミス原因：{mistake_reason}


# レビューしてほしいこと
1. 問題構造の捉え方は合っているか
2. SQLの誤り・改善点
3. 必要に応じた改善SQL
4. ミス分類
5. 次回同じミスを防ぐルール

# 回答方針
回答は簡潔にしてください。
元の問題文は復元せず、SQLTraceへ貼り戻す内容だけ返してください。
以下の4項目以外は出力しないでください。
レビュー後_正解SQLは、Markdownのコードブロックを使わず、SQL本文のみを記載してください。
レビュー後_ミス分類は、次の中から1つだけ選んでください。
なし / 問題理解ミス / テーブル・列選択ミス / JOINミス / 粒度・GROUP BYミス / WHERE/HAVINGミス / 集計関数ミス / CASEミス / WITH/サブクエリ分解ミス / 構文ミス / 処理順序ミス / その他
集計していない問題では、集計粒度の記録が自然かも確認してください。

# 回答形式
レビュー後_正解SQL：
レビュー後_ミス分類：
レビュー後_ミス原因：
レビュー後_次回ルール：
"""

# =========================
# ChatGPT連携
# =========================
with st.expander("🤖 ChatGPT連携", expanded=False):

    tab_question, tab_review, tab_response, tab_organize = st.tabs(
        [
            "📄 出題",
            "✅ レビュー",
            "📥 回答貼り戻し",
            "📝 レビュー後整理"
        ]
    )

    # =========================
    # 出題
    # =========================
    with tab_question:

        st.caption(
                    "学習テーマに合わせて、"
                    "ChatGPTへ渡す演習問題作成プロンプトを生成します。"
        )

        db_schema = get_database_schema(SAMPLE_DB_PATH)

        if not db_schema:
            st.warning("サンプルDBが見つかりません。出題機能を使うには data/sqltrace_sample.db を配置してください。")
            st.stop()

        st.write("### 使用可能テーブル")

        st.write(list(db_schema.keys()))

        selected_tables = st.multiselect(
            "出題に使用するテーブル",
            options=list(db_schema.keys()),
            key="exercise_selected_tables"
        )

        exercise_tables = format_schema_for_prompt(
            db_schema,
            selected_tables
        )

        # 確認用 =========================
        st.write("### 選択したテーブル定義")
        st.code(exercise_tables)
        # ================================
        col1, col2, col3 = st.columns(3)

        with col1:
            exercise_topic = st.selectbox(
                "学習テーマ",
                exercise_topics,
                key="exercise_topic"
            )
            # =========================
            # 出題条件チェック
            # =========================
            validation_error = False

            if exercise_topic == "JOIN" and len(selected_tables) < 2:
                st.warning(
                    "JOIN問題を作成するには、テーブルを2つ以上選択してください。"
                )
                validation_error = True

            elif len(selected_tables) == 0:
                st.warning(
                    "出題に使用するテーブルを1つ以上選択してください。"
                )
                validation_error = True
            # ==================================
        with col2:
            exercise_difficulty = st.selectbox(
                "難易度",
                exercise_difficulties,
                key="exercise_difficulty"
            )

        with col3:
            exercise_count = st.number_input(
                "問題数",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
                key="exercise_count"
            )

        exercise_focus = st.text_area(
            "練習したい観点",
            height=100,
            placeholder=(
                "例：集計粒度、条件指定、"
                "CTEでの段階分解、JOIN条件"
            ),
            key="exercise_focus"
        )

        exercise_format = st.selectbox(
            "出題形式",
            exercise_formats,
            key="exercise_format"
        )

        exercise_prompt = f"""
以下の条件で、SQL学習用の演習問題を作成してください。

# 目的
SQLの構造化力を鍛えることです。
既存教材や元の問題文を復元せず、新しい架空の演習問題を作ってください。

# 学習テーマ
{exercise_topic}

# 難易度
{exercise_difficulty}

# 使用テーブル定義
{exercise_tables}

# 問題数
{exercise_count}問

# 練習したい観点
{exercise_focus}

# 出題形式
{exercise_format}

# 問題作成ルール
1. 既存教材の問題文を再現しない
2. 学習テーマを必ず使う
3. SQLTraceに記録しやすい形式にする
4. 1問ごとに「問われていること」「必要テーブル」「必要列」「集計粒度」「条件」「出力列」「並び替え」を明示する
5. 正解SQLを出す場合は、読みやすく改行して書く
6. 初学者が段階的に解ける難易度にする
7. 各問題は似た形式に偏らないようにする
8. 同じ学習テーマ内でも、抽出・集計・条件指定・並び替え・段階分解の観点を変える
9. 「問題のみ」の場合は正解SQLを出さず、「正解SQL：記載なし」とする
10. 「問題＋ヒント＋正解SQL」または「SQLTrace転記用」の場合のみ正解SQLを出す
11. 問題作成には「使用テーブル定義」に記載されたテーブルと列だけを使用する
12. 「使用テーブル定義」に存在しないテーブル・列を新しく作らない
13. 複数問題を作成する場合も、すべての問題を「使用テーブル定義」の範囲内で作成する

# 出力形式

## 問題1
問題文：
学習段階：
問われていること：
必要テーブル：
必要列：
集計粒度：
条件：
出力列：
並び替え：
ヒント：
正解SQL：

## 問題2
問題文：
学習段階：
問われていること：
必要テーブル：
必要列：
集計粒度：
条件：
出力列：
並び替え：
ヒント：
正解SQL：
"""

        # 初回だけプロンプトを設定
        if "edited_exercise_prompt" not in st.session_state:
            st.session_state["edited_exercise_prompt"] = exercise_prompt

        # 選択内容から編集用プロンプトを更新
        st.caption("👇 出題条件を変更したら、下のボタンでプロンプトへ反映してください。")

        if st.button(
            "🔄 選択内容をプロンプトに反映",
            key="update_exercise_prompt_button",
            disabled=validation_error,
            type="primary"
        ):
            st.session_state["edited_exercise_prompt"] = exercise_prompt

        edited_exercise_prompt = st.text_area(
            "編集用：演習問題作成プロンプト",
            height=300,
            key="edited_exercise_prompt"
        )

        show_copy_prompt = st.toggle(
            "📋 コピー用プロンプトを表示",
            key="show_exercise_copy_prompt"
        )

        if show_copy_prompt:
            st.caption("右上のコピーアイコンからコピーできます。")
            st.code(
                edited_exercise_prompt,
                language="markdown"
            )

        st.divider()
        st.markdown("### 📥 ChatGPT出題結果貼り戻し")

        exercise_response = st.text_area(
            "ChatGPT出題結果",
            height=300,
            placeholder="ChatGPTで生成した問題をここに貼り付けます",
            key="exercise_response"
        )

        if st.button(
            "📥 問題1をSQLTrace入力欄へ反映",
            key="apply_exercise_problem1_button"
        ):
            problem1 = extract_problem_block(
                exercise_response,
                problem_no=1
            )

            if not problem1:
                st.warning("問題1を読み取れませんでした。")

            else:
                extracted_learning_stage = extract_section(
                    problem1,
                    "学習段階",
                    "問われていること"
                )

                extracted_asked = extract_section(
                    problem1,
                    "問われていること",
                    "必要テーブル"
                )

                extracted_tables = extract_section(
                    problem1,
                    "必要テーブル",
                    "必要列"
                )

                extracted_columns = extract_section(
                    problem1,
                    "必要列",
                    "集計粒度"
                )

                extracted_grain = extract_section(
                    problem1,
                    "集計粒度",
                    "条件"
                )

                extracted_condition = extract_section(
                    problem1,
                    "条件",
                    "出力列"
                )

                extracted_output_columns = extract_section(
                    problem1,
                    "出力列",
                    "並び替え"
                )

                extracted_sort_rule = extract_section(
                    problem1,
                    "並び替え",
                    "ヒント"
                )

                extracted_correct_sql = extract_section(
                    problem1,
                    "正解SQL"
                )

                st.session_state["pending_exercise_problem"] = {
                    "learning_stage": extracted_learning_stage,
                    "asked": extracted_asked,
                    "tables": extracted_tables,
                    "columns_needed": extracted_columns,
                    "grain": extracted_grain,
                    "condition": extracted_condition,
                    "output_columns": extracted_output_columns,
                    "sort_rule": extracted_sort_rule,
                    "correct_sql": (
                        extracted_correct_sql
                        if extracted_correct_sql != "記載なし"
                        else ""
                    ),
                }

                st.rerun()

    # =========================
    # レビュー用プロンプト
    # =========================
    with tab_review:

        st.caption(
            "問題構造・SQL・振り返りを変更したら、"
            "下のボタンでレビュー用プロンプトへ反映してください。"
        )

        # 初回だけレビュー用プロンプトを設定
        if "edited_review_prompt" not in st.session_state:
            st.session_state["edited_review_prompt"] = chatgpt_prompt

        # 現在の入力内容をレビュー用プロンプトへ反映
        if st.button(
            "🔄 入力内容をレビュー用プロンプトに反映",
            key="update_review_prompt_button",
            type="primary"
        ):
            st.session_state["edited_review_prompt"] = chatgpt_prompt

        edited_prompt = st.text_area(
            "編集用プロンプト",
            height=300,
            key="edited_review_prompt"
        )

        st.caption("右上のコピーアイコンからコピーできます。")
        st.code(
            edited_prompt,
            language="markdown"
        )

    # =========================
    # ChatGPT回答貼り戻し
    # =========================
    with tab_response:
        chatgpt_response = st.text_area(
            "ChatGPT回答貼り戻し",
            height=300,
            placeholder="ChatGPTから返ってきた4項目をここに貼ります",
            key="chatgpt_response"
        )

        parse_button = st.button(
            "貼り戻し内容を4項目に分解する",
            key="parse_chatgpt_response_button"
        )

        if parse_button:
            response_text = st.session_state.get(
                "chatgpt_response",
                ""
            )

            extracted_sql = extract_section(
                response_text,
                "レビュー後_正解SQL",
                "レビュー後_ミス分類"
            )

            extracted_mistake_type = extract_section(
                response_text,
                "レビュー後_ミス分類",
                "レビュー後_ミス原因"
            )

            extracted_mistake_reason = extract_section(
                response_text,
                "レビュー後_ミス原因",
                "レビュー後_次回ルール"
            )

            extracted_next_rule = extract_section(
                response_text,
                "レビュー後_次回ルール"
            )

            st.session_state["reviewed_sql"] = extracted_sql
            st.session_state[
                "reviewed_mistake_reason"
            ] = extracted_mistake_reason
            st.session_state[
                "reviewed_next_rule"
            ] = extracted_next_rule

            if extracted_mistake_type in mistake_types:
                st.session_state[
                    "reviewed_mistake_type"
                ] = extracted_mistake_type
            else:
                st.session_state[
                    "reviewed_mistake_type"
                ] = "その他"

            st.success("ChatGPT回答を4項目に分解しました。")

    # =========================
    # レビュー後整理
    # =========================
    with tab_organize:
        reviewed_sql = st.text_area(
            "レビュー後_正解SQL",
            height=180,
            placeholder="最終的に残す改善SQLを貼ります",
            key="reviewed_sql"
        )

        col1, col2 = st.columns(2)

        with col1:
            reviewed_mistake_type = st.selectbox(
                "レビュー後_ミス分類",
                mistake_types,
                key="reviewed_mistake_type"
            )

        with col2:
            reviewed_mistake_reason = st.text_area(
                "レビュー後_ミス原因",
                placeholder=(
                    "ChatGPTレビュー後に、"
                    "自分の言葉で短く整理したミス原因"
                ),
                key="reviewed_mistake_reason"
            )

        reviewed_next_rule = st.text_area(
            "レビュー後_次回ルール",
            placeholder="次回同じミスを防ぐための短いルール",
            key="reviewed_next_rule"
        )


# =========================
# SQLTraceログ保存
# =========================
st.divider()
st.subheader("💾 SQLTraceログを保存")

if st.button(
    "SQL学習ログを保存",
    type="primary",
    key="save_sqltrace_log"
):
    new_row = {
        "SQLログID": create_sql_log_id(),
        "日付": input_date.strftime("%Y-%m-%d"),
        "教材": material,
        "問題タイトル": problem_title,
        "学習段階": learning_stage,
        "学習対象": learning_target,
        "言語_技術": language_tech,
        "難易度": difficulty,

        "問われていること": asked,
        "必要テーブル": tables,
        "必要列": columns_needed,
        "集計粒度": grain,
        "条件": condition,
        "出力列": output_columns,
        "並び替え": sort_rule,

        "自分のSQL": my_sql,
        "正解SQL_改善SQL": correct_sql,
        "使用構文": ", ".join(used_syntax),
        "WITH使用": with_used,
        "SQL実行結果": sql_result,

        "正誤": correctness,
        "解答時間_秒": str(answer_time),
        "ミス分類": mistake_type,
        "ミス原因": mistake_reason,
        "次回ルール": next_rule,
        "理解度": str(understanding),
        "再現したい度": str(reproducibility),

        "ChatGPTプロンプト": chatgpt_prompt,
        "ChatGPT回答貼り戻し": st.session_state.get(
            "chatgpt_response",
            ""
        ),
        "レビュー後_正解SQL": st.session_state.get(
            "reviewed_sql",
            ""
        ),
        "レビュー後_ミス分類": st.session_state.get(
            "reviewed_mistake_type",
            ""
        ),
        "レビュー後_ミス原因": st.session_state.get(
            "reviewed_mistake_reason",
            ""
        ),
        "レビュー後_次回ルール": st.session_state.get(
            "reviewed_next_rule",
            ""
        ),

        "再練習済み": "",
        "再練習日": "",
        "再練習メモ": "",
    }

    save_data(new_row)

    st.success(
        f"SQLTraceログを保存しました。"
        f" ログID：{new_row['SQLログID']}"
    )

    st.rerun()
    

# =========================
# 最新ログ表示
# =========================
st.divider()
st.subheader("📌 最新ログ")

df = load_data()

if df.empty:
    st.info("まだログがありません。")
else:
    display_cols = [
        "日付",
        "教材",
        "問題タイトル",
        "学習段階",
        "難易度",
        "問われていること",
        "集計粒度",
        "正誤",
        "ミス分類",
        "次回ルール"
    ]

    existing_cols = [col for col in display_cols if col in df.columns]

    st.dataframe(
        df.tail(5)[existing_cols],
        width="stretch"
    )


# =========================
# 分析
# =========================
st.divider()

with st.expander("📊 分析", expanded=True):

    if df.empty:
        st.info("分析するログがまだありません。")
    else:
        # 数値変換
        df["解答時間_秒"] = pd.to_numeric(df["解答時間_秒"], errors="coerce")

        # =========================
        # 基本指標
        # =========================
        st.write("### 基本指標")

        col1, col2, col3, col4 = st.columns(4)

        total_count = len(df)
        correct_count = (df["正誤"] == "正解").sum()
        incorrect_count = (df["正誤"] == "不正解").sum()
        correct_rate = correct_count / total_count * 100 if total_count > 0 else 0

        with col1:
            st.metric("総ログ数", total_count)

        with col2:
            st.metric("正解数", int(correct_count))

        with col3:
            st.metric("不正解数", int(incorrect_count))

        with col4:
            st.metric("正答率", f"{correct_rate:.1f}%")


        # =========================
        # 日別演習数
        # =========================
        st.write("### 日別演習数")

        # 日付形式の混在対策
        df["日付_解析"] = pd.to_datetime(
            df["日付"].astype(str).str.strip(),
            errors="coerce",
            format="mixed"
        ).dt.date

        today = date.today()
        last_7_days = today - timedelta(days=6)

        today_count = (df["日付_解析"] == today).sum()
        last_7_count = (df["日付_解析"] >= last_7_days).sum()

        col1, col2 = st.columns(2)

        with col1:
            st.metric("今日の演習数", int(today_count))

        with col2:
            st.metric("直近7日間の演習数", int(last_7_count))

        daily_counts = (
            df.dropna(subset=["日付_解析"])
            .groupby("日付_解析")
            .size()
            .reset_index(name="演習数")
            .rename(columns={"日付_解析": "日付"})
            .sort_values("日付", ascending=False)
        )

        st.dataframe(daily_counts, width="stretch")

        with st.expander("日別演習数グラフ", expanded=False):
            daily_chart = daily_counts.sort_values("日付")
            st.bar_chart(
                daily_chart.set_index("日付")["演習数"]
            )


        # =========================
        # 目標達成スケジュール
        # =========================
        st.write("### 🎯 目標達成スケジュール")

        with st.expander("目標設定と達成予定", expanded=True):

            col1, col2, col3 = st.columns(3)

            with col1:
                target_name = st.text_input(
                    "目標名",
                    value="Progate SQL 基礎完了"
                )

            with col2:
                target_total = st.number_input(
                    "目標演習数",
                    min_value=1,
                    value=100,
                    step=1
                )

            with col3:
                target_date = st.date_input(
                    "目標達成日",
                    value=date.today() + timedelta(days=14)
                )

            # 現在の進捗
            current_count = len(df)
            remaining_count = max(target_total - current_count, 0)
            progress_rate = current_count / target_total * 100 if target_total > 0 else 0

            # 日付データの準備
            if "日付_解析" not in df.columns:
                df["日付_解析"] = pd.to_datetime(
                    df["日付"].astype(str).str.strip(),
                    errors="coerce",
                    format="mixed"
                ).dt.date

            valid_date_df = df.dropna(subset=["日付_解析"]).copy()

            today = date.today()
            last_7_days = today - timedelta(days=6)

            last_7_count = (valid_date_df["日付_解析"] >= last_7_days).sum()
            recent_daily_avg = last_7_count / 7 if last_7_count > 0 else 0

            # 現在ペースでの達成予定日
            if remaining_count == 0:
                estimated_completion_text = "達成済み"
                days_to_complete = 0
            elif recent_daily_avg > 0:
                days_to_complete = int(-(-remaining_count // recent_daily_avg))  # 切り上げ
                estimated_completion_date = today + timedelta(days=days_to_complete)
                estimated_completion_text = estimated_completion_date.strftime("%Y-%m-%d")
            else:
                estimated_completion_text = "算出不可"
                days_to_complete = None

            # 目標日までに必要な1日あたり演習数
            days_until_target = (target_date - today).days

            if remaining_count == 0:
                required_daily = 0
            elif days_until_target > 0:
                required_daily = remaining_count / days_until_target
            else:
                required_daily = remaining_count

            # 指標表示
            st.write("#### 進捗サマリー")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("現在演習数", int(current_count))

            with col2:
                st.metric("残り演習数", int(remaining_count))

            with col3:
                st.metric("進捗率", f"{progress_rate:.1f}%")

            with col4:
                st.metric("直近7日平均", f"{recent_daily_avg:.1f}問/日")

            st.write("#### 達成見込み")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("目標達成日", target_date.strftime("%Y-%m-%d"))

            with col2:
                st.metric("現在ペースでの達成予定日", estimated_completion_text)

            with col3:
                st.metric("必要ペース", f"{required_daily:.1f}問/日")

            # 判定メッセージ
            if remaining_count == 0:
                st.success(f"🎉 「{target_name}」は達成済みです。")
            elif recent_daily_avg == 0:
                st.info("直近7日間の演習記録がないため、現在ペースでの達成予定日は算出できません。")
            else:
                if estimated_completion_text != "算出不可":
                    if estimated_completion_date <= target_date:
                        st.success("現在のペースなら目標日までに達成できる見込みです。")
                    else:
                        delay_days = (estimated_completion_date - target_date).days
                        st.warning(f"現在のペースでは、目標日より約{delay_days}日遅れる見込みです。")


        # =========================
        # 学習段階別件数
        # =========================
        st.write("### 学習段階別件数")

        stage_counts = (
            df["学習段階"]
            .value_counts()
            .rename_axis("学習段階")
            .reset_index(name="件数")
        )

        st.dataframe(stage_counts, width="stretch")

        # 必要なら棒グラフも表示
        with st.expander("学習段階別件数グラフ", expanded=False):
            st.bar_chart(
                stage_counts.set_index("学習段階")["件数"]
            )

        # =========================
        # ミス分類別件数
        # =========================
        st.write("### ミス分類別件数")

        mistake_counts = (
            df["ミス分類"]
            .value_counts()
            .rename_axis("ミス分類")
            .reset_index(name="件数")
        )

        st.dataframe(mistake_counts, width="stretch")

        with st.expander("ミス分類別件数グラフ", expanded=False):
            st.bar_chart(
                mistake_counts.set_index("ミス分類")["件数"]
            )

        # =========================
        # 学習段階 × ミス分類
        # =========================
        st.write("### 学習段階 × ミス分類")

        cross = pd.crosstab(df["学習段階"], df["ミス分類"])
        st.dataframe(cross, width="stretch")

        # =========================
        # WITH使用分析
        # =========================
        st.write("### WITH使用分析")

        if "WITH使用" in df.columns:
            with_count = (df["WITH使用"] == "はい").sum()
            without_count = (df["WITH使用"] == "いいえ").sum()
            total_with_target = with_count + without_count
            with_rate = with_count / total_with_target * 100 if total_with_target > 0 else 0

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("WITH使用数", int(with_count))

            with col2:
                st.metric("WITH未使用数", int(without_count))

            with col3:
                st.metric("WITH使用率", f"{with_rate:.1f}%")

            with_counts = (
                df["WITH使用"]
                .value_counts()
                .rename_axis("WITH使用")
                .reset_index(name="件数")
            )

            st.dataframe(with_counts, width="stretch")

        else:
            st.info("WITH使用カラムがありません。")

        # =========================
        # 構文別件数
        # =========================
        st.write("### 構文別件数")

        if "使用構文" in df.columns:
            syntax_series = (
                df["使用構文"]
                .dropna()
                .astype(str)
                .str.split(", ")
                .explode()
            )

            syntax_series = syntax_series[
                (syntax_series.notna()) &
                (syntax_series.str.strip() != "") &
                (syntax_series != "nan")
            ]

            if syntax_series.empty:
                st.info("使用構文の記録がまだありません。")
            else:
                syntax_counts = (
                    syntax_series
                    .value_counts()
                    .rename_axis("使用構文")
                    .reset_index(name="件数")
                )

                st.dataframe(syntax_counts, width="stretch")

                with st.expander("構文別件数グラフ", expanded=False):
                    st.bar_chart(
                        syntax_counts.set_index("使用構文")["件数"]
                    )

        else:
            st.info("使用構文カラムがありません。")


        # =========================
        # ミスした問題一覧・再練習済みチェック
        # =========================

        st.subheader("❌ ミスした問題一覧")

        if df.empty:
            st.info("まだログがありません。")
        else:
            filtered_df = df.copy()

            if "学習段階" in filtered_df.columns:
                selected_stage = st.selectbox(
                    "学習段階で絞り込み",
                    ["すべて"] + sorted(filtered_df["学習段階"].dropna().astype(str).unique().tolist()),
                    key="miss_stage_filter"
                )

                if selected_stage != "すべて":
                    filtered_df = filtered_df[
                        filtered_df["学習段階"].astype(str) == selected_stage
                    ]

            miss_conditions = []

            if "正誤" in filtered_df.columns:
                miss_conditions.append(
                    filtered_df["正誤"].astype(str).str.contains(
                        "不正解|一部正解|×|ミス",
                        na=False
                    )
                )

            if "ミス分類" in filtered_df.columns:
                miss_conditions.append(
                    filtered_df["ミス分類"].notna()
                    & (filtered_df["ミス分類"].astype(str).str.strip() != "")
                    & (filtered_df["ミス分類"].astype(str).str.strip() != "なし")
                    & (filtered_df["ミス分類"].astype(str).str.strip() != "nan")
                )

            if "レビュー後_ミス分類" in filtered_df.columns:
                miss_conditions.append(
                    filtered_df["レビュー後_ミス分類"].notna()
                    & (filtered_df["レビュー後_ミス分類"].astype(str).str.strip() != "")
                    & (filtered_df["レビュー後_ミス分類"].astype(str).str.strip() != "なし")
                    & (filtered_df["レビュー後_ミス分類"].astype(str).str.strip() != "nan")
                )

            if miss_conditions:
                miss_mask = miss_conditions[0]
                for cond in miss_conditions[1:]:
                    miss_mask = miss_mask | cond

                miss_df = filtered_df[miss_mask].copy()
            else:
                miss_df = pd.DataFrame()

            # 未再練習のみ表示
            show_only_unretrained = st.checkbox(
                "未再練習のみ表示",
                value=True,
                key="show_only_unretrained"
            )

            if show_only_unretrained and not miss_df.empty and "再練習済み" in miss_df.columns:
                miss_df = miss_df[
                    miss_df["再練習済み"].astype(str).str.strip() != "済"
                ]

            if miss_df.empty:
                st.success("該当するミス問題はありません。")
            else:
                st.write(f"ミス件数：{len(miss_df)}件")

                display_cols = [
                    "日付",
                    "学習段階",
                    "問題タイトル",
                    "問われていること",
                    "自分のSQL",
                    "正解SQL_改善SQL",
                    "レビュー後_正解SQL",
                    "正誤",
                    "ミス分類",
                    "レビュー後_ミス分類",
                    "次回ルール",
                    "レビュー後_次回ルール",
                    "解答時間_秒",
                    "再練習済み",
                    "再練習日",
                    "再練習メモ"
                ]

                existing_cols = [col for col in display_cols if col in miss_df.columns]

                st.dataframe(
                    miss_df[existing_cols],
                    use_container_width=True
                )

                # =========================
                # 再練習済みに更新
                # =========================
                st.write("### ✅ 再練習済みチェック")

                target_index = st.selectbox(
                    "再練習済みにする問題を選択",
                    miss_df.index.tolist(),
                    format_func=lambda i: (
                        f"{i}｜"
                        f"{str(df.loc[i, '学習段階']) if '学習段階' in df.columns else ''}｜"
                        f"{str(df.loc[i, '問われていること'])[:50] if '問われていること' in df.columns else ''}"
                    ),
                    key="retrain_target_index"
                )

                retrain_memo = st.text_input(
                    "再練習メモ",
                    placeholder="例：JOIN条件と出力列を確認した",
                    key="retrain_memo"
                )

                if st.button("この問題を再練習済みにする", key="mark_retrained_button"):

                    # =========================
                    # 再練習関連カラムの準備
                    # =========================
                    for col in ["再練習済み", "再練習日", "再練習メモ"]:
                        if col not in df.columns:
                            df[col] = ""

                        df[col] = df[col].fillna("").astype(str)

                    # =========================
                    # 再練習済みに更新
                    # =========================
                    df.loc[target_index, "再練習済み"] = "済"
                    df.loc[target_index, "再練習日"] = date.today().strftime("%Y-%m-%d")
                    df.loc[target_index, "再練習メモ"] = retrain_memo

                    update_data(df)

                    st.success("再練習済みに更新しました。")
                    st.rerun()

        # =========================
        # 平均解答時間
        # =========================
        st.write("### 学習段階別 平均解答時間")

        avg_time_by_stage = (
            df.groupby("学習段階")["解答時間_秒"]
            .mean()
            .round(1)
            .rename("平均解答時間_秒")
            .reset_index()
        )

        st.dataframe(avg_time_by_stage, width="stretch")

