"""双卷印发校核：Flask 后端（题库 / 编排 / 封存 / 勘误 / 打印视图）。"""
import os

from flask import Flask, abort, jsonify, redirect, render_template, request

from database import get_db, init_db, new_id, now

app = Flask(__name__)

VERSIONS = ("A", "B")
LETTERS = "ABCD"


# ---------------------------------------------------------------- 数据组装

def fetch_question(conn, qid):
    q = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    if not q:
        return None
    opts = conn.execute(
        "SELECT * FROM options WHERE question_id=? ORDER BY position", (qid,)
    ).fetchall()
    return {
        "id": q["id"],
        "stem": q["stem"],
        "correct_option_id": q["correct_option_id"],
        "updated_at": q["updated_at"],
        "options": [{"id": o["id"], "text": o["text"]} for o in opts],
    }


def ensure_arrangement(conn, version):
    """把题库中尚未进入编排草稿的题目追加到该卷末尾（选项按题库顺序）。"""
    max_seq = conn.execute(
        "SELECT COALESCE(MAX(seq),0) AS m FROM arrangements WHERE version=?", (version,)
    ).fetchone()["m"]
    rows = conn.execute("SELECT id FROM questions ORDER BY created_at, id").fetchall()
    for r in rows:
        exists = conn.execute(
            "SELECT 1 FROM arrangements WHERE version=? AND question_id=?",
            (version, r["id"]),
        ).fetchone()
        if exists:
            continue
        max_seq += 1
        conn.execute(
            "INSERT INTO arrangements(version, question_id, seq) VALUES(?,?,?)",
            (version, r["id"], max_seq),
        )
        opts = conn.execute(
            "SELECT id FROM options WHERE question_id=? ORDER BY position", (r["id"],)
        ).fetchall()
        for pos, o in enumerate(opts):
            conn.execute(
                "INSERT INTO arrangement_options(version, question_id, option_id, position)"
                " VALUES(?,?,?,?)",
                (version, r["id"], o["id"], pos),
            )


def arrangement_payload(conn, version):
    """某卷当前编排草稿：题序 + 每题选项顺序（卷面字母按此顺序生成）。"""
    ensure_arrangement(conn, version)
    conn.commit()
    rows = conn.execute(
        "SELECT question_id FROM arrangements WHERE version=? ORDER BY seq", (version,)
    ).fetchall()
    out = []
    for r in rows:
        q = fetch_question(conn, r["question_id"])
        if not q:
            continue
        order = conn.execute(
            "SELECT option_id FROM arrangement_options WHERE version=? AND question_id=?"
            " ORDER BY position",
            (version, r["question_id"]),
        ).fetchall()
        order_ids = [o["option_id"] for o in order]
        by_id = {o["id"]: o for o in q["options"]}
        ordered = [by_id[i] for i in order_ids if i in by_id]
        ordered += [o for o in q["options"] if o["id"] not in order_ids]
        out.append({
            "question_id": q["id"],
            "stem": q["stem"],
            "correct_option_id": q["correct_option_id"],
            "options": ordered,
        })
    return out


def errata_dict(conn, e):
    dets = conn.execute(
        "SELECT version, seq, old_letter, new_letter FROM errata_details"
        " WHERE errata_id=? ORDER BY version",
        (e["id"],),
    ).fetchall()
    return {
        "id": e["id"],
        "batch_id": e["batch_id"],
        "question_id": e["question_id"],
        "new_option_id": e["new_option_id"],
        "note": e["note"],
        "created_at": e["created_at"],
        "details": [dict(d) for d in dets],
    }


