# Prompts Task 1 - Code Review
**Prompt 1:**
Is there an SQL injection possibility in this code:
```python
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
```
**AI OUTPUT**
**Yes, absolutely.** This code is highly vulnerable to **SQL Injection**.

### Why it is vulnerable

The code uses Python **f-strings** (`f"..."`) to construct SQL queries by directly embedding variables (`email`, `role`, and `raw`) into the query string.

Because SQL treats string literals and code commands using the same syntax, an attacker can supply malicious input containing single quotes (`'`) and SQL syntax. This allows them to break out of the intended string value, terminate the statement, and execute arbitrary SQL commands (such as dropping tables, reading sensitive data, or executing administrative commands).

---

### The Vulnerable Code Areas

1. **Audit Logging Query:**
```python
cur.execute(
    f"INSERT INTO webhook_audit(email, raw_json) VALUES ('{email}', '{raw.decode('utf-8')}')"
)

```


If an attacker provides an email like `admin@example.com', 'malicious_payload'); DROP TABLE users; --`, the database will execute the injected commands.
2. **User Upsert Query:**
```python
cur.execute(
    f"INSERT INTO users(email, role) VALUES('{email}', '{role}')"
)

```


Both `email` and `role` are directly interpolated from the payload without any sanitization or parameterization.

---

### How to Fix It (Parameterized Queries)

To fix SQL injection, you must **never** use string formatting or concatenation to build SQL queries. Instead, pass user inputs as separate parameters to the database driver (`cur.execute`), which handles escaping safely.

Here is the secure version:

```python
    email = payload.get("email", "")
    role = payload.get("role", "user")

    db = get_db()
    cur = db.cursor()

    # Store raw payload safely using parameterized queries
    # Note: Use '%s' instead of '?' if you are using PostgreSQL or MySQL with psycopg2/mysqlclient
    cur.execute(
        "INSERT INTO webhook_audit(email, raw_json) VALUES (?, ?)",
        (email, raw.decode('utf-8'))
    )

    # Upsert user securely
    cur.execute(
        "INSERT INTO users(email, role) VALUES(?, ?)",
        (email, role)
    )
    
    db.commit()

```

**Prompt 2:**
Does the below correctly check the hash. Also check the code to see if it could be brute-forced in order to determine the potential webhook secret.
```
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-secret")  # default for devdef get_db():
    return sqlite3.connect(DB_PATH)def verify(sig, body: bytes) -> bool:
    # Vendor docs: SHA256(secret + body)
    expected = hashlib.sha256(
        (WEBHOOK_SECRET + body.decode("utf-8")).encode("utf-8")
    ).hexdigest()
    return expected == sig  # simple compare
```

**AI OUTPUT**
### 1. Does it correctly check the hash?

**Functionally yes, but cryptographically and robustly no.** There are three main issues with how the hash is checked:

* **Timing Attacks (The `==` operator):** Using a standard `==` string comparison short-circuits as soon as it hits the first mismatched character. An attacker can measure tiny differences in response time to guess the signature character-by-character. You should use constant-time comparison like `hmac.compare_digest()`.
* **Potential Encoding Crashes:** Doing `body.decode("utf-8")` will throw a `UnicodeDecodeError` and crash your webhook handler if the vendor sends a body containing binary data or non-UTF-8 characters. It is much safer to work entirely in bytes (`bytes`).
* **Code Typo/Syntax Bug:** Notice that on the first line, `... # default for devdef get_db():` is missing a newline between the comment and `def get_db()`, which will cause a SyntaxError when Python loads the module.

---

### 2. Can it be brute-forced to determine the webhook secret?

**Yes, for two major reasons:**

#### A. The Dangerous Default Fallback (`"dev-secret"`)

The line `WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-secret")` provides a hardcoded default fallback.

* If this code is deployed to production and someone forgets to set the `WEBHOOK_SECRET` environment variable, **anyone on the internet can instantly forge valid signatures** using the publicly known default `"dev-secret"`. No brute-forcing is even required—they already know it.

#### B. Offline Brute-Forcing of Weak Secrets

If a weak or short secret is used (e.g., a simple password, a default string, or a short alphanumeric code), an attacker who intercepts a single valid webhook payload (`body`) and its corresponding signature (`sig`) can easily brute-force the secret **offline**.

* Because the algorithm is simply `SHA256(secret + body)` and SHA-256 is a very fast hashing algorithm, an attacker's computer can test millions of candidate secrets per second by prepending them to the known body and seeing which one produces the matching `sig`.

---

### The Secure Implementation

Here is how you should rewrite the `verify` function to prevent timing attacks, handle binary bodies safely, and fail securely if the secret isn't configured:

