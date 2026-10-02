from flask import Flask, request, redirect, url_for, session, render_template_string, abort
import sqlite3
from datetime import datetime
from functools import wraps
from markupsafe import escape

app = Flask(__name__)
app.secret_key = "replace-this-with-a-long-random-secret"
DB = "bazarino.db"
ADMIN_PASSWORD = "1234"  # حتماً قبل از انتشار عوضش کنید

CATEGORIES = [
    "دیجیتال", "لوازم خانه", "مد و پوشاک", "زیبایی و سلامت",
    "ورزش و سفر", "خودرو و موتور", "اسباب‌بازی", "کتاب و لوازم‌تحریر"
]

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL CHECK(price >= 0),
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            image TEXT DEFAULT ''
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            items TEXT NOT NULL,
            total INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT DEFAULT 'در انتظار بررسی'
        )""")

init_db()

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;900&display=swap');
*{box-sizing:border-box}body{margin:0;background:#f7f5fb;color:#29213b;font-family:Vazirmatn,Tahoma,sans-serif}
a{text-decoration:none;color:inherit}header{background:#fff;box-shadow:0 4px 20px #25104412;padding:16px max(4%,calc((100% - 1150px)/2));display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.logo{font-size:27px;font-weight:900;color:#6937b7}.logo span{color:#f0bf22}nav{display:flex;gap:18px;flex-wrap:wrap;font-weight:700}nav a:hover{color:#713fc0}
main{max-width:1150px;margin:28px auto;padding:0 18px}.hero{background:linear-gradient(115deg,#6331b2,#9862dc);color:white;border-radius:24px;padding:38px;display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap}
.hero h1{font-size:clamp(24px,4vw,36px);margin:0 0 10px}.hero p{margin:0;color:#eee5ff}.hero-mark{font-size:clamp(38px,7vw,68px);font-weight:900;color:#ffda45}
h2{font-size:23px;margin:26px 0 15px}.search{display:flex;gap:10px;margin:24px 0;flex-wrap:wrap}.search input{flex:1;min-width:180px}
input,select,textarea{font:inherit;border:1px solid #ded6e9;border-radius:12px;padding:12px;background:#fff;max-width:100%;width:100%}
button,.btn{font:inherit;font-weight:700;border:0;border-radius:12px;padding:11px 17px;background:#6c38b8;color:white;cursor:pointer;display:inline-block}
button:hover,.btn:hover{filter:brightness(.95)}.yellow{background:#ffd33d;color:#34230a}.danger{background:#b62c47;color:white}
.categories{display:flex;gap:9px;flex-wrap:wrap;margin:15px 0 25px}.categories a{background:#fff;border:1px solid #e7e0ef;padding:9px 14px;border-radius:30px;font-size:14px;font-weight:700}.categories a.active{background:#6c38b8;color:#fff}
.products{display:grid;grid-template-columns:repeat(auto-fill,minmax(205px,1fr));gap:17px}.card,.panel{background:#fff;border-radius:18px;padding:16px;box-shadow:0 5px 22px #2510440c}.product-img{height:155px;border-radius:13px;background:#f1eafa;display:flex;align-items:center;justify-content:center;overflow:hidden;color:#8060b0;font-size:30px}.product-img img{width:100%;height:100%;object-fit:cover}.card h3{font-size:17px;margin:13px 0 5px}.muted{color:#81788e;font-size:13px}.price,.total{color:#6937b7;font-weight:900;font-size:19px;margin:10px 0}.card form{margin-top:10px}.card button{width:100%}.panel{margin:18px 0;padding:20px}.form-grid{display:grid;gap:12px;max-width:600px}.form-grid button{justify-self:start}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:580px}td,th{padding:11px;border-bottom:1px solid #eee;text-align:right;vertical-align:top}th{color:#6b36b8}footer{text-align:center;padding:30px;color:#81788e}.notice{padding:12px 15px;border-radius:12px;background:#fff3c5;margin:15px 0}.inline{display:inline-block;margin:3px}
@media(max-width:600px){header{padding:14px 18px}nav{gap:12px;font-size:14px}.hero{padding:25px}.panel{padding:15px}}
"""

BASE = """<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }} | بازارینو</title>
<style>""" + CSS + """</style></head><body><header>
<a class="logo" href="/">بازار<span>ینو</span></a><nav>
<a href="/">فروشگاه</a><a href="/cart">سبد خرید ({{ count }})</a>
<a href="/admin">مدیریت</a></nav></header><main>{{ body|safe }}</main>
<footer>بازارینو | خریدی ساده و هوشمند</footer></body></html>"""

def page(title, body):
    count = sum(session.get("cart", {}).values())
    return render_template_string(BASE, title=title, body=body, count=count)

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin"))
        return fn(*args, **kwargs)
    return wrapped

def fmt(n):
    return f"{n:,}"

def safe_image(url):
    url = (url or "").strip()
    if url.startswith("https://") or url.startswith("http://"):
        return str(escape(url))
    return ""

