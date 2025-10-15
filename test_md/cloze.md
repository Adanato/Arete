model: Cloze
deck: test
tags: [cloze, mathjax, test]
markdown: true

# Note

## Text
**Inline math with $...$**:  
We say that two integers $a,b \in \mathbb{Z}$ are **{{c1::congruent modulo}}** **{{c2::$n$}} if **{{c3::their difference $(a-b)$ is a multiple of $n$}}**.

**Inline math with \(...\)** (same idea):  
Here \(a \equiv b \pmod{n}\) means **{{c4::\(n \mid (a-b)\)}}**.

**Display math with $$...$$**:  
$$
a \equiv b \pmod{n}
$$

**Display math with \[...\]**:  
\[
  a \equiv b \pmod{n}
\]

## Back Extra
- c1: “congruent modulo”
- c2: the modulus \(n\)
- c3: definition condition \(n \mid (a-b)\)
- c4: same condition using \(\cdot\) divisibility notation

