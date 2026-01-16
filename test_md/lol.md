---
model: Basic
deck: test
tags:
- markdown
- list
- mathjax
markdown: true
arete: true
cards:
- Front: |-
    List rendering test (unordered + ordered, nested, inline + block math).

    Unordered list (blank line above on purpose):

    - Inline math works: \(E = mc^2\)
    - Nested with inline math:
      - Pythagorean: \(a^2 + b^2 = c^2\)
      - Block math inside a bullet (indented 4 spaces):

        \[
        \begin{align*}
        (a+b)^2 &= a^2 + 2ab + b^2 \\
        \int_0^1 x^2\,dx &= \frac{1}{3}
        \end{align*}
        \]

    - Back to the outer list after the block.

    Ordered list (blank line above on purpose):

    1. Inline fraction: \(\frac{1}{x} \to 0\) as \(x \to \infty\)
    2. Trig identity: \(\sin^2\theta + \cos^2\theta = 1\)
    3. Matrix inline: \(A^{-1}A = I\)
  Back: |-
    Checks you should see on the card:

    - Bullets and numbers render as proper HTML lists (not just lines with `<br>`).
    - Inline math inside bullets is typeset by MathJax.
    - The aligned block inside a bullet stays **inside** that list item and is centered.

    Ordered list with a block (again, note the 4-space indent and blank lines):

    1. Derivation:

        \[
        \begin{align*}
        F &= ma \\
          &= m\frac{d^2x}{dt^2}
        \end{align*}
        \]

    2. Conclusion: \(F\) depends on \(x(t)\) via its second derivative.

    Tips:
    - Keep a **blank line before each list** (unordered or ordered).
    - Indent block math **4 spaces** when it belongs to a list item.
    - Use spaces (not tabs) in Markdown.
  nid: '1762988620254'
  cid: '1762988620255'
---