@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if cat in CATEGORIES:
        sql += " AND category=?"
        params.append(cat)
    sql += " ORDER BY id DESC"
    with connect() as con:
        products = con.execute(sql, params).fetchall()

    links = '<a href="/" class="' + ('active' if not cat else '') + '">همه</a>'
    for c in CATEGORIES:
        links += f'<a class="{"active" if cat == c else ""}" href="/?category={escape(c)}">{escape(c)}</a>'

    cards = ""
    for p in products:
        img = safe_image(p["image"])
        visual = f'<img src="{img}" alt="{escape(p["name"])}">' if img else "بازارینو"
        cards += f"""<article class="card"><div class="product-img">{visual}</div>
        <h3>{escape(p['name'])}</h3><div class="muted">{escape(p['category'])}</div>
        <p class="muted">{escape(p['description'])}</p><div class="price">{fmt(p['price'])} تومان</div>
        <form method="post" action="/add/{p['id']}"><button class="yellow">افزودن به سبد خرید</button></form></article>"""
    body = f"""<section class="hero"><div><h1>به بازارینو خوش آمدید</h1>
    <p>محصولات متنوع، تجربه خرید آسان</p></div><div class="hero-mark">بازارینو</div></section>
    <form class="search" method="get"><input name="q" placeholder="جست‌وجوی محصول..." value="{escape(q)}">
    <button class="yellow">جست‌وجو</button></form><h2>دسته‌بندی‌ها</h2><div class="categories">{links}</div>
    <h2>محصولات</h2><section class="products">{cards or '<p>هنوز محصولی ثبت نشده است.</p>'}</section>"""
    return page("فروشگاه", body)

@app.post("/add/<int:pid>")
def add(pid):
    with connect() as con:
        exists = con.execute("SELECT id FROM products WHERE id=?", (pid,)).fetchone()
    if not exists:
        abort(404)
    cart = session.get("cart", {})
    key = str(pid)
    cart[key] = min(cart.get(key, 0) + 1, 99)
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    items, total = [], 0
    with connect() as con:
        for pid, qty in cart_data.items():
            p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if p:
                subtotal = p["price"] * qty
                items.append((p, qty, subtotal))
                total += subtotal
    rows = ""
    for p, qty, subtotal in items:
        rows += f"""<tr><td>{escape(p['name'])}</td><td>{qty}</td>
        <td>{fmt(subtotal)} تومان</td><td><a href="/remove/{p['id']}">حذف</a></td></tr>"""
    checkout = ""
    if items:
        checkout = f"""<div class="panel"><h2>ثبت سفارش</h2><p class="muted">مبلغ نهایی: {fmt(total)} تومان</p>
        <form class="form-grid" method="post" action="/checkout">
        <input name="name" placeholder="نام و نام خانوادگی" required maxlength="100">
        <input name="phone" placeholder="شماره تماس" required maxlength="30">
        <textarea name="address" placeholder="نشانی کامل" required maxlength="1000"></textarea>
        <button class="yellow">ثبت سفارش</button></form></div>"""
    body = f"""<h2>سبد خرید</h2><div class="panel"><div class="table-wrap"><table>
    <tr><th>محصول</th><th>تعداد</th><th>مبلغ</th><th>عملیات</th></tr>{rows or '<tr><td colspan="4">سبد خرید خالی است.</td></tr>'}
    </table></div><p class="total">مجموع: {fmt(total)} تومان</p><a class="btn" href="/">ادامه خرید</a></div>{checkout}"""
    return page("سبد خرید", body)

