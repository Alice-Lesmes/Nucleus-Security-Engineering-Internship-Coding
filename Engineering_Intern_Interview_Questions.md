# Engineering Intern Interview Questions

## Introduction

Thank you for your interest in the Nucleus Security Engineering
internship program! This document contains 2 primary interview
challenges for you. The first is a code review question, and the second
is a coding challenge.

For both, we absolutely encourage the use of AI. If you do use AI, we
would like for you to share your prompts and then answer the follow-up
questions about how you thought through your prompts.

We know this time of the year is crazy for college students and that
your time is very valuable. Please try not to spend more than about 1
total hour collectively on this.

------------------------------------------------------------------------

## Contents

-   Introduction
-   Code Review (10 minutes)
    -   Task
    -   PHP
    -   Python
    -   Code comments
    -   Follow-up Questions
-   Coding Challenge (\~50 minutes)
    -   Exercise
    -   Follow-up questions
-   Delivery

------------------------------------------------------------------------

# Code Review (10 minutes)

You are welcome and encouraged to use AI for this section. If you do,
please provide your prompts and answer the questions in the follow-up
section.

## Task

Your colleague or team member was given the following task:

1.  Add a `/webhook` endpoint to receive vendor events about users who
    are vendors.

2.  Input data will look like:

    ``` json
    {"email":"a@b.com","role":"admin","metadata":{"source":"vendor"}}
    ```

3.  Verify signature header `X-Signature`.

4.  Parse JSON and upsert the user data.

5.  Store the raw payload for audit/debug.

They have opened a PR with the code below. Review the code and comment
on any issues you find.

**Note:** Both the PHP and Python do the same thing. You can choose to
review whichever one you want. It is not intended for you to review
both.

------------------------------------------------------------------------

## PHP

``` php
<?php
// webhook.php
require_once "db.php"; // provides $pdo (PDO instance)

// Config (dev defaults)
$WEBHOOK_SECRET = getenv("WEBHOOK_SECRET") ?: "dev-secret";
$DB_AUDIT_ENABLED = getenv("AUDIT_ENABLED") ?: "true";

function verify_signature($sig, $body, $secret) {
    // Vendor docs: SHA256(secret + body)
    $expected = hash("sha256", $secret . $body);
    return $expected == $sig; // simple compare
}

$method = $_SERVER["REQUEST_METHOD"] ?? "GET";
$path = parse_url($_SERVER["REQUEST_URI"], PHP_URL_PATH);

// Basic routing
if ($method !== "POST" || $path !== "/webhook") {
    http_response_code(404);
    echo "not found";
    exit;
}

$raw = file_get_contents("php://input"); // raw body string
$sig = $_SERVER["HTTP_X_SIGNATURE"] ?? "";

if (!verify_signature($sig, $raw, $WEBHOOK_SECRET)) {
    http_response_code(401);
    echo "bad sig";
    exit;
}

// Decode JSON
$payload = json_decode($raw, true);
$email = $payload["email"] ?? "";
$role = $payload["role"] ?? "user";

// Store raw payload for auditing / debugging
if ($DB_AUDIT_ENABLED) {
    $pdo->exec("INSERT INTO webhook_audit(email, raw_json) VALUES ('$email', '$raw')");
}

// Upsert user (simple)
$pdo->exec("INSERT INTO users(email, role) VALUES('$email', '$role')");

echo "ok";
```

------------------------------------------------------------------------

## Python

