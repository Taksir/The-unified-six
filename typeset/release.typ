// The Unified Six — v1.0 editions. Data: typeset/build/<name>.json (from `python -m u6 m5 pdf`).
// Inputs: data (path), edition (A|B), lang (en|enar), part (hadith|appendix).
#let data = json(sys.inputs.at("data"))
#let edition = sys.inputs.at("edition", default: "A")
#let lang = sys.inputs.at("lang", default: "enar")
#let part = sys.inputs.at("part", default: "hadith")
#let ar = lang == "enar"
#let ed-name = if edition == "A" [by attestation] else [by topic]
#let vol-label = [Volume #data.vol of #data.nvols]

#set document(title: "The Unified Six — Edition " + edition + " (" + (if ar { "English + Arabic" } else { "English" }) + ") — " + (if part == "hadith" { "Hadith" } else { "Appendix" }) + " — vol. " + str(data.vol))
#set page(paper: "a5", margin: (x: 1.5cm, top: 1.7cm, bottom: 1.7cm),
  numbering: "1",
  header: context { if counter(page).get().first() > 1 [
    #set text(7.5pt, fill: luma(110))
    The Unified Six · Edition #edition (#ed-name) · #if part == "hadith" [Hadith] else [Appendix] · #vol-label
    #h(1fr) #data.range
  ]})
#set text(font: ("Libertinus Serif", "Amiri", "Noto Sans Symbols 2"), size: 9.5pt, lang: "en")
#set par(justify: true, leading: 0.55em)
#show heading.where(level: 1): it => { pagebreak(weak: true); set text(14pt); block(below: 1em, it.body) }
#show heading.where(level: 2): it => block(above: 1.1em, below: 0.6em, sticky: true, text(11pt, weight: "bold", it.body))
#show link: set text(fill: rgb("#1f5fa8"))

#let badge(b) = if b == "muttafaq" {
  box(baseline: 0.12em, circle(radius: 0.3em, fill: rgb("#2e8540")))
} else if b == "sahih_one" {
  box(baseline: 0.12em, circle(radius: 0.3em, fill: rgb("#1f5fa8")))
}
#let issue(uid) = link("https://github.com/Taksir/The-unified-six/issues/new?title=" + uid + "%3A%20&body=Edition%20" + edition + "%2C%20" + uid)[report]

#let english(e) = for s in e.s {
  if s.at(2) [#s.at(1) ] else [#emph(s.at(1)) ]
}
#let arabic(e) = {
  set text(font: "Amiri", lang: "ar", dir: rtl, size: 12pt)
  set par(justify: true, leading: 0.7em)
  for s in e.s {
    if s.at(2) [#s.at(0) ] else [#text(fill: luma(85), s.at(0)) ]
  }
}

#let entry(e) = block(breakable: true, below: 1em)[
  #text(weight: "bold")[#e.n.] #english(e)
  #if ar [#v(0.2em) #arabic(e)]
  #v(0.1em)
  #set text(8pt)
  [#e.st #badge(e.bd) · #e.lt#if e.tg != "" [ · T: #e.tg]#if e.un [ · ≈] · →A#e.n · #issue(e.uid)]
]

#let mem(m) = [
  #m.at(0) #m.at(1)
  #if m.at(2) == "partial" [⯪ fragment] else [★ full]#if m.at(3) == "ref" [ (chain only)]#if m.at(3) == "ref_variant" [ (variant chain)]#if m.at(6) [ — *text shown*]
  #if ar and m.at(4) != "" [ · #text(font: "Amiri", lang: "ar", dir: rtl, m.at(4))]
  #if m.at(7) != "" [ · T: #m.at(7)]
  #if m.at(5) != "" [ · #link(m.at(5))[sunnah.com]] \
]

