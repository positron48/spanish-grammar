# Spanish Grammar from Zero to C1 (RU -> ES)

This file is the source outline for the Spanish grammar course in `courses/spanish-grammar/`.

Keep this file human-readable and automation-friendly:
- section and chapter titles are intentionally ASCII-friendly, so future tools can derive stable `section_id` and `chapter_id` values;
- learner-facing translations can be added later in chapter metadata;
- `05-final.json` is generated and should not be edited by hand.

## Authoring Rules

- Audience: a full beginner in Spanish who knows Russian.
- UI language: Russian. Target language: Spanish.
- Base norm: neutral international Spanish. Mention Spain vs Latin America differences only where they materially affect grammar or usage.
- One chapter = one main grammar decision or one tightly related cluster.
- End most sections with one synthesis chapter (`Build & speak` or `Build & write`).
- Every chapter should call out predictable Russian-speaker mistakes when they matter.
- A0-A1 chapters should include reading aloud, stress, sound-to-spelling, and short sentence decoding.
- Pronunciation chapters are part of the core path, not an optional appendix.

## Chapter Production Contract

For every chapter, the later content-generation workflow should produce:
1. `01-outline.json`
2. `02-theory-blocks/*.json`
3. `03-questions.json`
4. `05-final.json` only via `make final`
5. validation via `make validate-all`

Bundle refresh is done from the monorepo root:
1. `./scripts/generate-grammar-bundle.sh es`

## Suggested Production Batches

1. Batch 1: Sections 0-5 (A0-A1 foundations)
2. Batch 2: Sections 6-10 (A2 tense and modality core)
3. Batch 3: Sections 11-17 (B1 sentence-building and timeline control)
4. Batch 4: Sections 18-21 (B2 subjunctive, reporting, voice)
5. Batch 5: Section 22 (C1 style, discourse, register)

## Course Outline

### Section 0. Orientation: alphabet, sounds, stress, punctuation (A0)

0.1. The Spanish alphabet and letter names
0.2. Vowels, syllables, diphthongs and hiatus
0.3. Stress rules and written accents
0.4. Core pronunciation map: b/v, c/z, g/j, ll/y, enye, h, r/rr
0.5. Intonation and inverted question/exclamation marks
0.6. Build & read: decode words and read mini-sentences aloud

------

### Section 1. First building blocks: nouns, gender, articles, agreement (A0-A1)

1.1. Noun gender: masculine, feminine and useful heuristics
1.2. Singular and plural: -s, -es and common spelling changes
1.3. Definite and indefinite articles: el/la/los/las, un/una/unos/unas
1.4. Adjectives: gender and number agreement
1.5. Demonstratives: este/ese/aquel and esto/eso/aquello
1.6. Numbers 0-100 and basic quantity words
1.7. Build & speak: name and describe objects around you

------

### Section 2. First sentences: ser, pronouns, questions, negation (A1)

2.1. Subject pronouns and null subjects: when to say yo and when not to
2.2. Forms of address: tu, usted, ustedes, vosotros and register
2.3. Ser for identity, origin, profession, material and time
2.4. Statements, yes/no questions and negation with no
2.5. Basic question words: que, quien, cual, donde, como
2.6. Ser + adjectives: personal description and evaluation
2.7. Build & speak: introduce yourself and other people

------

### Section 3. Existence, location and possession: estar, hay, tener (A1)

3.1. Estar for location and temporary states
3.2. Hay for existence and introducing new things
3.3. First ser vs estar contrast
3.4. Tener for possession, age and common bodily-state expressions
3.5. Possessives: mi/tu/su/nuestro and de + noun
3.6. Basic time, date and weather expressions
3.7. Build & speak: describe a room, city or daily schedule

------

### Section 4. Present 1: regular verbs and everyday actions (A1)

4.1. Infinitives and present tense endings: -ar, -er, -ir
4.2. Present statements with regular verbs
4.3. Present questions: where the subject and adverbs go
4.4. Negation: no, nunca, tampoco, ya no
4.5. Frequency expressions: siempre, a menudo, a veces, nunca
4.6. Spelling-change verbs: sacar/pagar/empezar-like basics
4.7. Build & speak: my day, habits and routines

------

### Section 5. Present 2: irregulars, stem changes, reflexives, gustar (A1-A2)