``` python
# app.py
import os
import json
import sqlite3
import hashlib
from flask import Flask, request

app = Flask(__name__)
DB_PATH = os.getenv("DB_PATH", "/tmp/app.db")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-secret")  # default for dev

def get_db():
    return sqlite3.connect(DB_PATH)

def verify(sig, body: bytes) -> bool:
    # Vendor docs: SHA256(secret + body)
    expected = hashlib.sha256(
        (WEBHOOK_SECRET + body.decode("utf-8")).encode("utf-8")
    ).hexdigest()
    return expected == sig  # simple compare

@app.post("/webhook")
def webhook():
    raw = request.data  # bytes
    sig = request.headers.get("X-Signature", "")

    if not verify(sig, raw):
        return ("bad sig", 401)

    payload = json.loads(raw.decode("utf-8"))

    # Example payload:
    # {"email":"a@b.com","role":"admin","metadata":{"source":"vendor"}}
    email = payload.get("email", "")
    role = payload.get("role", "user")

    db = get_db()
    cur = db.cursor()

    # Store raw payload for auditing / debugging
    cur.execute(
        f"INSERT INTO webhook_audit(email, raw_json) VALUES ('{email}', '{raw.decode('utf-8')}')"
    )

    # Upsert user
    cur.execute(
        f"INSERT INTO users(email, role) VALUES('{email}', '{role}')"
    )

    db.commit()

    return ("ok", 200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

------------------------------------------------------------------------

## Code comments

Put your code comments here. For comments on specific lines, please
include the line number. Feel free to comment on the general task as
well.

160/34 - This allows for any text of any format to be an email or role. Additionally, it also doesn't check to see that the passed in data is a string. Why do we not fail when we detect data that does not meet our expectations? It is best to fail early and alert when it does so, rather than fill up the database with potentially junk data.

151/25 - Again, this should fail instead of passing a default value.

167/41-46 - This is poor SQL query generation. It allows a malicious actor to potentially perform a SQL injection because we are simply pasting in the whatever string we are given. SQL injection in this case would allow the bad actor to do basically anything to this database. This should instead use parameterised queries i.e.
```SQL
cur.execute(
        "INSERT INTO webhook_audit(email, raw_json) VALUES (?, ?)",
        (email, raw.decode('utf-8'))
    )