def batch_detail(conn, bid):
    b = conn.execute("SELECT * FROM batches WHERE id=?", (bid,)).fetchone()
    if not b:
        return None
    versions = {}
    for v in VERSIONS:
        sqs = conn.execute(
            "SELECT * FROM sealed_questions WHERE batch_id=? AND version=? ORDER BY seq",
            (bid, v),
        ).fetchall()
        items = []
        for sq in sqs:
            opts = conn.execute(
                "SELECT option_id, letter, text FROM sealed_options"
                " WHERE sealed_question_id=? ORDER BY letter",
                (sq["id"],),
            ).fetchall()
            letter_of = {o["option_id"]: o["letter"] for o in opts}
            items.append({
                "seq": sq["seq"],
                "question_id": sq["question_id"],
                "stem": sq["stem"],
                "options": [
                    {"option_id": o["option_id"], "letter": o["letter"], "text": o["text"]}
                    for o in opts
                ],
                "original_option_id": sq["correct_option_id"],
                "current_option_id": sq["current_correct_option_id"],
                "original_letter": letter_of.get(sq["correct_option_id"]),
                "current_letter": letter_of.get(sq["current_correct_option_id"]),
                "corrected": sq["correct_option_id"] != sq["current_correct_option_id"],
            })
        versions[v] = items
    ers = conn.execute(
        "SELECT * FROM errata WHERE batch_id=? ORDER BY id", (bid,)
    ).fetchall()
    return {
        "id": b["id"],
        "name": b["name"],
        "created_at": b["created_at"],
        "versions": versions,
        "errata": [errata_dict(conn, e) for e in ers],
    }


def body():
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------- 页面路由

@app.get("/")
def index():
    return redirect("/bank")


@app.get("/bank")
def page_bank():
    return render_template("bank.html")


@app.get("/arrange")
def page_arrange():
    return render_template("arrange.html")


@app.get("/batches")
def page_batches():
    return render_template("batches.html")


@app.get("/batches/<int:bid>")
def page_batch(bid):
    return render_template("batch.html", batch_id=bid)


@app.get("/batches/<int:bid>/print/<version>/<kind>")
def page_print(bid, version, kind):
    if version not in VERSIONS or kind not in ("paper", "sheet", "key"):
        abort(404)
    return render_template("print.html", batch_id=bid, version=version, kind=kind)


@app.get("/errata")
def page_errata():
    return render_template("errata.html")


# ---------------------------------------------------------------- 题库 API

@app.get("/api/questions")
def api_questions():
    conn = get_db()
    try:
        rows = conn.execute("SELECT id FROM questions ORDER BY created_at, id").fetchall()
        return jsonify({"questions": [fetch_question(conn, r["id"]) for r in rows]})
    finally:
        conn.close()


@app.post("/api/questions")
def api_create_question():
    data = body()
    stem = (data.get("stem") or "").strip()
    opts = data.get("options") or []
    correct_index = data.get("correct_index")
    errors = []
    if not stem:
        errors.append("题干不能为空")
    if len(opts) != 4:
        errors.append("必须提供 4 个选项")
    elif any(not str(o.get("text") or "").strip() for o in opts):
        errors.append("选项文本不能为空")
    if not isinstance(correct_index, int) or not 0 <= correct_index < 4:
        errors.append("必须指定正确选项")
    if errors:
        return jsonify({"errors": errors}), 400
    conn = get_db()
    try:
        qid = new_id("Q", conn, "questions")
        ts = now()
        conn.execute(
            "INSERT INTO questions(id, stem, correct_option_id, created_at, updated_at)"
            " VALUES(?,?,?,?,?)",
            (qid, stem, None, ts, ts),
        )
        oids = []
        for pos, o in enumerate(opts):
            oid = new_id("O", conn, "options")
            conn.execute(
                "INSERT INTO options(id, question_id, text, position) VALUES(?,?,?,?)",
                (oid, qid, str(o.get("text")).strip(), pos),
            )
            oids.append(oid)
        conn.execute(
            "UPDATE questions SET correct_option_id=? WHERE id=?",
            (oids[correct_index], qid),
        )
        for v in VERSIONS:
            ensure_arrangement(conn, v)  # 新题自动进入两卷编排草稿
        conn.commit()
        return jsonify({"question": fetch_question(conn, qid)}), 201
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        return jsonify({"errors": [str(e)]}), 500
    finally:
        conn.close()


