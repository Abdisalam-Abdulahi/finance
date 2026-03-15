import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd


import datetime
now = datetime.datetime.now().replace(microsecond=0)
now = str(now)

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    emepty = db.execute("SELECT * FROM purchase WHERE user_id = ?", session["user_id"])
    remainingCash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    remainingCash = float(remainingCash[0]["cash"])
    if not emepty:
        return render_template("index.html", cash=remainingCash, total=remainingCash)
    else:
        lkup = []
        stocks = db.execute("SELECT symbol, SUM(numberOfShares) FROM records WHERE r_id = ? GROUP BY symbol",
                            session["user_id"])
        for stonk in stocks:
            result = lookup(stonk["symbol"])
            if result is not None:
                lkup.append(result["price"])
        data = zip(stocks, lkup)
        return render_template("index.html", data=data, cash=remainingCash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    
    elif request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        result = lookup(symbol)
        if result is None:
            return apology("Invalid symbol")
        
        if not shares:
            return apology("Missing shares")

        try:
            shares = int(shares)
        except ValueError:
            return apology("Invalid shares")
        
        if shares < 0:
            return apology("shares must be positive integer")
        
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cost = float(result["price"]) * shares
        if cost > cash[0]["cash"]:
            return apology("OOPS! No enough cash")
        
        db.execute("INSERT INTO purchase (user_id, symbol, numberOfShares, pricePerShare, total, time) VALUES(?, ?, ?, ?, ?, ?)", 
                   session["user_id"], symbol, shares, float(result["price"]), cost, now)
        remainingCash = cash[0]["cash"] - cost
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remainingCash, session["user_id"])

        record = db.execute("SELECT * FROM records WHERE r_id = ?", session["user_id"])

        if len(record) == 0 or True not in [symbol in x["symbol"] for x in record]:
            db.execute("INSERT INTO records (r_id, symbol, numberOfShares) VALUES(?, ?, ?)",
                       session["user_id"], symbol, shares)
            return redirect("/")
        elif True in [symbol in x["symbol"] for x in record]:
            db.execute("UPDATE records SET numberOfShares = numberOfShares + ? WHERE symbol = ? AND r_id = ?", 
                       shares, symbol, session["user_id"])
            return redirect("/")
    
    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute("SELECT * FROM purchase where user_id = ?", session["user_id"])
    return render_template("history.html", data=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    
    elif request.method == "POST":
        symbol = request.form.get("symbol")
        result = lookup(symbol)
        if result is None:
            return apology("Symbol does'nt exist")
        return render_template("quoted.html", name=result["name"], symbol=result["symbol"], price=result["price"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("registration.html")
    
    elif request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Missing Name")
        
        if not password:
            return apology("Missing Password")
        
        if not confirmation:
            return apology("NO confirmation")
        
        if password != confirmation:
            return apology("passowrd does'nt match")
        
        hash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)
        except ValueError:
            return apology("username already exists")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")
   # return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    records = db.execute("SELECT * FROM records WHERE r_id = ?", session["user_id"])

    symbol = request.form.get("symbol")
    nshares = request.form.get("shares")
    if nshares is not None:
        nshares = int(nshares)

    if request.method == "GET":
        return render_template("sell.html", records=records)
    elif request.method == "POST":
        rshares = 0
        for record in records:
            if record["symbol"] == symbol:
                rshares = record["numberOfShares"]
        if nshares > rshares:
            return apology("Not enaough shares")
        if not symbol:
            return apology("Not symbol selected")
        if True not in [symbol in x["symbol"] for x in records]:
            return apology("You don't own this stoc")
        if nshares < 1:
            return apology("shares must be positive integer")
        
        result = lookup(symbol)
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        income = float(result["price"]) * nshares
        cash = cash[0]["cash"]
        cash = cash + income

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
        db.execute("UPDATE records SET numberOfShares = ? WHERE r_id = ? and symbol = ?", 
                   (rshares - nshares), session["user_id"], symbol)
        db.execute("DELETE FROM records WHERE numberOfShares = ?", 0)

        db.execute("INSERT INTO purchase (user_id, symbol, numberOfShares, pricePerShare, total, time, type) VALUES(?, ?, ?, ?, ?, ?, ?)", 
                   session["user_id"], symbol, nshares, float(result["price"]), income, now, "-")
        
        return redirect("/")