```python
import os
import hashlib
import hmac

# Fail-safe: Do not provide a weak default secret in production
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET environment variable is not set!")

def verify(sig: str, body: bytes) -> bool:
    # Vendor docs: SHA256(secret + body)
    # Keep everything as bytes to avoid Unicode decode errors
    secret_bytes = WEBHOOK_SECRET.encode("utf-8")
    
    expected_digest = hashlib.sha256(secret_bytes + body).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_digest, sig)

```
**Prompt 3:**
Ok but wouldn't the data from this be practically useless since we're comparing the sha data which is fixed-length against something else and also factoring in network data?
**AI OUTPUT**
You have hit on a very astute and valid point regarding **network jitter and latency**, but there is a nuance to how string comparisons and timing vulnerabilities work.

Your skepticism is well-founded, but the vulnerability is still real for a few specific reasons:

### 1. How `==` Works with Strings (Early Exit)

Even though a SHA-256 hex digest is a fixed length (64 characters), standard string comparison (`==`) in Python (and many other languages) evaluates strings **character by character from left to right**, stopping (short-circuiting) the exact moment it finds a mismatch.

* If the first character of the attacker's guess is wrong, the comparison aborts immediately.
* If the first character is correct, it checks the second character, taking a tiny fraction of a nanosecond longer.

This means the execution time of the comparison *does* mathematically correlate with how many characters matched from the beginning of the string.

### 2. The Real Hurdle: Network Jitter

You are entirely correct that **network latency and jitter over the public internet** introduce a massive amount of "noise." A variation of a few milliseconds in network transit can easily mask a difference of a few nanoseconds in server processing time.

Because of this, a simple remote timing attack over the internet is notoriously difficult to pull off against a standard web server. However, it is not impossible:

* **Statistical Analysis:** Attackers can send millions of requests and use statistical techniques (like t-tests or averaging) to filter out network noise and isolate the server-side processing time.
* **Local/Cloud Infrastructure:** If the attacker is operating within the same cloud provider network (e.g., sharing a data center or a physical host with your service), network jitter drops to near-zero, making timing attacks much more viable.

### Why Fix It Anyway?

While network noise makes remote timing attacks harder, security best practices dictate using constant-time functions like `hmac.compare_digest()` for two reasons:

1. **Defense in Depth:** Security layers should not rely on network instability to protect them.
2. **Standard Compliance:** It eliminates an entire class of side-channel vulnerabilities entirely, ensuring that code remains secure even if deployment architectures change (e.g., moving to a low-latency internal microservice mesh where timing differences are easily measured).