@app.put("/api/questions/<qid>")
def api_update_question(qid):
    """修改题库（不影响任何已封存卷：封存卷保存的是快照）。"""
    data = body()
    conn = get_db()
    try:
        q = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        if not q:
            return jsonify({"errors": ["题目不存在"]}), 404
        stem = (data.get("stem") or "").strip()
        correct = data.get("correct_option_id")
        opt_updates = data.get("options") or []
        existing_ids = {
            r["id"]
            for r in conn.execute(
                "SELECT id FROM options WHERE question_id=?", (qid,)
            ).fetchall()
        }
        errors = []
        if not stem:
            errors.append("题干不能为空")
        if correct not in existing_ids:
            errors.append("正确选项必须属于该题")
        for ou in opt_updates:
            if ou.get("id") not in existing_ids:
                errors.append(f"选项 {ou.get('id')} 不属于该题")
            elif not str(ou.get("text") or "").strip():
                errors.append("选项文本不能为空")
        if errors:
            return jsonify({"errors": errors}), 400
        conn.execute(
            "UPDATE questions SET stem=?, correct_option_id=?, updated_at=? WHERE id=?",
            (stem, correct, now(), qid),
        )
        for ou in opt_updates:
            conn.execute(
                "UPDATE options SET text=? WHERE id=?",
                (str(ou.get("text")).strip(), ou["id"]),
            )
        conn.commit()
        return jsonify({"question": fetch_question(conn, qid)})
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        return jsonify({"errors": [str(e)]}), 500
    finally:
        conn.close()


@app.delete("/api/questions/<qid>")
def api_delete_question(qid):
    """从题库删除（同时移出编排草稿；已封存卷不受影响）。"""
    conn = get_db()
    try:
        conn.execute("DELETE FROM questions WHERE id=?", (qid,))
        for v in VERSIONS:
            conn.execute(
                "DELETE FROM arrangements WHERE version=? AND question_id=?", (v, qid)
            )
            conn.execute(
                "DELETE FROM arrangement_options WHERE version=? AND question_id=?",
                (v, qid),
            )
            rows = conn.execute(
                "SELECT question_id FROM arrangements WHERE version=? ORDER BY seq", (v,)
            ).fetchall()
            for i, r in enumerate(rows, 1):
                conn.execute(
                    "UPDATE arrangements SET seq=? WHERE version=? AND question_id=?",
                    (i, v, r["question_id"]),
                )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        return jsonify({"errors": [str(e)]}), 500
    finally:
        conn.close()


# ---------------------------------------------------------------- 编排 API

@app.get("/api/arrangement")
def api_get_arrangement():
    conn = get_db()
    try:
        return jsonify({v: arrangement_payload(conn, v) for v in VERSIONS})
    finally:
        conn.close()


@app.put("/api/arrangement/<version>")
def api_put_arrangement(version):
    if version not in VERSIONS:
        return jsonify({"errors": ["卷别不存在"]}), 404
    data = body()
    qids = data.get("questions") or []
    opt_orders = data.get("options") or {}
    conn = get_db()
    try:
        bank_ids = [r["id"] for r in conn.execute("SELECT id FROM questions").fetchall()]
        bank_set = set(bank_ids)
        seen = []
        for qid in qids:  # 过滤已不在题库中的标识
            if qid in bank_set and qid not in seen:
                seen.append(qid)
        for qid in bank_ids:  # 未提及的题目追加到末尾，保证不丢题
            if qid not in seen:
                seen.append(qid)
        conn.execute("DELETE FROM arrangements WHERE version=?", (version,))
        conn.execute("DELETE FROM arrangement_options WHERE version=?", (version,))
        for i, qid in enumerate(seen, 1):
            conn.execute(
                "INSERT INTO arrangements(version, question_id, seq) VALUES(?,?,?)",
                (version, qid, i),
            )
            db_opts = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM options WHERE question_id=? ORDER BY position", (qid,)
                ).fetchall()
            ]
            want = opt_orders.get(qid) or []
            ordered = [o for o in want if o in db_opts]
            ordered += [o for o in db_opts if o not in want]
            for pos, oid in enumerate(ordered):
                conn.execute(
                    "INSERT INTO arrangement_options(version, question_id, option_id,"
                    " position) VALUES(?,?,?,?)",
                    (version, qid, oid, pos),
                )
        conn.commit()
        return jsonify({"ok": True, "arrangement": arrangement_payload(conn, version)})
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        return jsonify({"errors": [str(e)]}), 500
    finally:
        conn.close()


