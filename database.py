"""SQLite 连接、表结构与公共工具。"""
import os
import secrets
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "exam.db"))

SCHEMA = """
-- 题库：题目与选项都有稳定标识，封存后修改题库不影响已封存卷
CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY,                -- 稳定题目标识，如 Q-1a2b3c4d
  stem TEXT NOT NULL,
  correct_option_id TEXT,             -- 题库当前正确选项（稳定选项标识）
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS options (
  id TEXT PRIMARY KEY,                -- 稳定选项标识，如 O-1a2b3c4d
  question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  position INTEGER NOT NULL           -- 题库内展示顺序
);

-- 编排草稿：封存前 A/B 两卷各自的题序
CREATE TABLE IF NOT EXISTS arrangements (
  version TEXT NOT NULL,              -- 'A' / 'B'
  question_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  PRIMARY KEY (version, question_id)
);

-- 编排草稿：封存前 A/B 两卷各自的选项顺序
CREATE TABLE IF NOT EXISTS arrangement_options (
  version TEXT NOT NULL,
  question_id TEXT NOT NULL,
  option_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (version, question_id, option_id)
);

-- 封存批次：一次封存同时生成 A、B 两卷（同一题库修订）
CREATE TABLE IF NOT EXISTS batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- 封存题目：题库内容的快照，题号为卷内序号
CREATE TABLE IF NOT EXISTS sealed_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL REFERENCES batches(id),
  version TEXT NOT NULL,              -- 'A' / 'B'
  seq INTEGER NOT NULL,               -- 卷面题号
  question_id TEXT NOT NULL,          -- 稳定题目标识
  stem TEXT NOT NULL,                 -- 题干快照
  correct_option_id TEXT NOT NULL,          -- 封存时的正确选项
  current_correct_option_id TEXT NOT NULL   -- 勘误后的当前正确选项
);

-- 封存选项：选项文本与卷面字母的快照
CREATE TABLE IF NOT EXISTS sealed_options (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sealed_question_id INTEGER NOT NULL REFERENCES sealed_questions(id) ON DELETE CASCADE,
  option_id TEXT NOT NULL,            -- 稳定选项标识
  letter TEXT NOT NULL,               -- 本卷印出的字母 A/B/C/D
  text TEXT NOT NULL                  -- 选项文本快照
);

-- 勘误：按封存题目与当时印出的选项提交
CREATE TABLE IF NOT EXISTS errata (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL REFERENCES batches(id),
  question_id TEXT NOT NULL,          -- 稳定题目标识
  new_option_id TEXT NOT NULL,        -- 更正后的稳定选项标识
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

-- 勘误明细：各卷题号及勘误前后的选项字母
CREATE TABLE IF NOT EXISTS errata_details (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  errata_id INTEGER NOT NULL REFERENCES errata(id) ON DELETE CASCADE,
  version TEXT NOT NULL,
  seq INTEGER NOT NULL,               -- 该卷题号
  old_letter TEXT NOT NULL,           -- 勘误前字母
  new_letter TEXT NOT NULL            -- 勘误后字母
);
"""


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def new_id(prefix, conn, table):
    """生成稳定标识，如 Q-9f3ab210 / O-77c1d2e8。"""
    while True:
        value = f"{prefix}-{secrets.token_hex(4)}"
        if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (value,)).fetchone():
            return value


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