# Prompts Task 2 - Calculator App
### Prompts
[Claude link](https://claude.ai/share/0db99a09-1705-47d8-9c49-693bdb0ebd75) for every prompt and response
#### Prompt 1 - ChatGPT
##### Prompt
Alert me to any logical issues to my pseudo code implementation of a calculator, do not attempt to actually code the python code yourself.

PSEUDO CODE:

1. Have an initial pass to determine if the given phrase is within the syntax/language we are defining (nodes) and then log everything as a node. Yes, this is similar to parsing in compilers.
    a. A node is of types:
        - (Could have these separate, but we might just call this a 'number' node as well.)
            - int
            - float/double (anything with decimal)
        - ~~variable (consisting of singular letter)~~ <== This is unecessary and will only be done later if i have time
        - Operation with the subtypes:
            - Brackets (parentheses)
            - Exponents (represented using `^`)
            - Multiplication (Represented using `*`)
            - Division (repr using `/`)
            - Addition (repr using `+`)
            - Subtraction (repr using `-`)
            - Negative (repr using `-` as well) (This is theoretical, do not actually use this, refer to below as to why)

2. Then we will check the cases that will be mathematically sound. Check specifically at least these cases:
    - All parentheses have matching beginning and end parentheses there should be an equal amount of `(`'s as `)`'s, as well as a `)` must be preceded by at least one `(` and doing so matches the expression into the parentheses operation node.
    - Parentheses must have some operation contained inside them that is not just parentheses. Do not allow for parentheses all the way down, but do allow for: ((1+2)+3) as well as ((1+2)).
    - All operations (excluding parentheses, and negative) must have a number node on either side of the operation.
    - Check for division by 0, in which case we will alert with either 'undefined' or 'div by 0' on the screen in the front-end (just raise exception most likely)
    - If a subtraction symbol `-` has no symbol to the left of it we can assume it's a 'negative' symbol and replace it with a 'subtraction' node of '0-NUMBER' surrounded in a 'parentheses' node, to maintain proper order.
    - Yes I am aware of exponents actually having right precedence so we must take this into account. VERY IMPORTANT.
3. To determine the order of operation we will assign each operation a precedence score based on the operation following BIMDAS/PEMDAS, as in parentheses are precedence 0, exponents are 1, div/mul is equally 2, add/sub is equally 3.
    1. To begin with initialise an empty tree. We will start with the left-most value and assign the operation node as the root node with the left number being forced to be just a number, otherwise it is NOT the left-most operation obviously.
    2. Once we have a tree that looks like '1 + (some operations)' we can then go to the next left-most operation doing the same thing, and we keep doing this down and down, until we have a tree that looks like below.
    == EXAMPLE: ==
    ```
    Equation: 1 + 2 - 3 * (6 / 2)

        +
    1       -
        2       *
            3       ()
                    / (div)
                6       2
    ```

    == END EXAMPLE ==
    3. Now that we have this tree we can actually perform the operations recursively, i.e. some code that looks like below
    ```
    def eval_op(Operation, lvalue, rvalue) -> numberNode:
        match (operation):
            case 'additionNode':
                return lvalue + eval_op(rvalue.operation, rvalue.lVal, rvalue.rVal)
            # ...
            default:
                raise error
    ```
    Note this is just pseudo code and can def be improved by just passing in the nodes directly.
4. Return the eval_op(rootNode.operation, rootNode.lVal, rootNode.rVal)
##### Response
[ChatGPT link to response](https://chatgpt.com/s/t_6af92838c23481918fa5c6457918e837) - used for logic checking my pseudo logic to be provided to Claude
#### Prompt 2 - Claude
##### Prompt
I have some pseudo logic for you to actually implement, do it in python. here is the pseudo logic. This is for a calculator app

PSEUDO CODE:

1. Have an initial pass to determine if the given phrase is within the syntax/language we are defining (nodes) and then log everything as a node. Yes, this is similar to parsing in compilers.
    a. A node is of types:
        - (Could have these separate, but we might just call this a 'number' node as well.)
            - int
            - float/double (anything with decimal)
        - ~~variable (consisting of singular letter)~~ <== This is unnecessary and will only be done later if i have time
        - Operation with the subtypes:
            - Brackets (parentheses)
            - Exponents (represented using `^`)
            - Multiplication (Represented using `*`)
            - Division (repr using `/`)
            - Addition (repr using `+`)
            - Subtraction (repr using `-`)
            - Negative (repr using `-` as well) (This is theoretical, do not actually use this, refer to below as to why)

2. Then we will check the cases that will be mathematically sound. Check specifically at least these cases:
    - All parentheses have matching beginning and end parentheses there should be an equal amount of `(`'s as `)`'s, as well as a `)` must be preceded by at least one `(` and doing so matches the expression into the parentheses operation node.
    - Parentheses must have some operation contained inside them that is not just parentheses. Do not allow for parentheses all the way down, but do allow for: ((1+2)+3) as well as ((1+2)).
    - All operations (excluding parentheses, and negative) must have some other node on either side.
    - If a subtraction symbol `-` has no symbol to the left of it we can assume it's a 'negative' symbol and replace it with a 'subtraction' node of '0-NODE' surrounded in a 'parentheses' node, to maintain proper order.
    - Yes I am aware of exponents actually having right precedence so we must take this into account. VERY IMPORTANT.
3. To determine the order of operation we will assign each operation a precedence score based on the operation following BIMDAS/PEMDAS, as in parentheses are precedence 0, exponents are 1, div/mul is equally 2, add/sub is equally 3.
    1. To begin with we search the operations and we catalogue their positions in the given formula as well as their precedence. We search for the operations with the least precedence (highest number) and then by the ones the furthest to the left. We select this node as the root node (the operation).
    2. We now have two sections a left and right section, do this recursively for each section (left and right) and make sure we sort by precedence and order.
    3. This should now have a tree that looks somewhat like below
    == EXAMPLE: ==
    ```
    Equation: 1 - 2 - (3 * 3) + 2
        -
    1       -
        2       +
            ()      2
            *
        3       3

    ```
    == END EXAMPLE ==
    4. Now that we have this tree we can actually perform the operations recursively, i.e. some code that looks like below
    ```
    def eval_node(Operation, lvalue, rvalue) -> numberNode:
        match (operation): (Also remember to check for div by 0)
            case 'additionNode':
                return lvalue + eval_op(rvalue.operation, rvalue.lVal, rvalue.rVal)
            # ..
            case 'numberNode':
                return node.val
            # ...
            default:
                raise error
    ```
    Note this is just pseudo code and can def be improved by just passing in the nodes directly.
4. Return the eval_op(rootNode.operation, rootNode.lVal, rootNode.rVal)

##### Response
I've written `calculator.py` following your four steps, and its built-in tests pass. Run `python calculator.py` for a REPL (`tree 1+2*3` prints the tree) or `python calculator.py --test` to run the tests.

**One deliberate deviation from your pseudo logic.** Your rule of picking the leftmost lowest-precedence operator as root gives the wrong answer for `+ - * /`. Your example tree, `1 - (2 - ((3*3) + 2))`, evaluates to 10, but `1 - 2 - 9 + 2` is -8. So I pick the rightmost operator for the left-associative ones, which gives `((1 - 2) - (3*3)) + 2`. For `^` I kept your leftmost rule, so `2^3^2 = 512`. The tree printed for your example now has `+` at the root.

How each step maps to the code:
- **Step 1, nodes:** `tokenize` handles ints and floats. Anything outside the language, including letters and `**`, raises an error.
- **Step 2, validation:** `check_parentheses` and `check_adjacency` cover unmatched parentheses, empty `()` (which also rules out `((()))`), operators missing an operand, and touching values like `2 3`. `((1+2)+3)` and `((1+2))` are allowed.
- **Negatives:** `rewrite_negatives` turns a `-` with nothing to its left into `(0 - X)`, so `2 * -3` and `2^-1` work.
- **Steps 3 and 4:** `build_tree` and `eval_node` build and evaluate the tree. Division by zero raises an error, as does `0^-1`. Exact integer divisions stay ints, so `10/5` gives `2`.

Two behaviours to be aware of:
- Following your negative rule literally, `-2^2` becomes `(0-2)^2 = 4`, not the conventional -4. If you want the conventional result, tell me and I'll make the negative apply after exponents.
- Implicit multiplication like `2(3)` is rejected rather than guessed at.

**See `./backend.py` for the claude Calculator.py file excluding the top docstring, that's mine.**
#### Prompt 3 - Claude
##### Prompt
Ok good, now create a very simple front-end calculator front-end that sends the result to this backend file (which should be your calculator.py). Preferably I'd like it to be written in svelte with quite simple graphics reminiscent of an actual calculator.
##### Response
I've built the Svelte calculator front-end and a small Python server so it can send expressions to `calculator.py`. I tested the server with curl, but I couldn't install or run the Svelte side here, so `App.svelte` is untested.

The curl checks covered your example (`-8`), `2^3^2` (`512`), `0.1+0.2` (`0.3`) and division by zero (returns an error message).

To run it, put the files together in one folder (they're in `calculator-app`), then:

1. In one terminal, run `python server.py`. It uses only the standard library and listens on port 8000.
2. In another, run `npm install` and then `npm run dev`, and open the URL Vite prints (usually http://localhost:5173).

**What you get**
- **Look:** a dark calculator body with a green LCD-style screen, chunky keys that press down when clicked, red function keys, amber operators and a green `=` key.
- **Keys:** digits, `.`, `( )`, `^`, `+ − × ÷`, `C` and backspace.
- **Keyboard:** digits and operators work, Enter or `=` evaluates, Backspace deletes and Esc clears.
- **Flow:** pressing `=` posts `{"expression": "..."}` to `/api/calculate`, and the answer or error message shows on the screen. After a result, an operator key continues from it and any other key starts fresh.
- **Float noise:** the server tidies results like `0.30000000000000004` into `0.3`, and sends them as strings so big integers don't lose precision in JavaScript.

`calculator.py` is unchanged; `server.py` just imports `calculate` and `CalcError` from it. It is written for Svelte 5 (the `$state` syntax), which `package.json` pins.

**See ./claudeWeb/ for all the claude files it generated**

#### Prompt 4 - Claude
##### Prompt
Ok explain to me which files are supposed to be in the 'src' folder
##### Response
Only two files belong in `src`: `App.svelte` and `main.js`.

- **`App.svelte`** is the calculator itself: the button layout, the screen, the styling, and the code that sends the expression to the backend.
- **`main.js`** is the entry point. It's a few lines that mount `App` into the page.

The rest go in the project root, next to the `src` folder, not inside it:

```
calculator-app/
├── src/
│   ├── App.svelte
│   └── main.js
├── index.html
├── package.json
├── vite.config.js
├── server.py
├── calculator.py
└── README.md
```

`index.html` loads `/src/main.js`, so if `main.js` isn't in `src`, Vite will report a missing-file error. `server.py` and `calculator.py` need to sit together, because `server.py` does `from calculator import ...`.

After you run `npm install`, a `node_modules` folder will appear in the root. That's expected, and you don't need to touch it.

------------------------------------------------------------------------