# ---------------------------------------------------------------- 封存 API

@app.post("/api/seal")
def api_seal():
    """以题库当前修订一次性封存 A、B 两卷，各自按编排顺序生成卷面快照。"""
    conn = get_db()
    try:
        arrs = {v: arrangement_payload(conn, v) for v in VERSIONS}
        problems = []
        for v in VERSIONS:
            if not arrs[v]:
                problems.append(f"{v}卷没有任何题目")
            for i, item in enumerate(arrs[v], 1):
                if len(item["options"]) != 4:
                    problems.append(
                        f"{v}卷第{i}题（{item['question_id']}）选项数不是 4"
                    )
                opt_ids = [o["id"] for o in item["options"]]
                if item["correct_option_id"] not in opt_ids:
                    problems.append(
                        f"{v}卷第{i}题（{item['question_id']}）未设置正确答案"
                    )
        if problems:
            return jsonify({"errors": problems}), 400
        n = conn.execute("SELECT COUNT(*) AS c FROM batches").fetchone()["c"] + 1
        name = f"第 {n} 批封存"
        cur = conn.execute(
            "INSERT INTO batches(name, created_at) VALUES(?,?)", (name, now())
        )
        bid = cur.lastrowid
        for v in VERSIONS:
            for i, item in enumerate(arrs[v], 1):
                cur = conn.execute(
                    "INSERT INTO sealed_questions(batch_id, version, seq, question_id,"
                    " stem, correct_option_id, current_correct_option_id)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (
                        bid, v, i, item["question_id"], item["stem"],
                        item["correct_option_id"], item["correct_option_id"],
                    ),
                )
                sqid = cur.lastrowid
                for j, o in enumerate(item["options"]):
                    conn.execute(
                        "INSERT INTO sealed_options(sealed_question_id, option_id,"
                        " letter, text) VALUES(?,?,?,?)",
                        (sqid, o["id"], LETTERS[j], o["text"]),
                    )
        conn.commit()
        return jsonify({"ok": True, "batch_id": bid, "name": name}), 201
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        return jsonify({"errors": [str(e)]}), 500
    finally:
        conn.close()


@app.get("/api/batches")
def api_batches():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM batches ORDER BY id DESC").fetchall()
        out = []
        for b in rows:
            qc = conn.execute(
                "SELECT COUNT(*) AS c FROM sealed_questions"
                " WHERE batch_id=? AND version='A'",
                (b["id"],),
            ).fetchone()["c"]
            ec = conn.execute(
                "SELECT COUNT(*) AS c FROM errata WHERE batch_id=?", (b["id"],)
            ).fetchone()["c"]
            out.append({
                "id": b["id"],
                "name": b["name"],
                "created_at": b["created_at"],
                "question_count": qc,
                "errata_count": ec,
            })
        return jsonify({"batches": out})
    finally:
        conn.close()


@app.get("/api/batches/<int:bid>")
def api_batch(bid):
    conn = get_db()
    try:
        data = batch_detail(conn, bid)
        if not data:
            return jsonify({"errors": ["封存批次不存在"]}), 404
        return jsonify(data)
    finally:
        conn.close()