```

144/18 - This code will fail if decode(utf-8) fails at any point, especially if it raises an exception. An exception might be raised if the data we are provided is not encoded using utf-8.

136/10 - Potentially dangerous to have a default variable at all. If WEBHOOK_SECRET is assigned to this default value, it might be trivial for anyone to have their signatures to be accepted by us.

146/20 - A simple check here is a bit suspicious and could be an attack vector from an attacker's POV, especially if they have low latency and jitter to the server. A simple check like this most likely will be checking left-to-right which could pose a potential attack that allows a person to guess a bunch of times to see which are most likely to be correct by guessing amount of likely hash values. While it is low-priority it is better to check this than not. Use a function like `hmac.compare_digest()` to compare the signatures.

------------------------------------------------------------------------

## Follow-up Questions

1.  Share your prompts and the AI outputs.
2.  For each prompt:
    -   Tell us what you were hoping for the AI to accomplish.
    -   Tell us what it actually did.
    -   Did you have to re-prompt it based on its output?
    -   If you had to change your approach, why?

------------------------------------------------------------------------

1. [The chat with an AI agent, Gemini](https://share.gemini.google/CmpIMYcpAhFI). My prompts were giving small code sections and directly prompting the AI for sections of code that I believe could pose some possible issues. You can also see the prompts file in the Github for the prompts as well if you don't want to click the link.
=== Begin QN 2 ===
Prompt 1:
1. I was hoping to double check my belief of there being a potential SQL injection attack. 
2. It reaffirmed my belief of a potential SQL injection attack. Additionally, it also reminded me of the officially supported way of how to limit the issue of SQL injection by using parameterised queries, as well as providing the code which I modified for the example code in my review.
3. No.
4. I would change my approach to provide the LLM with pseudo code that does not potentially leak non-public facing code to a third-party.
Prompt 2:
1. I was hoping to double check my belief of there being an attack potential in the provided code as well as checking that it properly checks the payload's signature.
2. It reaffirmed my belief of a potential attack. It did alert me of how the attack might occur. It also alerted me of a potential issue when performing a utf-8 decode.
3. Yes, because I was/am not entirely convinced on the output of the LLM that the attack is an actual issue that could be exploited, given the jitter and latency between a request and a response. See prompt 3 for reprompt.
4. I would change my approach to provide the LLM with pseudo code that does not potentially leak non-public facing code to a third-party.
Prompt 3:
1. I was attempting to challenge agent on its belief that it could brute force through the network jitter and latency as well as the fixed length and complete difference of most hashes. When challenged I was attempting to see if it backed down and admitted that its belief of the issue was in fact misplaced.
2. It doubled down on its belief of the potential attack. It gave a reason of "even if it isn't an attack vulnerability, mitigating the issue is better than leaving it alone", a reasonable suggestion, so I agreed.
3. No.
4. I would change my approach to provide the LLM with pseudo code that does not potentially leak non-public facing code to a third-party.

# Coding Challenge (\~50 minutes)

For the below coding exercise, there is no expectation that you will
have a fully working solution. For anything you feel you didn't
accomplish, please let us know in the follow-up section after the
exercise.

## Exercise

Build a calculator web application. It should include a frontend piece
and any backend logic needed to perform the calculations.

You can use any language of your choosing for both the frontend and
backend code.

------------------------------------------------------------------------

## Follow-up questions

1.  How far were you able to get with the exercise?
  I completed the exercise to a reasonable degree, despite taking a little longer than I'd initially like logic checking my original solution before asking AI to do some last minute logic checks itself. There is a self-hostable calculator web-app that takes in user input and returns a reasonable result.
2.  What challenges did you encounter in the process?
  Some initial challenges was that I was initially getting my logic incorrect for how to evaluate the precedence/order of operations when thinking about the back-end. I didn't quite take into account how I could not go simply left-to-right in all cases and forgot to take that into account in my initial approach. In my second approach I was slightly better, in constructing a mostly logically sound approach, just failing in some oversights regarding which direction to scan the operation string given.
3.  If you were given unlimited time, what additional functionality
    would you include?
    I would have preferably added more calculator functions past the simple operations expected of a calculator. For example, I would have liked to have allowed for 'variable' functionality. How the calculator works now it wouldn't be trivial to add variables, as that requires storing memory through multiple iterations. Although this could be done using some sort of find and replace when taking in new operations. Additionally, there are a lot of missing calculator functions that allow for nicer use, some missing functionality is: modulo, trig functions, bit-shifting (and other programmer calculator options), ability to display in different bases, log, GCD, LCM, etc.
4.  If you used AI, please include all of your prompts and answer the
    following questions:
    -   What did the AI do well?
    -   What did the AI do poorly?
    -   For the places it did poorly, how did you change your approach
        to your prompts to improve its output?
If you just want the answers to the questions, click [here](#Calc-Answered-Questions), else look at prompts in the Github repo for the.. prompts.
### Calc Answered Questions
1. The AIs were quite good on catching me on potential incorrect assumptions in my pseudo logic I provided them, but they understood quite well that I was asking them to create a language that would evaluate the result of some operations. Additionally, Claude was obviously quite good at actually coding the web app application, all facets of it, both back-end as well as the front-end. Both LLM products did provide potential test case outputs, which was quite nice for testing their outputs.
2. The ChatGPT response was unnecessarily verbose and often keeps listing numbered list options for some reason, which is really annoying, it also found issues with my provided pseudo code that I did not care to properly fix and were quite small changes but it exacerbated these issues more than needed. Additionally, there is a minor issue with Claude's `calculator.py` / `./backend.py` file when running it myself, it prints the tree of operations and numbers quite strangely and is not very human readable and intuitive, but other than that it was alright.
3. For ChatGPT I mostly ignored some of its suggestions, like with parentheses since I disagreed there, but I did make mild alterations to change NumberNode to just Node, since it was technically correct there. For Claude I mostly just ignored the way it creates the tree and pressed on, since it is not necessary to completing the product and is just for debugging, and looked mostly correct despite how strange it looked. No real changes to prompts were made.

# Delivery

Please reply to the email you received with:

1.  Answers to any follow-up above.
2.  Any questions or thoughts you had on the exercise.
3.  A link to a public GitHub repository including your answer to the
    coding challenge.
    -   If we can't get to the repository, we won't be able to consider
        your answer to the coding challenge.
