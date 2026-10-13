// The Unified Six — M1 format sample. Data: typeset/build/sample-data.json (from `python -m u6 m1 sample`).
#let data = json("build/sample-data.json")
#let edition = sys.inputs.at("edition", default: "A")

#set document(title: "The Unified Six — format sample, Edition " + edition)
#set page(paper: "a5", margin: (x: 1.6cm, top: 1.7cm, bottom: 1.8cm),
  numbering: "1",
  header: context { if counter(page).get().first() > 1 [
    #set text(8pt, fill: luma(110))
    The Unified Six · Edition #edition (#if edition == "A" [by attestation] else [by topic]) · format sample
    #h(1fr) Bukhārī + Muslim only
  ]})
#set text(font: ("Libertinus Serif", "Amiri", "Noto Sans Symbols 2"), size: 10pt, lang: "en")
#set par(justify: true, leading: 0.55em)
#show heading.where(level: 1): it => { pagebreak(weak: true); set text(15pt); block(below: 1em, it.body) }
#show heading.where(level: 2): it => block(above: 1.2em, below: 0.7em, text(11.5pt, weight: "bold", it.body))

#let star-order = ("★★", "★⯪", "⯪⯪", "★", "⯪")
#let topic-index(t) = data.topics.position(x => x == t)
#let entries = if edition == "A" {
  data.entries.sorted(key: e => (star-order.position(s => s == e.stars), topic-index(e.topic)))
} else {
  data.entries.sorted(key: e => (topic-index(e.topic), star-order.position(s => s == e.stars)))
}
#let num = (:)
#for (i, e) in entries.enumerate() { num.insert(e.uid, i + 1) }

#let badge(b) = if b == "muttafaq" {
  box(baseline: 0.12em, circle(radius: 0.32em, fill: rgb("#2e8540")))
} else if b == "sahih_one" {
  box(baseline: 0.12em, circle(radius: 0.32em, fill: rgb("#1f5fa8")))
}

#let english(e) = for s in e.segments {
  if s.core [#s.en ] else [#emph(s.en) ]
}
#let arabic(e) = {
  set text(font: "Amiri", lang: "ar", dir: rtl, size: 12.5pt)
  set par(justify: true, leading: 0.75em)
  for s in e.segments {
    if s.core [#s.ar ] else [#text(font: "Amiri", style: "italic", fill: luma(70), s.ar) ]
  }
}

#let entry(e) = block(breakable: true, below: 1.1em)[
  #text(weight: "bold")[#num.at(e.uid).] #english(e)
  #v(0.25em)
  #arabic(e)
  #v(0.15em)
  #set text(8.5pt)
  [#e.stars #badge(e.badge) · #e.letters.join(" ")#if e.uncertain [ · ≈] · →A#num.at(e.uid)]
]

// ---------------------------------------------------------------- front matter
#align(center)[
  #v(2.5cm)
  #text(22pt)[The Unified Six]
  #v(0.3em)
  #text(11pt)[#if edition == "A" [Edition A — by attestation] else [Edition B — by topic]]
  #v(0.3em)
  #text(9pt, fill: luma(90))[Format sample · Ṣaḥīḥ al-Bukhārī and Ṣaḥīḥ Muslim only · #entries.len() hadith]
]
#v(1.2cm)
#set text(9pt)
*How to read an entry.* Each hadith appears once. The main text is the fullest version found.
Upright text appears in every full version; _italic_ text appears only in some versions (the appendix
says which). The bracket below each hadith gives:

- *★* one star per book that carries the full hadith, *⯪* per book that carries only a fragment of it;
- #badge("muttafaq") *Muttafaq ʿalayh* — in both al-Bukhārī and Muslim; #badge("sahih_one") in one of the two;
- the book letters (*B* al-Bukhārī, *M* Muslim) and the appendix entry (→A12);
- *≈* the grouping of these narrations rests on an uncertain machine judgement; a researcher should check it.

Stars count how many books carry a hadith. They say nothing about its authenticity.

*This is a draft.* The English is a machine translation made for this sample and has not been
reviewed. Topics come from a provisional list. Numbering: al-Bukhārī by Fuʾād ʿAbd al-Bāqī
(= Fatḥ al-Bārī); Muslim by Fuʾād ʿAbd al-Bāqī with letter suffixes for supporting chains.
#set text(10pt)

// ---------------------------------------------------------------- body
#if edition == "A" {
  for s in star-order {
    let group = entries.filter(e => e.stars == s)
    if group.len() > 0 [
      = #s #h(0.4em) #text(10pt, fill: luma(90))[#if s.contains("★★") [in both books, in full] else if s == "★⯪" [full in one book, fragment in the other] else if s == "⯪⯪" [fragments in both books] else if s == "★" [in one book] else [fragment in one book]]
      #for e in group { entry(e) }
    ]
  }
} else {
  for t in data.topics {
    let group = entries.filter(e => e.topic == t)
    if group.len() > 0 [
      == #t
      #for e in group { entry(e) }
    ]
  }
}

// ---------------------------------------------------------------- appendix
= Appendix: sources and variants
#set text(8.5pt)
#for e in entries [
  #block(breakable: false, below: 0.9em)[
    *A#num.at(e.uid)* · #e.uid · #e.stars #badge(e.badge) · #e.topic \
    #for m in e.members [
      #m.letter #m.number
      #if m.role == "partial" [⯪ fragment] else [★ full]#if m.kind == "ref" [ (chain only: “with this isnād, likewise”)]#if m.kind == "ref_variant" [ (variant chain)]#if m.is_rep [ — *text shown*]
      #if m.narrator != "" [ · #text(font: "Amiri", lang: "ar", dir: rtl, m.narrator)]
      #if m.url != "" [ · #link(m.url)[sunnah.com]] \
    ]
    #if e.variants > 0 [Versions compared for the italics: #(e.variants + 1). ]#if e.uncertain [*≈ Grouping uncertain:* at least one narration joined this entry on a low-confidence judgement. ]
    #if e.see_also.len() > 0 [See also (possible duplicates, unconfirmed): #e.see_also.join(", ").]
  ]
]