# ---------------------------------------------------------------- 勘误 API

@app.post("/api/errata")
def api_create_errata():
    """按封存题目与当时印出的选项提交勘误。

    校验（任一失败则整次拒绝，原答案不变）：
    - 题目在两卷都有封存映射；
    - 所选选项属于该封存题目（两卷均有此选项映射）。
    通过后在同一事务中登记勘误并更新两卷答案表。
    """
    data = body()
    batch_id = data.get("batch_id")
    question_id = (data.get("question_id") or "").strip()
    option_id = (data.get("option_id") or "").strip()
    note = (data.get("note") or "").strip()
    if not batch_id or not question_id or not option_id:
        return jsonify({"errors": ["缺少必要参数：批次、题目、选项"]}), 400
    conn = get_db()
    try:
        b = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not b:
            return jsonify({"errors": ["封存批次不存在"]}), 404
        rows = conn.execute(
            "SELECT * FROM sealed_questions WHERE batch_id=? AND question_id=?",
            (batch_id, question_id),
        ).fetchall()
        by_version = {r["version"]: r for r in rows}
        missing = [v for v in VERSIONS if v not in by_version]
        if missing:
            return jsonify({"errors": [
                f"题目 {question_id} 在 {'、'.join(missing)} 卷缺少映射，整次勘误被拒绝"
            ]}), 400
        letters = {}
        for v in VERSIONS:
            opts = conn.execute(
                "SELECT option_id, letter FROM sealed_options WHERE sealed_question_id=?",
                (by_version[v]["id"],),
            ).fetchall()
            letters[v] = {o["option_id"]: o["letter"] for o in opts}
            if option_id not in letters[v]:
                return jsonify({"errors": [
                    f"选项 {option_id} 不属于封存题目 {question_id}"
                    f"（{v}卷无此选项映射），整次勘误被拒绝"
                ]}), 400
        if all(by_version[v]["current_correct_option_id"] == option_id for v in VERSIONS):
            return jsonify({"errors": ["该选项已是两卷当前答案，无需勘误"]}), 400
        cur = conn.execute(
            "INSERT INTO errata(batch_id, question_id, new_option_id, note, created_at)"
            " VALUES(?,?,?,?,?)",
            (batch_id, question_id, option_id, note, now()),
        )
        eid = cur.lastrowid
        details = []
        for v in VERSIONS:  # 同一事务内更新两卷答案表
            sq = by_version[v]
            old_letter = letters[v].get(sq["current_correct_option_id"], "?")
            new_letter = letters[v][option_id]
            conn.execute(
                "INSERT INTO errata_details(errata_id, version, seq, old_letter,"
                " new_letter) VALUES(?,?,?,?,?)",
                (eid, v, sq["seq"], old_letter, new_letter),
            )
            conn.execute(
                "UPDATE sealed_questions SET current_correct_option_id=? WHERE id=?",
                (option_id, sq["id"]),
            )
            details.append({
                "version": v, "seq": sq["seq"],
                "old_letter": old_letter, "new_letter": new_letter,
            })
        conn.commit()
        return jsonify({"ok": True, "errata": {
            "id": eid, "batch_id": batch_id, "question_id": question_id,
            "new_option_id": option_id, "note": note, "details": details,
        }}), 201
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        return jsonify({"errors": [str(e)]}), 500
    finally:
        conn.close()


@app.get("/api/errata")
def api_list_errata():
    batch_id = request.args.get("batch_id")
    conn = get_db()
    try:
        sql = "SELECT * FROM errata"
        args = []
        if batch_id:
            sql += " WHERE batch_id=?"
            args.append(batch_id)
        sql += " ORDER BY id DESC"
        ers = conn.execute(sql, args).fetchall()
        return jsonify({"errata": [errata_dict(conn, e) for e in ers]})
    finally:
        conn.close()


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
