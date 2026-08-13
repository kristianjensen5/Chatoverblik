# Auditprompts i Command Center

**Status:** begge prompts er skrevet ind i `chatoverblik.py` 2026-08-13.
Knapperne kører dem, så snart Command Center genstartes.

**Denne fil indeholder ikke prompt-teksten.** Den står i koden — én kilde.
To kopier af samme prompt driver fra hinanden, og så ved ingen hvilken der
gælder. Skal en prompt ændres, ændres den i `chatoverblik.py`.

---

## De to knapper

| | **Analyse af mit workflow** | **Stil-audit (sidste 3 uger)** |
|---|---|---|
| Endpoint | `/api/workflow-analysis` | `/api/prompting-review` |
| Prompt i koden | linje ~2431 | linje ~2851 |
| Omfang | alle chats, alle projekter | 21 dage |
| Data per chat | 400-tegns **resumé** | **faktisk** åbningsbesked (1200 tegn) + sidste besked (600 tegn) |
| max_tokens | 8000 | 16000 |
| Ser på | HVAD chats handler om, hvor projekter lander | HVORDAN Kristian formulerer sig, om chats lukkes |

**Kør begge.** De svarer på hver sin ting:

- **Workflow-analysen** giver bredden — hvilke projekter landede, live URL,
  repo, færdiggørelsesmønstre. Input til `context/08_repo_politik.md`.
- **Stil-auditten** giver dybden — Kristians egne ord, og om en chat lukkes
  eller ebber ud. Den er stærkest til adfærdsreglerne, fordi den parrer en
  chats sidste besked med næste chats første besked i samme projekt.

Stil-auditten har rådata; workflow-analysen har kun resuméer. Hvor de er
uenige, vejer stil-auditten tungest.

**Model:** Opus til begge. Det er audits af arbejdsgangen — dyb zone efter
regel 17 i `context/01_arbejdsgang.md`.

---

## Hvad de IKKE gør

Ingen af dem vurderer de 19 regler i `context/01_arbejdsgang.md`.

Command Center laver et rent API-kald **uden filadgang** — modellen kan ikke
åbne regelfilen og ville gætte sig til indholdet. Det ser rigtigt ud og er
værdiløst.

Regel-vurderingen er et **separat trin** i Claude Code eller Codex, hvor
filerne ligger på disken. Rapporterne fra de to kørsler er input til det trin.

**Rækkefølge:**

1. Kør begge knapper i Command Center → to rapporter
2. Giv rapporterne til Claude Code → dom over de 19 regler, målt mod de
   faktiske filer
3. Sonnet gennemfører oprydningen i `context/`

---

## Hvad der blev ændret 2026-08-13

### Analyse af mit workflow — omskrevet

Den gamle prompt havde rolle, men ingen af de øvrige fire greb fra
`context/07_model_playbook.md` ("Anatomi: en god dyb-model-prompt").

| Tilføjet | Hvorfor |
|---|---|
| **Forbud** | Rolle uden forbud får modellen til at glide over i teknisk kritik. Forbuddet er vigtigere end rollen |
| **Vægtning i tre bånd** | "Vægter nyere højere" er en holdning, ikke en instruks modellen kan handle på. Nu: 0-30 / 31-120 / >120 dage med hver sin brug |
| **Kategorisering A-D** | Den vigtigste tilføjelse. Uden den ser en velfungerende vane identisk ud med en død vane — begge er usynlige i data. Kategori D (situationen opstod aldrig) må aldrig bruges som argument for at afskaffe noget |
| **Beviskrav** | Hvert fund skal bære chat-titel + dage_siden. Fra Dronningen-lektien: en analyse kaldte projektet strandet, disken viste det var deployet |
| **Dataens grænser** | Modellen får kun 400-tegns resuméer. Uden blokken konkluderer den selvsikkert om en chat-midte den aldrig har set |
| **Usikkerhedsventil** | Uden den udfyldes huller med plausible gæt |
| **Maks-grænser** | Var 5 løse sektioner uden grænser → opremsning af 59 projekter. Nu tvunget prioritering |
| **Punkt 4: "det ingen regel dækker endnu"** | Ny. Den eneste leverance der kan producere en helt ny regel. Det manglende er sværere at få øje på end det overflødige |
| **Svarformat som diff** | Gør svaret anvendeligt i stedet for et essay |
| **max_tokens 4000 → 8000** | Kategorisering + kvitteringer sprængte budgettet, og svaret blev stille afkortet |

### Stil-audit — justeret, ikke omskrevet

Den var allerede den stærkeste af de to: bevis-krav, usikkerhedsventil,
"ingen kompliment-runde" og `max_tokens=16000` var på plads.

| Tilføjet | Hvorfor |
|---|---|
| **Forbud** | Samme grund som ovenfor |
| **"Du har mine faktiske ord, ikke resuméer"** | Gør styrken eksplicit, så modellen bruger citater frem for at parafrasere |
| **Alderen er allerede filtreret** | 21-dages vinduet er per definition nuværende niveau — modellen må ikke forklare et mønster væk med "han er ved at lære det" |
| **Kategori A-D ved punkt 2** | Lukke-vanen er præcis det A-D måler: skete den af sig selv, kun på opfordring, slet ikke, eller er der for få par? |
| **Maks-grænser på punkt 2, 3 og 4** | Punkt 1 havde "3-5 mønstre"; resten var ubegrænsede |
| **Punkt 6: hvad analysen ikke kan afgøre** | Den ser kun første og sidste besked. Nu skal den selv sige hvilke fund der kræver det fulde forløb |

---

## Verificering (2026-08-13)

- `python3 -m py_compile chatoverblik.py` → OK
- Alle 8 f-string-placeholders udtrukket med `ast` og kontrolleret mod
  variabler i scope: `chats_summary`, `projects_summary`, `chat_data`, `days`
  — ingen nye eller forkerte navne
- **Ikke testet:** en faktisk kørsel af de to knapper. Syntakstjek fanger
  ikke alt (jf. lektien *"Syntakstjek fanger ikke en slettet reference —
  kun en sideindlæsning gør"*). Genstart Command Center og kør begge
  knapper én gang, før resultatet bruges til noget.