#let app(e) = block(breakable: true, below: 0.8em)[
  *A#e.n* · #e.uid · #e.st #badge(e.bd) · #e.topic#if e.sec.len() > 0 [ (also: #e.sec.join(", "))] \
  #for m in e.mem { mem(m) }
  #if e.var > 0 [Versions compared for the italics: #(e.var + 1). ]#if e.idrop [Italics not shown: the translation could not be aligned clause by clause. ]#if e.ext [Text repaired: the source split cut it short; shown in full after the first chain. ]#if e.un [*≈ Grouping uncertain:* at least one narration joined this entry on a low-confidence machine judgement. ]
  #if e.see.len() > 0 [See also (possible duplicates, unconfirmed): #e.see.map(x => "A" + str(x)).join(", ").]
]

// ---------------------------------------------------------------- title and front matter
#align(center)[
  #v(2cm)
  #text(22pt)[The Unified Six]
  #v(0.2em)
  #text(10pt)[al-Kutub al-Sitta in one compilation: each distinct hadith once]
  #v(0.6em)
  #text(11pt)[Edition #edition — #ed-name · #if ar [English and Arabic] else [English]]
  #v(0.3em)
  #text(11pt)[#if part == "hadith" [Hadith] else [Appendix: sources and variants] · #vol-label]
  #v(0.3em)
  #text(9pt, fill: luma(90))[#data.range · version #data.version]
]
#v(1cm)
#if data.vol == 1 {
  set text(8.5pt)
  [
  *What this is.* The six canonical books — Ṣaḥīḥ al-Bukhārī (*B*), Ṣaḥīḥ Muslim (*M*), Sunan Abī Dāwūd (*D*),
  Jāmiʿ al-Tirmidhī (*T*), Sunan al-Nasāʾī (*N*) and Sunan Ibn Mājah (*J*) — hold #data.narrations narrations.
  Repetitions within and across the books are merged here into #data.total entries, so each distinct hadith
  is printed once, with a pointer to every book that carries it. Chains of narrators are in the source books;
  the appendix lists every original narration with its number and a link.

  *How to read an entry.* The main text is the fullest version. Upright text appears in every full version;
  _italic_ text only in some (the appendix says which books). Under each hadith:
  - *★* one star per book with the full hadith, *⯪* per book with only a fragment;
  - #badge("muttafaq") *muttafaq ʿalayh* (in both al-Bukhārī and Muslim); #badge("sahih_one") in one of the two;
  - book letters; *T:* al-Tirmidhī's own grading where he gives one; *≈* the grouping rests on an uncertain
    machine judgement; *→A12* the appendix entry; *report* opens a correction form on GitHub.

  Stars count books. They say nothing about authenticity; no modern grader is used.

  *Machine-assisted compilation and machine translation.* The grouping was made by software and language models,
  checked on samples (about 96–100 % of merges correct). The English is a machine translation (Claude Sonnet)
  and has not been reviewed by a scholar. A sample check of v1.0 found an error affecting meaning in about 6 % of
  hadith; for v1.1 a second machine pass re-read every translation against the Arabic and corrected #data.fixed of them.
  Some errors remain.
  Rely on the Arabic and on the source books, and please report mistakes.

  *Numbering.* B: Fuʾād ʿAbd al-Bāqī (= Fatḥ al-Bārī); M: Fuʾād ʿAbd al-Bāqī with letter suffixes for
  supporting chains; D: Muḥyī al-Dīn ʿAbd al-Ḥamīd; T: Aḥmad Shākir; N: ʿAbd al-Fattāḥ Abū Ghudda;
  J: Fuʾād ʿAbd al-Bāqī. Arabic text from the editions published on sunnah.com.

  *License.* Text and data: CC BY 4.0. Code: MIT. github.com/Taksir/The-unified-six
  ]
}

// ---------------------------------------------------------------- body
#set text(9.5pt)
#if part == "hadith" {
  for g in data.groups [
    = #g.title
    #if g.note != "" [#text(9pt, fill: luma(90), g.note) #v(0.4em)]
    #for e in g.entries { entry(e) }
  ]
} else {
  set text(8pt)
  for g in data.groups [
    = #g.title
    #for e in g.entries { app(e) }
  ]
}