@app.post("/checkout")
def checkout():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    cart_data = session.get("cart", {})
    if not name or not phone or not address or not cart_data:
        return redirect(url_for("cart"))
    details, total = [], 0
    with connect() as con:
        for pid, qty in cart_data.items():
            p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if p:
                details.append(f"{p['name']} × {qty}")
                total += p["price"] * qty
        if not details:
            return redirect(url_for("cart"))
        cur = con.execute("""INSERT INTO orders(customer,phone,address,items,total,date)
            VALUES(?,?,?,?,?,?)""",
            (name, phone, address, "، ".join(details), total,
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        order_id = cur.lastrowid
    session["cart"] = {}
    return page("سفارش ثبت شد", f"""<div class="panel"><h2>سفارش ثبت شد</h2>
    <p>شماره سفارش: <b>{order_id}</b></p><p>مبلغ: {fmt(total)} تومان</p>
    <div class="notice">این نسخه پرداخت آنلاین ندارد؛ سفارش فقط در سایت ثبت شده است.</div>
    <a class="btn yellow" href="/">بازگشت به فروشگاه</a></div>""")

@app.route("/remove/<int:pid>")
def remove(pid):
    cart = session.get("cart", {})
    cart.pop(str(pid), None)
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        error = ""
        if request.method == "POST":
            if request.form.get("password") == ADMIN_PASSWORD:
                session["admin"] = True
                return redirect(url_for("admin"))
            error = '<p class="notice">رمز عبور اشتباه است.</p>'
        return page("ورود مدیریت", f"""<div class="panel"><h2>ورود مدیر</h2>{error}
        <form method="post" class="form-grid"><input type="password" name="password" placeholder="رمز مدیریت" required>
        <button class="yellow">ورود</button></form></div>""")
    with connect() as con:
        products = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        orders = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    options = "".join(f'<option value="{escape(c)}">{escape(c)}</option>' for c in CATEGORIES)
    prows = ""
    for p in products:
        prows += f"""<tr><td>{escape(p['name'])}</td><td>{fmt(p['price'])}</td><td>{escape(p['category'])}</td>
        <td><a class="inline" href="/edit/{p['id']}">ویرایش</a>
        <form class="inline" method="post" action="/delete/{p['id']}" onsubmit="return confirm('حذف شود؟')">
        <button class="danger">حذف</button></form></td></tr>"""
    orows = ""
    for o in orders:
        orows += f"""<tr><td>{o['id']}</td><td>{escape(o['customer'])}</td><td>{escape(o['phone'])}</td>
        <td>{escape(o['items'])}</td><td>{fmt(o['total'])}</td><td>{escape(o['date'])}</td>
        <td>{escape(o['status'])}</td></tr>"""
    body = f"""<h2>پنل مدیریت</h2><p><a href="/logout">خروج از پنل</a></p>
    <div class="panel"><h2>افزودن محصول</h2><form method="post" action="/new" class="form-grid">
    <input name="name" placeholder="نام محصول" required maxlength="150">
    <input name="price" type="number" min="0" placeholder="قیمت به تومان" required>
    <select name="category">{options}</select><textarea name="description" placeholder="توضیحات" maxlength="1000"></textarea>
    <input name="image" type="url" placeholder="لینک تصویر (اختیاری)">
    <button class="yellow">ثبت محصول</button></form></div>
    <div class="panel"><h2>محصولات</h2><div class="table-wrap"><table>
    <tr><th>نام</th><th>قیمت</th><th>دسته‌بندی</th><th>عملیات</th></tr>
    {prows or '<tr><td colspan="4">محصولی ثبت نشده.</td></tr>'}</table></div></div>
    <div class="panel"><h2>سفارش‌ها</h2><div class="table-wrap"><table>
    <tr><th>شماره</th><th>مشتری</th><th>تلفن</th><th>محصولات</th><th>مبلغ</th><th>تاریخ</th><th>وضعیت</th></tr>
    {orows or '<tr><td colspan="7">سفارشی ثبت نشده.</td></tr>'}</table></div></div>"""
    return page("مدیریت", body)

@app.post("/new")
@admin_required
def new_product():
    name = request.form.get("name", "").strip()
    price = request.form.get("price", "")
    category = request.form.get("category", "")
    description = request.form.get("description", "").strip()
    image = request.form.get("image", "").strip()
    try:
        price = int(price)
        if not name or price < 0 or category not in CATEGORIES:
            raise ValueError
    except ValueError:
        return page("خطا", '<div class="panel">اطلاعات محصول معتبر نیست. <a href="/admin">بازگشت</a></div>')
    with connect() as con:
        con.execute("INSERT INTO products(name,price,category,description,image) VALUES(?,?,?,?,?)",
                    (name, price, category, description, image))
    return redirect(url_for("admin"))

@app.route("/edit/<int:pid>", methods=["GET", "POST"])
@admin_required
def edit(pid):
    with connect() as con:
        p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "")
        description = request.form.get("description", "").strip()
        image = request.form.get("image", "").strip()
        try:
            price = int(request.form.get("price", ""))
            if not name or price < 0 or category not in CATEGORIES:
                raise ValueError
        except ValueError:
            return page("ویرایش", '<div class="panel">اطلاعات معتبر نیست.</div>')
        with connect() as con:
            con.execute("""UPDATE products SET name=?,price=?,category=?,description=?,image=? WHERE id=?""",
                        (name, price, category, description, image, pid))
        return redirect(url_for("admin"))
    options = "".join(f'<option {"selected" if c == p["category"] else ""} value="{escape(c)}">{escape(c)}</option>' for c in CATEGORIES)
    body = f"""<div class="panel"><h2>ویرایش محصول</h2><form method="post" class="form-grid">
    <input name="name" value="{escape(p['name'])}" required>
    <input name="price" type="number" min="0" value="{p['price']}" required>
    <select name="category">{options}</select>
    <textarea name="description">{escape(p['description'])}</textarea>
    <input name="image" type="url" value="{escape(p['image'])}" placeholder="لینک تصویر">
    <button class="yellow">ذخیره تغییرات</button></form><p><a href="/admin">بازگشت</a></p></div>"""
    return page("ویرایش محصول", body)

@app.post("/delete/<int:pid>")
@admin_required
def delete(pid):
    with connect() as con:
        con.execute("DELETE FROM products WHERE id=?", (pid,))
    cart = session.get("cart", {})
    cart.pop(str(pid), None)
    session["cart"] = cart
    return redirect(url_for("admin"))

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
