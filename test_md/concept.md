---
deck: test
model: Basic
tags: [congruence, modular_arithmetic, definition]
cards:
  - id: def-congruence-mod-n
    model: Basic
    Front: |
      **Definition:** Congruence Modulo \(\!n\!\)

      Let \(\!n \in \mathbb{N}\!\) be a fixed positive integer (the **modulus**).

      For any two integers \(\!a, b \in \mathbb{Z}\!\), we say that
      **\(\!a\!\) is congruent to \(\!b\!\) modulo \(\!n\!\)** if their difference \(\!(a-b)\!\) is a multiple of \(\!n\!\).
    Back: |
      \[
        a \equiv b \pmod{n}
      \]

      In shorthand, this means that \(\!n \mid (a-b)\!\).

  - id: cloze-congruence
    model: Cloze
    Text: |
      We say that two integers \(\!a,b \in \mathbb{Z}\!\) are **{{c1::congruent modulo}}**
      **{{c2::\(n\)}}** if **{{c3::their difference \((a-b)\) is a multiple of \(n\)}}**.
    Extra: |
      \[
        a \equiv b \pmod{n}
      \]
      Meaning \(\!n \mid (a-b)\!\).
---

# Definition
> [!definition] Definition: Congruence Modulo \(n\)
> Let \(n \in \mathbb{N}\) be a fixed positive integer, which we call the **modulus**.
>
> For any two integers \(a, b \in \mathbb{Z}\), we say that **\(a\) is congruent to \(b\) modulo \(n\)** if their difference \((a - b)\) is a multiple of \(n\).
>
> We write this relationship using the notation:
> \[
>