5.1. Stem-changing verbs: e-ie, o-ue, e-i
5.2. High-frequency irregulars: ir, hacer, tener, venir, decir, poner
5.3. Reflexive verbs: llamarse, levantarse, sentirse
5.4. Gustar, encantar, interesar: liking as an indirect pattern
5.5. Doler, faltar, quedar: more verbs like gustar
5.6. Estar + gerundio: what is happening right now
5.7. Present simple vs estar + gerundio
5.8. Build & speak: what I usually do vs what is happening now

------

### Section 6. Past 1: preterito perfecto and recent experience (A2)

6.1. Haber + participio: the form of preterito perfecto
6.2. Regular and irregular participles
6.3. Meaning: experience, result and unfinished time periods
6.4. Markers: ya, todavia no, alguna vez, nunca, esta semana
6.5. Preterito perfecto in Spain vs Latin America: what changes
6.6. Build & speak: recent news, experience and results

------

### Section 7. Past 2: preterito indefinido for completed actions (A2)

7.1. Regular indefinido endings
7.2. Spelling changes in -car/-gar/-zar and vowel shifts
7.3. Core irregulars: fue, tuvo, estuvo, hizo, dijo, pudo, quiso
7.4. Time markers: ayer, anoche, el ano pasado, en 2019
7.5. Sequencing events in a simple story
7.6. Build & speak: tell what happened yesterday

------

### Section 8. Past 3: imperfecto and past contrast (A2)

8.1. Imperfecto for background, repetition and description
8.2. Imperfecto forms and the three main irregulars
8.3. Indefinido vs imperfecto: event vs background
8.4. Antes, siempre, de nino: habitual past
8.5. Weather, age, time and setting in stories
8.6. Build & write: a childhood memory or scene

------

### Section 9. Future and conditionals: plans, predictions, hypotheses (A2)

9.1. Ir a + infinitive for plans and near future
9.2. Present tense for schedules and fixed arrangements
9.3. Futuro simple: forms and core uses
9.4. Futuro for probability in the present
9.5. Condicional simple: polite requests and hypotheticals
9.6. Build & speak: plans, predictions and polite requests

------

### Section 10. Obligation, ability and starter commands (A2)

10.1. Poder, saber and querer + infinitive
10.2. Tener que, deber and hay que: shades of obligation
10.3. Se puede, no se puede and esta prohibido
10.4. Affirmative commands: tu, usted and nosotros
10.5. Pronouns with infinitives, gerunds and affirmative commands
10.6. Build & speak: rules, instructions and advice

------

### Section 11. Noun phrase upgrade: quantity, comparison, precision (A2-B1)

11.1. Mucho, poco, bastante, demasiado, suficiente
11.2. Alguno, ninguno, otro, mismo, cada, todo
11.3. Comparative structures: mas/menos/tan... como
11.4. Superlatives and intensifiers: el mas..., muchisimo, super
11.5. Articles in generic reference, body parts and abstract nouns
11.6. Apocope and short adjective forms: buen, gran, primer
11.7. Neuter lo: lo bueno, lo importante
11.8. Build & speak: compare cities, people, habits and options

------

### Section 12. Prepositions and verb patterns (B1)

12.1. Personal a and object marking
12.2. Core prepositions: a, de, en, con, sin, sobre
12.3. Por vs para: the central contrast
12.4. Prepositions with time and movement: desde, hasta, hacia, por, para
12.5. Verb + preposition patterns: pensar en, depender de, contar con
12.6. Adjective + preposition patterns: contento con, parecido a, lleno de
12.7. Build & speak: directions, reasons, goals and relationships

------

### Section 13. Pronouns 1: direct and indirect objects (B1)

13.1. Direct object pronouns: lo, la, los, las
13.2. Indirect object pronouns: le, les and recipient meaning
13.3. Placement rules: before the verb or attached after it
13.4. Double pronouns: me lo, se lo, te la
13.5. Le, lo, la: baseline norm and what learners should treat as standard
13.6. Build & speak: giving, showing, buying and telling

------

### Section 14. Pronouns 2 and the se system (B1)

