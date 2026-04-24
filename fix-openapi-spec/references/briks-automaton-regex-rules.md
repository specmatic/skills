# BRICS Automaton Regular Expression Rules

This summarizes the regular expression syntax accepted by `dk.brics.automaton.RegExp`.

## Operator Precedence

From highest to lowest precedence:

Escaped characters, literal characters, character classes, groups, strings, named automata, and intervals

Parentheses override precedence.

## Core Syntax

| Syntax | Meaning |
| --- | --- |
| `.` | Any single character |
| `(expr)` | Grouping and precedence override |
| `[chars]` | Character class |
| `[^chars]` | Negated character class |
| `a-b` inside a character class | Character range including both endpoints |
| `expr?` | Zero or one occurrence |
| `expr*` | Zero or more occurrences |
| `expr+` | One or more occurrences |
| `expr{n}` | Exactly `n` occurrences |
| `expr{n,}` | At least `n` occurrences |
| `expr{n,m}` | Between `n` and `m` occurrences, inclusive |
| `expr1|expr2` | Union |

## Character Classes

Character classes are built from individual character expressions and ranges.

Examples:

```text
[abc]
[a-z]
[^0-9]
```

Rules:

- A range includes both endpoints.
- `-` has special meaning inside a character class when used as a range separator.
- Reserved characters must still be escaped inside character classes.

## Reserved Characters and Escaping

Characters used by enabled syntax are reserved. To use a reserved character literally:

- Prefix it with `\`, for example `\+`.
- Or place it inside a quoted string, for example `"a+b"`.

This escaping rule also applies inside character classes.