14.1. Reflexive vs reciprocal actions
14.2. Pronominal verbs that change meaning: ir/irse, quedar/quedarse
14.3. Accidental se: se me cayo, se nos olvido
14.4. Impersonal se and passive se
14.5. One more ser vs estar contrast: result vs state with participles
14.6. Build & write: everyday incidents, rules and short news items

------

### Section 15. Complex sentences 1: connecting ideas clearly (B1)

15.1. Que and si: noun clauses after saying, thinking and asking
15.2. Porque, como, por eso, asi que: cause and result
15.3. Pero, sino, aunque, sin embargo: contrast
15.4. Cuando, antes de, despues de, mientras: time relations
15.5. Relative clauses: que, quien, donde, cuyo starter use
15.6. Indirect questions: no se que..., me puedes decir si...
15.7. Build & write: a 120-180 word text with connectors and relative clauses

------

### Section 16. Non-finite forms and verbal periphrases (B1-B2)

16.1. Infinitive after prepositions and conjunctions
16.2. Gerundio: ongoing action, manner and what not to do with it
16.3. Participles as adjectives and result states
16.4. Periphrases of change and process: seguir + gerundio, acabar de, volver a, dejar de
16.5. Soler, llevar + gerundio, terminar por: aspect and nuance
16.6. Build & speak: routines, progress, interruption and change

------

### Section 17. Compound tenses and narration upgrades (B1-B2)

17.1. Pluscuamperfecto: past before past
17.2. Future perfect and conditional perfect
17.3. Reported sequence of past events
17.4. Timeline control: perfecto, indefinido, imperfecto, pluscuamperfecto
17.5. Build & write: biography, flashback and cause-effect chains

------

### Section 18. Subjunctive 1: present subjunctive in noun clauses (B2)

18.1. How to form the present subjunctive
18.2. Desire and influence: quiero que..., necesito que...
18.3. Emotion and evaluation: me alegra que..., es bueno que...
18.4. Doubt, denial and possibility vs certainty
18.5. Impersonal expressions and triggers of certainty
18.6. Negative commands and polite commands with subjunctive
18.7. Indicative vs subjunctive: decision rules in noun clauses
18.8. Build & speak: wishes, recommendations, emotions and opinions

------

### Section 19. Subjunctive 2: time, purpose, condition, relative clauses (B2)

19.1. Cuando, en cuanto, hasta que with future reference
19.2. Para que, a fin de que and sin que
19.3. Antes de que and despues de que with subject change
19.4. Aunque, por mas que and como si: meaning and mood choice
19.5. Relative clauses with known vs unknown or hypothetical reference
19.6. Infinitive vs subjunctive when the subject stays the same
19.7. Build & write: plans, warnings, requirements and search criteria

------

### Section 20. Subjunctive 3: past subjunctive and counterfactuals (B2)

20.1. Imperfect subjunctive forms: -ra and -se
20.2. Sequence of tenses after past reporting verbs
20.3. Si + imperfect subjunctive + conditional
20.4. Perfect subjunctive: haya hecho
20.5. Pluscuamperfecto de subjuntivo and unreal past
20.6. Third conditional and mixed counterfactuals
20.7. Build & speak: regrets, hypotheticals and alternative histories

------

### Section 21. Voice, reported speech and distancing (B2-C1)

21.1. Passive with ser and agent phrases
21.2. Se-passive vs impersonal se vs generic statements
21.3. Reported statements and questions without mechanical backshift
21.4. Reported requests, orders and recommendations
21.5. Evidential and distancing expressions: al parecer, segun, se dice que
21.6. Build & write: news, reports and formal summaries

------

### Section 22. C1 style: discourse, register, emphasis, precision (C1)

22.1. Discourse markers for argument: sin embargo, de hecho, en cambio, por lo tanto
22.2. Information structure and word order: what moves and why
22.3. Focus and emphasis strategies in Spanish
22.4. Nominalization and dense academic/professional style
22.5. Hedging, stance and precision: quiza, al parecer, es probable que...
22.6. Formal vs informal tone: email, interview, essay and debate
22.7. Build & rewrite: neutral to formal, spoken to written, direct to tactful

## Optional Later Expansions

1. Regional appendix: voseo
2. Regional appendix: stronger vosotros production track
3. Pronunciation appendix: seseo, distincion, yeismo and regional variation
4. Advanced norm appendix: leismo and other non-core standard variations
